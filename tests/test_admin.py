import re

import pytest

from app import admin, config, llm

from tests.conftest import PDF_OK
from tests.test_api import ANSWERS, client, start  # noqa: F401

TOKEN = "test-admin-token-123"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


@pytest.fixture(autouse=True)
def _token(monkeypatch):
    monkeypatch.setattr(config, "ADMIN_TOKEN", TOKEN)
    admin._failures._hits.clear()
    llm.STATS.reset()


def _session(c, answers=None, confirm=False, name=None):
    sid = start(c)["session_id"]
    for i, a in enumerate(answers or []):
        c.post(f"/sessions/{sid}/messages", json={"text": a})
    if confirm:
        assert c.post(f"/sessions/{sid}/confirm").status_code == 200
    return sid


def _confirmed_with_open(c):
    a = list(ANSWERS)
    a[24] = "Developer ilə dəqiqləşdirəcəm"
    return _session(c, a, confirm=True)


# ---------- giriş və gizlilik ----------
def test_admin_is_invisible_without_token(client, monkeypatch):
    monkeypatch.setattr(config, "ADMIN_TOKEN", "")
    assert client.get("/admin").status_code == 404
    assert client.get("/admin/api/overview").status_code == 404
    assert client.get("/admin/api/overview", headers=AUTH).status_code == 404  # boş token heç vaxt uyğun gəlmir
    assert client.get("/admin/api/overview", headers={"Authorization": "Bearer "}).status_code == 404


def test_page_is_served_but_carries_no_data(client):
    r = client.get("/admin")
    assert r.status_code == 200 and "text/html" in r.headers["content-type"]
    assert r.headers["cache-control"] == "no-store"
    assert TOKEN not in r.text and "noindex" in r.text


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer wrong"}, {"Authorization": TOKEN},
                                     {"Authorization": "Basic " + TOKEN}, {"Authorization": "Bearer "}])
def test_api_requires_the_exact_token(client, headers):
    for path in ("/admin/api/overview", "/admin/api/sessions", "/admin/api/sessions/x", "/admin/api/sessions/x/download"):
        assert client.get(path, headers=headers).status_code == 401, path
    assert client.delete("/admin/api/sessions/x", headers=headers).status_code == 401


def test_query_string_token_is_not_accepted(client):
    assert client.get(f"/admin/api/overview?token={TOKEN}").status_code == 401


def test_failed_attempts_are_rate_limited_but_valid_token_still_works(client):
    codes = [client.get("/admin/api/overview", headers={"Authorization": "Bearer bad"}).status_code for _ in range(12)]
    assert codes[:10] == [401] * 10 and codes[10:] == [429, 429]
    assert client.get("/admin/api/overview", headers=AUTH).status_code == 200  # düzgün token bloklanmır


def test_responses_are_not_cached(client):
    assert client.get("/admin").headers["cache-control"] == "no-store"
    r = client.get("/admin/api/overview", headers=AUTH)
    assert r.status_code == 200


# ---------- siyahı ----------
def test_list_filters_search_and_pagination(client):
    admin_ids = {}
    admin_ids["confirmed_open"] = _confirmed_with_open(client)
    admin_ids["confirmed_clean"] = _session(client, ANSWERS, confirm=True)
    admin_ids["active"] = _session(client, ANSWERS[:3])

    def lst(**q):
        qs = "&".join(f"{k}={v}" for k, v in q.items())
        r = client.get(f"/admin/api/sessions?{qs}", headers=AUTH)
        assert r.status_code == 200
        return r.json()

    allr = lst()
    ids = {i["id"] for i in allr["items"]}
    assert set(admin_ids.values()) <= ids
    assert {i["id"] for i in lst(status="confirmed")["items"]} >= {admin_ids["confirmed_open"], admin_ids["confirmed_clean"]}
    assert admin_ids["active"] not in {i["id"] for i in lst(status="confirmed")["items"]}
    assert {i["id"] for i in lst(status="active")["items"]} >= {admin_ids["active"]}

    opened = lst(open=1)["items"]
    assert admin_ids["confirmed_open"] in {i["id"] for i in opened}
    assert admin_ids["active"] not in {i["id"] for i in opened}  # hələ heç nə keçilməyib
    assert all(i["open_count"] > 0 for i in opened)

    assert admin_ids["confirmed_clean"] in {i["id"] for i in lst(q="atlas.az")["items"]}  # e-poçtla
    assert admin_ids["confirmed_clean"] in {i["id"] for i in lst(q=admin_ids["confirmed_clean"][:8])["items"]}  # id ilə
    assert lst(q="no-such-thing-xyz")["items"] == []

    page1, page2 = lst(limit=1, offset=0), lst(limit=1, offset=1)
    assert len(page1["items"]) == 1 and len(page2["items"]) == 1
    assert page1["items"][0]["id"] != page2["items"][0]["id"] and page1["total"] == allr["total"]
    assert lst(limit=100000)["limit"] == admin.MAX_PAGE  # həddən artıq limit kəsilir

    row = next(i for i in allr["items"] if i["id"] == admin_ids["confirmed_clean"])
    assert row["status"] == "confirmed" and row["version"] == 1 and row["contact"] == "info@atlas.az"
    assert row["project"] == "Atlas Logistika" and row["cost_min"] > 0 and row["progress"] == 100


