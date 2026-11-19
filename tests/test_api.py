import io
import zipfile

import pytest
from fastapi.testclient import TestClient

from app.main import app, limiter

ANSWERS = ["Korporativ sayt",
           "Atlas Logistika",
           "Yük daşımaları və sorğu toplamaq",
           "Şirkətlər (B2B)",
           "Yeni sayt (sıfırdan)",
           "Struktur uyğundur",
           "Bütün səhifələrin məzmununu sonra göndərəcəm",
           "AZ + EN",
           "Özüm idarə edəcəm",
           "Heç biri yoxdur",
           "Lazım deyil",
           "Minimalist və korporativ",
           "Hər ikisi var",
           "Loqonu sonra göndərəcəm",
           "#0A3D91",
           "Nümunə yoxdur",
           "Skrinşotum yoxdur",
           "Rəqib göstərmirəm",
           "+994 12 345 67 89, Bakı, 09:00-18:00",
           "Sosial şəbəkəm yoxdur",
           "Bakı, Nizami küç. 10",
           "info@atlas.az",
           "2-3 ay ərzində",
           "Əliyev Ali, direktor",
           "2 raund",
           "Özüm təqdim edəcəm",
           "3000-8000 AZN"]


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def start(c):
    r = c.post("/sessions", json={"consent": True, "language": "az"})
    assert r.status_code == 200
    return r.json()


def finish_chat(c, sid):
    last = None
    for a in ANSWERS:
        last = c.post(f"/sessions/{sid}/messages", json={"text": a}).json()
    return last


def test_consent_required(client):
    assert client.post("/sessions", json={"consent": False}).status_code == 400


def test_full_flow_confirm_download_delete(client):
    s = start(client)
    sid = s["session_id"]
    assert "Korporativ sayt" in s["chips"] and s["state"]["sections"][0]["status"] == "pending"
    last = finish_chat(client, sid)
    assert last["ready_for_summary"] and last["state"]["progress"] == 100
    assert len(last["state"]["sections"]) == 10

    summ = client.get(f"/sessions/{sid}/summary").json()
    assert summ["ready"] and summ["budget"]["cost_min"] > 0

    # sessiya bərpası
    st = client.get(f"/sessions/{sid}/state").json()
    assert st["messages"][0]["role"] == "ai" and st["status"] == "active"

    # təsdiqdən əvvəl yükləmə olmaz
    assert client.get(f"/sessions/{sid}/download?format=docx").status_code == 409

    r = client.post(f"/sessions/{sid}/confirm")
    assert r.status_code == 200 and r.json()["version"] == 1

    d = client.get(f"/sessions/{sid}/download?format=docx")
    assert d.status_code == 200
    z = zipfile.ZipFile(io.BytesIO(d.content))
    xml = z.read("word/document.xml").decode("utf-8")
    assert "Atlas Logistika" in xml and "Büdcə" in xml

    p = client.get(f"/sessions/{sid}/download?format=pdf")
    if p.status_code == 501:  # Windows-da GTK yoxdursa PDF mümkün deyil, Docker-də işləyir
        pytest.skip("WeasyPrint sistem kitabxanaları yoxdur")
    assert p.status_code == 200 and p.content[:4] == b"%PDF"

    # təsdiqdən sonra söhbət bağlanır
    assert client.post(f"/sessions/{sid}/messages", json={"text": "salam"}).status_code == 409

    assert client.post(f"/sessions/{sid}/feedback", json={"rating": 5, "comment": "əla"}).status_code == 200
    assert client.delete(f"/sessions/{sid}").json() == {"success": True}
    assert client.get(f"/sessions/{sid}/state").status_code == 404


def test_confirm_not_ready_returns_missing(client):
    sid = start(client)["session_id"]
    r = client.post(f"/sessions/{sid}/confirm")
    assert r.status_code == 409
    d = r.json()["detail"]
    assert d["code"] == "not_ready" and "Struktur təsdiqi" in d["missing"]


def test_validation_and_unknown_session(client):
    sid = start(client)["session_id"]
    assert client.post(f"/sessions/{sid}/messages", json={"text": "x" * 4001}).status_code == 422
    assert client.post(f"/sessions/{sid}/messages", json={"text": ""}).status_code == 422
    assert client.post("/sessions/nope/messages", json={"text": "salam"}).status_code == 404
    assert client.post(f"/sessions/{sid}/feedback", json={"rating": 9}).status_code == 422


