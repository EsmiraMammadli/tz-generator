from fastapi.testclient import TestClient  # noqa: F401  (fixture client comes from test_api)

from app import engine, rules
from app.llm import HeuristicExtractor, strip_links
from app.schemas import TZState

from tests.test_api import client, finish_chat, start  # noqa: F401

X = HeuristicExtractor()


def _finished(client):
    sid = start(client)["session_id"]
    finish_chat(client, sid)
    return sid


def _post(client, sid, **body):
    return client.post(f"/sessions/{sid}/answers", json=body)


def _field_ids(summary):
    return {i["field_id"]: i for s in summary["sections"] for i in s["items"] if i.get("field_id")}


def test_url_tld_is_not_read_as_language():
    assert "az" not in strip_links("https://atlas-kohne.az və www.atlas.az, ali@mail.az").lower().split()
    s = TZState()
    engine.start(s)
    for t in ("Korporativ sayt", "Atlas", "Məqsəd", "Hər ikisi", "Mövcud saytın yenidən hazırlanması",
              "https://atlas-kohne.az"):
        engine.process_turn(s, t, X)
    assert "languages" not in s.fields  # «.az» domeni dil seçimi sayılmır


def test_edit_choice_and_text_from_summary(client):
    sid = _finished(client)
    r = _post(client, sid, fields={"company_name": "Yeni Ad MMC", "revision_rounds": "3 raund"})
    assert r.status_code == 200
    body = r.json()
    assert body["updated"] and body["rejected"] == [] and body["needs_chat"] is False
    items = _field_ids(body["summary"])
    assert items["company_name"]["value"] == "Yeni Ad MMC"
    assert items["revision_rounds"]["value"] == "3 raund"
    assert body["summary"]["ready"] is True


def test_invalid_value_is_not_written(client):
    sid = _finished(client)
    r = _post(client, sid, fields={"contact_email": "email-deyil"})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "invalid_value"
    r = _post(client, sid, fields={"company_name": "Başqa Ad", "contact_email": "yanlis"})
    assert r.status_code == 200 and len(r.json()["rejected"]) == 1 and r.json()["updated"]
    summary = client.get(f"/sessions/{sid}/summary").json()
    assert _field_ids(summary)["contact_email"]["value"] == "info@atlas.az"  # köhnə düzgün dəyər qalır


def test_site_type_and_unknown_fields_are_rejected(client):
    sid = _finished(client)
    assert _post(client, sid, fields={"site_type": "Onlayn mağaza"}).status_code == 422
    assert _post(client, sid, fields={"nonexistent": "x"}).status_code == 422
    assert _post(client, sid).status_code == 422  # boş sorğu
    assert _field_ids(client.get(f"/sessions/{sid}/summary").json())["site_type"]["editable"] is False


def test_changing_answer_prunes_dependent_field_and_asks_new_question(client):
    sid = _finished(client)
    # «Heç biri yoxdur» → domen adı soruşulmayıb; «Domen və hostinq var» seçəndə domen adı sualı açılır
    r = _post(client, sid, fields={"domain_hosting": "Domen və hostinq var"}).json()
    assert r["needs_chat"] is True and r["pending_slot"] == "field:domain_name"
    msgs = client.get(f"/sessions/{sid}/state").json()["messages"]
    assert "domen" in msgs[-1]["content"].lower()  # söhbətdə yeni sual görünür
    # domen adını xülasədən də yazmaq olar
    r = _post(client, sid, fields={"domain_name": "atlas.az"}).json()
    assert r["needs_chat"] is False and _field_ids(r["summary"])["domain_name"]["value"] == "atlas.az"
    # geri «heç biri yoxdur»: domen adı silinir
    r = _post(client, sid, fields={"domain_hosting": "Heç biri yoxdur"}).json()
    assert r["dropped"] and "domain_name" not in _field_ids(r["summary"])


def test_mark_open_and_resolve_open_question(client):
    sid = _finished(client)
    r = _post(client, sid, open=["competitors"]).json()
    assert "competitors" in _field_ids(r["summary"]) and _field_ids(r["summary"])["competitors"]["source"] == "open"
    assert any("Rəqib" in c for c in r["summary"]["clarifications"])
    r = _post(client, sid, fields={"competitors": "rəqib.az"}).json()
    assert _field_ids(r["summary"])["competitors"]["source"] == "user"
    assert not any("Rəqib" in c for c in r["summary"]["clarifications"])


def test_page_content_edit_and_required_field_cannot_be_opened(client):
    sid = _finished(client)
    summary = client.get(f"/sessions/{sid}/summary").json()
    pid = summary["page_tree"][0]["id"]
    r = _post(client, sid, page_content={pid: "Şirkət haqqında mətn, 5 şəkil"}).json()
    page = next(p for p in r["summary"]["page_tree"] if p["id"] == pid)
    assert page["content"].startswith("Şirkət") and page["content_status"] == "answered"
    # məcburi sahə (ad) «açıq sual» edilə bilməz
    assert _post(client, sid, open=["company_name"]).status_code == 422


def test_edits_blocked_after_confirm(client):
    sid = _finished(client)
    assert client.post(f"/sessions/{sid}/confirm").status_code == 200
    assert _post(client, sid, fields={"company_name": "X"}).status_code == 409
    assert _post(client, "nope", fields={"company_name": "X"}).status_code == 404


def test_edit_reflected_in_docx(client):
    import io
    import zipfile
    sid = _finished(client)
    _post(client, sid, fields={"company_name": "Düzəldilmiş Ad"})
    client.post(f"/sessions/{sid}/confirm")
    z = zipfile.ZipFile(io.BytesIO(client.get(f"/sessions/{sid}/download?format=docx").content))
    assert "Düzəldilmiş Ad" in z.read("word/document.xml").decode("utf-8")