# ---------- təfərrüat ----------
def test_detail_shows_open_questions_chat_and_files(client):
    sid = _confirmed_with_open(client)
    r = client.get(f"/admin/api/sessions/{sid}", headers=AUTH)
    assert r.status_code == 200
    d = r.json()
    assert d["clarifications"] and any("raund" in c.lower() or "Düzəliş" in c for c in d["clarifications"])
    assert d["messages"][0]["role"] == "ai" and any(m["role"] == "user" for m in d["messages"])
    assert [s["title"] for s in d["sections"]][0].startswith("1.")
    assert d["versions"] == [{"version": 1, "at": d["versions"][0]["at"]}]
    assert client.get("/admin/api/sessions/does-not-exist", headers=AUTH).status_code == 404


def test_client_text_is_returned_as_data_not_markup(client):
    sid = _session(client, ["Korporativ sayt", "<script>alert(1)</script>"])
    d = client.get(f"/admin/api/sessions/{sid}", headers=AUTH).json()
    assert "<script>alert(1)</script>" in [m["content"] for m in d["messages"]]
    js = (config.ROOT / "static" / "admin.js").read_text(encoding="utf-8")
    assert not re.search(r"innerHTML|outerHTML|insertAdjacentHTML|document\.write|eval\(", js)  # yalnız textContent


def test_feedback_is_listed(client):
    sid = _session(client, ANSWERS, confirm=True)
    client.post(f"/sessions/{sid}/feedback", json={"rating": 4, "comment": "yaxşı"})
    d = client.get(f"/admin/api/sessions/{sid}", headers=AUTH).json()
    assert d["feedback"][0]["rating"] == 4 and d["feedback"][0]["comment"] == "yaxşı"
    assert client.get("/admin/api/overview", headers=AUTH).json()["feedback"]["avg"] is not None


# ---------- yükləmə / silmə ----------
def test_download_docx_pdf_zip_for_confirmed_and_409_for_active(client):
    sid = _session(client, ANSWERS, confirm=True)
    r = client.get(f"/admin/api/sessions/{sid}/download?format=docx", headers=AUTH)
    assert r.status_code == 200 and r.content[:2] == b"PK" and "Texniki_Tapsiriq_v1.docx" in r.headers["content-disposition"]
    pdf = client.get(f"/admin/api/sessions/{sid}/download?format=pdf", headers=AUTH)
    if PDF_OK:
        assert pdf.content[:4] == b"%PDF"
    else:  # GTK yoxdur: səliqəli 501, çökmə yox
        assert pdf.status_code == 501 and pdf.json()["detail"]["code"] == "pdf_unavailable"
    assert client.get(f"/admin/api/sessions/{sid}/download?format=assets", headers=AUTH).content[:2] == b"PK"
    assert client.get(f"/admin/api/sessions/{sid}/download?format=exe", headers=AUTH).status_code == 400
    active = _session(client, ANSWERS[:2])
    assert client.get(f"/admin/api/sessions/{active}/download?format=docx", headers=AUTH).status_code == 409


def test_delete_removes_session_and_files(client):
    sid = _session(client, ANSWERS, confirm=True)
    assert (config.FILES_DIR / sid).exists()
    assert client.delete(f"/admin/api/sessions/{sid}", headers=AUTH).json() == {"success": True}
    assert client.get(f"/admin/api/sessions/{sid}", headers=AUTH).status_code == 404
    assert not (config.FILES_DIR / sid).exists()
    assert client.delete(f"/admin/api/sessions/{sid}", headers=AUTH).status_code == 404


# ---------- ümumi baxış ----------
def test_overview_counts_top_skipped_and_provider_stats(client):
    _confirmed_with_open(client)
    _session(client, ANSWERS[:2])
    llm.STATS.record("gemini/gemini-2.5-flash", False, 900, "ServiceUnavailableError")
    llm.STATS.record("gemini/gemini-2.5-flash", False, 800, "ServiceUnavailableError")
    llm.STATS.record("groq/llama-3.3-70b-versatile", True, 300)
    o = client.get("/admin/api/overview", headers=AUTH).json()
    s = o["sessions"]
    assert s["total"] >= 2 and s["confirmed"] >= 1 and s["active"] >= 1 and s["with_open_questions"] >= 1
    assert s["total"] == s["confirmed"] + s["active"]
    assert any("raund" in t["label"].lower() or "Düzəliş" in t["label"] for t in o["top_open"])
    assert o["top_open"][0]["count"] >= 1
    stats = o["llm"]["stats"]
    assert stats[0]["model"] == "gemini/gemini-2.5-flash" and stats[0]["fail"] == 2 and stats[0]["fail_rate"] == 1.0  # ən çox çökən birinci
    assert o["system"]["db"] in ("sqlite", "postgresql") and set(o["system"]["notify"]) == {"email", "telegram"}
    assert "password" not in str(o).lower() and TOKEN not in str(o)


def test_admin_does_not_break_normal_api(client):
    sid = start(client)["session_id"]
    assert client.get(f"/sessions/{sid}/state").status_code == 200
    assert client.get("/").status_code == 200 and client.get("/static/admin.js").status_code == 200