def test_page_ops_endpoint(client):
    sid = start(client)["session_id"]
    client.post(f"/sessions/{sid}/messages", json={"text": "Korporativ sayt"})
    for t in ("Atlas", "Məqsəd", "Hər ikisi", "Yeni sayt (sıfırdan)"):
        client.post(f"/sessions/{sid}/messages", json={"text": t})
    r = client.post(f"/sessions/{sid}/page-ops", json={"ops": [{"op": "add", "name": "3D konfiqurator"}]}).json()
    assert any(p["kind"] == "custom" for p in r["state"]["page_tree"])
    assert "3D konfiqurator" in r["reply"]  # custom sual axını başladı
    r = client.post(f"/sessions/{sid}/page-ops", json={"ops": [{"op": "remove", "name": "Xidmətlər"}]}).json()
    assert all(p["name"] != "Xidmətlər" for p in r["state"]["page_tree"])


def test_rate_limit(client):
    sid = start(client)["session_id"]
    old = limiter.limit
    limiter.limit = 2
    limiter._hits.clear()
    try:
        codes = [client.post(f"/sessions/{sid}/messages", json={"text": "salam"}).status_code for _ in range(4)]
    finally:
        limiter.limit = old
        limiter._hits.clear()
    assert 429 in codes


def test_health_and_security_headers(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["db"] == "ok"
    assert "script-src 'self'" in r.headers["content-security-policy"]


def test_pii_mask():
    from app.security import mask_pii
    assert "a***@***" in mask_pii("yaz: ali@mail.az") and "[telefon]" in mask_pii("+994 50 123 45 67")


def test_confirm_is_idempotent_and_docx_regenerates(client, tmp_path):
    import shutil
    from app import config
    sid = start(client)["session_id"]
    finish_chat(client, sid)
    assert client.post(f"/sessions/{sid}/confirm").json()["version"] == 1
    assert client.post(f"/sessions/{sid}/confirm").json()["version"] == 1  # yeni versiya yaranmır
    shutil.rmtree(config.FILES_DIR / sid)  # hostinqdə disk sıfırlanması
    assert client.get(f"/sessions/{sid}/download?format=docx").status_code == 200


def test_xff_ignored_without_trust_proxy(client):
    from app import main
    old = main.limiter.limit
    main.limiter.limit = 2
    try:
        codes = [client.post("/sessions", json={"consent": True}, headers={"X-Forwarded-For": f"9.9.9.{i}"}).status_code
                 for i in range(4)]
    finally:
        main.limiter.limit = old
        main.limiter._hits.clear()
    assert codes[-1] == 429


def test_logo_upload_validation(client):
    import base64
    sid = start(client)["session_id"]
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 50
    ok = client.post(f"/sessions/{sid}/logo", json={"filename": "logo.png", "data": base64.b64encode(png).decode()})
    assert ok.status_code == 200
    sec4 = next(s for s in ok.json()["state"]["sections"] if s["number"] == 4)
    assert any("logo.png" in str(i["value"]) for i in sec4["items"])
    assert client.get(f"/sessions/{sid}/logo").content == png
    svg = base64.b64encode(b"<svg onload=alert(1)>").decode()
    assert client.post(f"/sessions/{sid}/logo", json={"filename": "x.svg", "data": svg}).status_code == 415
    assert client.post(f"/sessions/{sid}/logo", json={"filename": "x.png", "data": "!!!"}).status_code == 400
    big = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"0" * (2 * 1024 * 1024)).decode()
    assert client.post(f"/sessions/{sid}/logo", json={"filename": "b.png", "data": big}).status_code == 413


def test_logo_upload_advances_to_colors_and_restores_widget(client):
    import base64
    sid = start(client)["session_id"]
    for a in ANSWERS[:ANSWERS.index("Hər ikisi var") + 1]:  # brand_assets cavabına qədər
        r = client.post(f"/sessions/{sid}/messages", json={"text": a}).json()
    assert r["widget"] == "logo" and "Loqonu sonra göndərəcəm" in r["chips"]
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 50
    up = client.post(f"/sessions/{sid}/logo", json={"filename": "logo.png", "data": base64.b64encode(png).decode()}).json()
    assert up["widget"] == "colors" and "logo.png" in up["reply"]  # avtomatik növbəti sual: rənglər
    st = client.get(f"/sessions/{sid}/state").json()
    assert st["messages"][-1]["widget"] == "colors"  # səhifə yenilənəndə vidjet bərpa olunur
    r = client.post(f"/sessions/{sid}/messages", json={"text": "#0A3D91, #FF8A00"}).json()
    assert r["widget"] is None
    summ = client.get(f"/sessions/{sid}/summary").json()
    sec4 = next(x for x in summ["sections"] if x["number"] == 4)
    vals = " ".join(str(i["value"]) for i in sec4["items"])
    assert "logo.png" in vals and "#0A3D91" in vals


def test_all_llm_models_down_falls_back_instead_of_503():
    from app import llm
    from app.schemas import TZState

    class Down:
        def extract(self, ctx):
            raise llm.LLMUnavailable("503")

    ex = llm.ResilientExtractor(Down(), llm.HeuristicExtractor())
    ext = ex.extract(llm.Ctx(TZState(), "Korporativ sayt", "field:site_type", "?"))
    assert ext is not None


def test_litellm_chain_skips_failed_model(monkeypatch):
    import sys
    import types
    from app import llm
    from app.schemas import TZState
    calls = []

    class ServiceUnavailableError(Exception):
        pass

    def completion(model, **kw):
        calls.append(model)
        if model == "a/bad":
            raise ServiceUnavailableError("503")
        msg = types.SimpleNamespace(content='{"fields": {"site_type": "Korporativ sayt"}}')
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=msg)])

    fake = types.SimpleNamespace(completion=completion, drop_params=False)
    monkeypatch.setitem(sys.modules, "litellm", fake)
    ex = llm.LiteLLMExtractor(["a/bad", "b/good"], timeout=1, cooldown=60)
    ctx = llm.Ctx(TZState(), "Korporativ sayt", "field:site_type", "?")
    assert ex.extract(ctx).fields["site_type"] == "Korporativ sayt"
    assert calls == ["a/bad", "b/good"]
    calls.clear()
    ex.extract(ctx)  # xəta verən model cooldown-dadır: dərhal yaxşı modelə keçir
    assert calls == ["b/good"]


def test_llm_trace_records_order_and_answering_model(monkeypatch):
    import sys
    import types
    from app import llm
    from app.schemas import TZState
    llm.STATS.reset()

    class ServiceUnavailableError(Exception):
        pass

    def completion(model, **kw):
        if model == "a/bad":
            raise ServiceUnavailableError("503")
        msg = types.SimpleNamespace(content='{"fields": {"site_type": "Korporativ sayt"}}')
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=msg)])

    monkeypatch.setitem(sys.modules, "litellm", types.SimpleNamespace(completion=completion, drop_params=False))
    ex = llm.LiteLLMExtractor(["a/bad", "b/good"], timeout=1, cooldown=60)
    llm.take_run()
    ex.extract(llm.Ctx(TZState(), "Korporativ sayt", "field:site_type", "?"))
    run = llm.take_run()
    assert run["order"] == ["a/bad", "b/good"] and run["answered_by"] == "b/good"
    assert [(t["model"], t["outcome"]) for t in run["tried"]] == [("a/bad", "ServiceUnavailableError"), ("b/good", "ok")]
    assert llm.take_run() is None  # oxunandan sonra təmizlənir
    stats = {r["model"]: r for r in llm.STATS.snapshot()}
    assert stats["a/bad"]["fail"] == 1 and stats["a/bad"]["last_error"] == "ServiceUnavailableError"
    assert stats["b/good"]["ok"] == 1 and llm.STATS.snapshot()[0]["model"] == "a/bad"  # ən çox çökən birinci


def test_all_down_trace_says_heuristic():
    from app import llm
    from app.schemas import TZState

    class Down:
        def extract(self, ctx):
            llm.begin_run(["x/y"])
            raise llm.LLMUnavailable("503")

    llm.take_run()
    llm.ResilientExtractor(Down(), llm.HeuristicExtractor()).extract(llm.Ctx(TZState(), "Korporativ sayt", "field:site_type", "?"))
    assert llm.take_run()["answered_by"] == "heuristic"


def test_turn_log_has_no_stale_llm_trace_for_chip_answers(client, caplog):
    import logging
    from app import llm
    sid = start(client)["session_id"]
    caplog.set_level(logging.INFO, logger="tz.api")
    llm.begin_run(["m/one"])  # əvvəlki sorğudan qalmış iz simulyasiyası
    client.post(f"/sessions/{sid}/messages", json={"text": "Korporativ sayt"})  # chip: LLM çağırılmır
    turn = [r for r in caplog.records if r.name == "tz.api" and r.getMessage() == "turn"][-1]
    assert "answered_by" not in turn.ctx and turn.ctx["slot"]


def test_state_and_turn_expose_why(client):
    s = start(client)
    assert s["why"]
    sid = s["session_id"]
    r = client.post(f"/sessions/{sid}/messages", json={"text": "Korporativ sayt"}).json()
    assert r["why"]
    msgs = client.get(f"/sessions/{sid}/state").json()["messages"]
    assert msgs[-1]["why"] == r["why"]


# ---------- loqo və brend: bir neçə fayl, rəng nümunələri, skrinşotlar ----------
def _png(w=8, h=8, rgb=(10, 61, 145)):
    """Həqiqətən açılan minimal PNG (sənədə yerləşdirmə testi üçün)."""
    import struct
    import zlib

    def chunk(t, d):
        c = struct.pack(">I", len(d)) + t + d
        return c + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    raw = b"".join(b"\x00" + bytes(rgb) * w for _ in range(h))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def _b64(b):
    import base64
    return base64.b64encode(b).decode()


def _file(name, data, kind="logo"):
    return {"filename": name, "data": _b64(data), "kind": kind}


JPG = b"\xff\xd8\xff\xe0" + b"0" * 40
PDF = b"%PDF-1.4\n" + b"0" * 40


def to_logo_question(c):
    sid = start(c)["session_id"]
    for a in ANSWERS[:ANSWERS.index("Hər ikisi var") + 1]:
        c.post(f"/sessions/{sid}/messages", json={"text": a})
    return sid


def test_upload_several_logo_variants_in_one_request(client):
    sid = to_logo_question(client)
    r = client.post(f"/sessions/{sid}/files", json={"files": [_file("light.png", _png()), _file("dark.jpg", JPG)]})
    assert r.status_code == 200
    body = r.json()
    assert [f["filename"] for f in body["files"]] == ["light.png", "dark.jpg"]
    assert body["widget"] == "colors"  # loqo cavablandı: növbəti sual
    sec4 = next(s for s in body["state"]["sections"] if s["number"] == 4)
    logo_item = next(i for i in sec4["items"] if "light.png" in str(i["value"]))
    assert "dark.jpg" in logo_item["value"]
    assert len(body["state"]["files"]) == 2
    assert client.get(f"/sessions/{sid}/files").json()["files"][1]["ext"] == "jpg"


def test_file_kinds_and_types_are_enforced(client):
    sid = start(client)["session_id"]
    post = lambda f: client.post(f"/sessions/{sid}/files", json={"files": [f]}).status_code  # noqa: E731
    assert post(_file("g.pdf", PDF, "guide")) == 200
    assert post(_file("g.pdf", PDF, "logo")) == 415  # PDF loqo ola bilməz
    assert post(_file("x.png", _png(), "guide")) == 415  # bələdçi yalnız PDF
    assert post(_file("x.svg", b"<svg onload=alert(1)>", "reference")) == 415
    assert client.post(f"/sessions/{sid}/files", json={"files": [{"filename": "a", "data": "!!!", "kind": "logo"}]}).status_code == 400
    assert client.post(f"/sessions/{sid}/files", json={"files": [{"filename": "a", "data": _b64(_png()), "kind": "evil"}]}).status_code == 422
    assert client.post(f"/sessions/{sid}/files", json={"files": []}).status_code == 422
    big = _png() + b"0" * (2 * 1024 * 1024)
    assert post(_file("big.png", big)) == 413


def test_batch_is_all_or_nothing_and_limits_apply(client):
    sid = start(client)["session_id"]
    bad = client.post(f"/sessions/{sid}/files", json={"files": [_file("ok.png", _png()), _file("bad.svg", b"<svg/>")]})
    assert bad.status_code == 415
    assert client.get(f"/sessions/{sid}/files").json()["files"] == []  # ok.png də saxlanmadı
    for i in range(6):
        assert client.post(f"/sessions/{sid}/files", json={"files": [_file(f"l{i}.png", _png())]}).status_code == 200
    over = client.post(f"/sessions/{sid}/files", json={"files": [_file("l7.png", _png())]})
    assert over.status_code == 409 and over.json()["detail"]["code"] == "too_many_files"


def test_get_and_delete_file_and_open_question_when_all_logos_removed(client):
    sid = to_logo_question(client)
    out = client.post(f"/sessions/{sid}/files", json={"files": [_file("a.png", _png()), _file("b.png", _png())]}).json()
    a, b = out["files"]
    assert client.get(f"/sessions/{sid}/files/{a['id']}").content == _png()
    assert client.get(f"/sessions/{sid}/files/nope").status_code == 404
    r = client.delete(f"/sessions/{sid}/files/{a['id']}").json()
    assert [f["filename"] for f in r["files"]] == ["b.png"]
    summ = client.get(f"/sessions/{sid}/summary").json()
    assert "a.png" not in str(summ["sections"]) and "b.png" in str(summ["sections"])
    client.delete(f"/sessions/{sid}/files/{b['id']}")
    summ = client.get(f"/sessions/{sid}/summary").json()
    assert any("Loqo faylı" in c for c in summ["clarifications"])  # dəyər uydurulmur: açıq sual
    assert client.delete(f"/sessions/{sid}/files/{b['id']}").status_code == 404


def test_pdf_guide_is_downloaded_as_attachment_and_listed(client):
    sid = start(client)["session_id"]
    g = client.post(f"/sessions/{sid}/files", json={"files": [_file("brand.pdf", PDF, "guide")]}).json()["files"][0]
    r = client.get(f"/sessions/{sid}/files/{g['id']}")
    assert r.headers["content-type"] == "application/pdf" and "attachment" in r.headers["content-disposition"]
    summ = client.get(f"/sessions/{sid}/summary").json()
    sec4 = next(x for x in summ["sections"] if x["number"] == 4)
    assert any(i["label"] == "Brend bələdçisi (PDF)" and "brand.pdf" in i["value"] for i in sec4["items"])


def test_upload_mid_flow_keeps_the_same_question(client):
    sid = start(client)["session_id"]  # hələ sayt növü sualındayıq
    r = client.post(f"/sessions/{sid}/files", json={"files": [_file("ref.png", _png(), "reference")]}).json()
    assert "ref.png" in r["reply"] and "Hazırlamaq istədiyiniz saytın növü" in r["reply"]


def test_old_logo_endpoint_still_works_and_adds_instead_of_replacing(client):
    sid = start(client)["session_id"]
    for n in ("one.png", "two.png"):
        assert client.post(f"/sessions/{sid}/logo", json={"filename": n, "data": _b64(_png())}).status_code == 200
    assert len(client.get(f"/sessions/{sid}/files").json()["files"]) == 2
    assert client.get(f"/sessions/{sid}/logo").content == _png()


def test_reference_screenshots_question_and_upload(client):
    sid = start(client)["session_id"]
    for a in ANSWERS[:ANSWERS.index("Nümunə yoxdur") + 1]:
        r = client.post(f"/sessions/{sid}/messages", json={"text": a}).json()
    assert r["widget"] == "references" and "Skrinşotum yoxdur" in r["chips"]
    up = client.post(f"/sessions/{sid}/files", json={"files": [_file("s1.png", _png(), "reference"), _file("s2.jpg", JPG, "reference")]}).json()
    sec4 = next(s for s in up["state"]["sections"] if s["number"] == 4)
    assert any("2 skrinşot" in str(i["value"]) for i in sec4["items"])
    assert "Rəqib" in up["reply"] or "rəqib" in up["reply"]  # növbəti sual


def test_color_swatches_in_summary_docx_and_pdf_html(client):
    sid = start(client)["session_id"]
    for a in ANSWERS[:ANSWERS.index("#0A3D91") + 1]:
        client.post(f"/sessions/{sid}/messages", json={"text": a})
    client.post(f"/sessions/{sid}/messages", json={"text": "#0a3d91, #f80"})  # ehtiyat: son cavab artıq rəngdir
    summ = client.get(f"/sessions/{sid}/summary").json()
    sec4 = next(x for x in summ["sections"] if x["number"] == 4)
    item = next(i for i in sec4["items"] if i.get("swatches"))
    assert item["swatches"] == ["#0A3D91"]
    from app import docgen
    h = docgen.build_html(summ)
    assert "class='sw'" in h and "background:#0A3D91" in h


def test_swatch_parsing_rules():
    from app import rules
    assert rules.parse_hex_colors("#0a3d91, #F80 və #0A3D91 təkrar") == ["#0A3D91", "#FF8800"]
    assert rules.parse_hex_colors("tünd mavi və narıncı") == []  # sözdən HEX uydurulmur
    assert rules.parse_hex_colors("#12345") == [] and rules.parse_hex_colors("a#123456") == []
    assert len(rules.parse_hex_colors(" ".join(f"#00000{i}" for i in range(9)))) == 6


def test_docx_has_shaded_swatch_and_embeds_images(client):
    sid = start(client)["session_id"]
    for a in ANSWERS:
        if a == "Loqonu sonra göndərəcəm":
            client.post(f"/sessions/{sid}/files", json={"files": [_file("logo.png", _png(), "logo")]})
            continue
        client.post(f"/sessions/{sid}/messages", json={"text": a})
    client.post(f"/sessions/{sid}/files", json={"files": [_file("ref.png", _png(40, 20, (200, 30, 30)), "reference")]})
    assert client.post(f"/sessions/{sid}/confirm").status_code == 200
    d = client.get(f"/sessions/{sid}/download?format=docx")
    z = zipfile.ZipFile(io.BytesIO(d.content))
    xml = z.read("word/document.xml").decode("utf-8")
    assert 'w:fill="0A3D91"' in xml  # rəng nümunəsi xanası
    media = [n for n in z.namelist() if n.startswith("word/media/")]
    assert len(media) == 2  # loqo + skrinşot sənədə yerləşdirilib


def test_docx_regenerates_without_images_when_disk_was_reset(client):
    import shutil
    from app import config
    sid = start(client)["session_id"]
    for a in ANSWERS:
        if a == "Loqonu sonra göndərəcəm":
            client.post(f"/sessions/{sid}/files", json={"files": [_file("logo.png", _png(), "logo")]})
            continue
        client.post(f"/sessions/{sid}/messages", json={"text": a})
    client.post(f"/sessions/{sid}/confirm")
    shutil.rmtree(config.FILES_DIR / sid)  # pulsuz hostinqdə disk sıfırlandı
    d = client.get(f"/sessions/{sid}/download?format=docx")
    assert d.status_code == 200 and d.content[:2] == b"PK"


def test_assets_zip_download(client):
    sid = start(client)["session_id"]
    for a in ANSWERS:
        if a == "Loqonu sonra göndərəcəm":
            client.post(f"/sessions/{sid}/files", json={"files": [_file("logo.png", _png(), "logo"),
                                                                   _file("logo.png", _png(), "logo"),
                                                                   _file("brand.pdf", PDF, "guide")]})
            continue
        client.post(f"/sessions/{sid}/messages", json={"text": a})
    assert client.get(f"/sessions/{sid}/download?format=assets").status_code == 409  # təsdiqdən əvvəl yox
    client.post(f"/sessions/{sid}/confirm")
    r = client.get(f"/sessions/{sid}/download?format=assets")
    names = sorted(zipfile.ZipFile(io.BytesIO(r.content)).namelist())
    assert names == ["guide/brand.pdf", "logo/logo.png", "logo/logo_2.png"]


def test_uploads_blocked_after_confirm_and_deleted_with_session(client):
    from app import config
    sid = start(client)["session_id"]
    for a in ANSWERS:
        if a == "Loqonu sonra göndərəcəm":
            client.post(f"/sessions/{sid}/files", json={"files": [_file("logo.png", _png(), "logo")]})
            continue
        client.post(f"/sessions/{sid}/messages", json={"text": a})
    client.post(f"/sessions/{sid}/confirm")
    assert client.post(f"/sessions/{sid}/files", json={"files": [_file("x.png", _png())]}).status_code == 409
    fid = client.get(f"/sessions/{sid}/files").json()["files"][0]["id"]
    assert client.delete(f"/sessions/{sid}/files/{fid}").status_code == 409
    assert (config.FILES_DIR / sid).exists()
    client.delete(f"/sessions/{sid}")
    assert not (config.FILES_DIR / sid).exists()
