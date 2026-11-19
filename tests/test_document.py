"""7-ci hissə (sənəd: açıq suallar başda + başlıq/loqo) və 8-ci hissə (data bütövlüyü)."""
import io

import pytest
import yaml
from docx import Document
from PIL import Image

from app import catalog, config, docgen

from tests.conftest import PDF_OK
from tests.test_api import ANSWERS, client, start  # noqa: F401

DONT_KNOW = "Developer ilə dəqiqləşdirəcəm"


def _confirmed(c, answers=None):
    sid = start(c)["session_id"]
    for a in answers or ANSWERS:
        c.post(f"/sessions/{sid}/messages", json={"text": a})
    r = c.post(f"/sessions/{sid}/confirm")
    assert r.status_code == 200, r.text
    return sid, r.json()["summary"]


def _with_open():
    a = list(ANSWERS)
    a[24] = DONT_KNOW  # düzəliş raundları
    return a


def _logo(tmp_path):
    p = tmp_path / "agency.png"
    Image.new("RGB", (120, 120), (250, 180, 40)).save(p)
    return p


def _paras(doc):
    return [(p.style.name, p.text) for p in doc.paragraphs]


def test_docx_open_questions_come_before_section_one(client):
    sid, tz = _confirmed(client, _with_open())
    assert tz["clarifications"]
    doc = Document(io.BytesIO(client.get(f"/sessions/{sid}/download?format=docx").content))
    heads = [t for s, t in _paras(doc) if s.startswith("Heading 1")]
    assert heads[0].startswith("Açıq suallar")
    assert heads[1].startswith("1.")
    bullets = [t for s, t in _paras(doc) if s == "List Bullet"][:len(tz["clarifications"])]
    assert bullets == tz["clarifications"]


def test_docx_and_html_say_so_when_nothing_is_open(client):
    from app import tz_builder  # noqa: F401
    _, tz = _confirmed(client)
    tz = dict(tz, clarifications=[])
    html = docgen.build_html(tz)
    assert html.index("Açıq suallar") < html.index("1. Layihə")
    assert "Açıq sual yoxdur" in html


@pytest.mark.parametrize("lang,head", [("en", "Open questions"), ("ru", "Открытые вопросы")])
def test_open_questions_heading_follows_language(client, lang, head):
    from tests.test_api import ANSWERS as _A  # noqa: F401
    sid = client.post("/sessions", json={"consent": True, "language": lang}).json()["session_id"]
    tz = client.get(f"/sessions/{sid}/summary").json()
    tz = dict(tz, clarifications=["x"])
    assert head in docgen.build_html(tz)


@pytest.mark.skipif(not PDF_OK, reason="WeasyPrint sistem kitabxanaları (GTK) yoxdur")
def test_pdf_has_open_questions_before_sections(client):
    sid, _ = _confirmed(client, _with_open())
    r = client.get(f"/sessions/{sid}/download?format=pdf")
    assert r.status_code == 200 and r.content[:4] == b"%PDF"
    html = docgen.build_html(client.get(f"/sessions/{sid}/summary").json())
    assert html.index("Açıq suallar") < html.index("1. Layihə")


def test_agency_header_with_logo_in_docx_and_html(client, monkeypatch, tmp_path):
    monkeypatch.setattr(config, "AGENCY_NAME", "Atlas Digital")
    monkeypatch.setattr(config, "AGENCY_TAGLINE", "Web studio")
    monkeypatch.setattr(config, "AGENCY_LOGO_PATH", _logo(tmp_path))
    sid, tz = _confirmed(client)
    doc = Document(io.BytesIO(client.get(f"/sessions/{sid}/download?format=docx").content))
    first = doc.tables[0]
    assert len(first.rows[0].cells) == 2
    assert "Atlas Digital" in first.rows[0].cells[1].text
    assert len(doc.inline_shapes) >= 1  # agentlik loqosu
    html = docgen.build_html(tz)
    assert "Atlas Digital" in html and "class='aglogo'" in html and "data:image/png;base64," in html


def test_agency_header_without_logo(client, monkeypatch):
    monkeypatch.setattr(config, "AGENCY_NAME", "Atlas Digital")
    monkeypatch.setattr(config, "AGENCY_LOGO_PATH", None)
    sid, tz = _confirmed(client)
    doc = Document(io.BytesIO(client.get(f"/sessions/{sid}/download?format=docx").content))
    assert len(doc.tables[0].rows[0].cells) == 1 and "Atlas Digital" in doc.tables[0].rows[0].cells[0].text
    assert "class='aglogo'" not in docgen.build_html(tz)


def test_agency_header_is_escaped(monkeypatch):
    monkeypatch.setattr(config, "AGENCY_NAME", "<script>alert(1)</script>")
    monkeypatch.setattr(config, "AGENCY_LOGO_PATH", None)
    assert "<script>" not in docgen._html_banner()


def test_broken_agency_logo_does_not_break_docx(client, monkeypatch, tmp_path):
    bad = tmp_path / "bad.png"
    bad.write_bytes(b"not an image")
    monkeypatch.setattr(config, "AGENCY_LOGO_PATH", bad)
    sid, _ = _confirmed(client)
    assert client.get(f"/sessions/{sid}/download?format=docx").status_code == 200


# ---------- 8: modul və şablon datası ----------
def _yaml(name):
    return yaml.safe_load((config.ROOT / "data" / name).read_text(encoding="utf-8"))


def test_new_site_types_and_modules_exist():
    templates, modules = _yaml("templates.yaml"), _yaml("modules.yaml")["modules"]
    assert {"news", "school", "directory"} <= set(templates)
    ids = {m["id"] for m in modules}
    assert {"events", "timetable", "courses", "admissions", "documents", "listings", "listing_detail"} <= ids


def test_every_template_reference_resolves_and_is_translated():
    templates, mods = _yaml("templates.yaml"), {m["id"]: m for m in _yaml("modules.yaml")["modules"]}
    for tid, t in templates.items():
        for lang in ("az", "en", "ru"):
            assert t["title"].get(lang), (tid, lang)
        for p in t["pages"]:
            for lang in ("az", "en", "ru"):
                assert p["name"].get(lang) and p["purpose"].get(lang), (tid, p["name"], lang)
            for m in p.get("modules", []):
                assert m in mods, (tid, m)
        for m in t.get("global", []) + t.get("suggest", []):
            assert m in mods, (tid, m)


def test_every_module_is_fully_translated_and_requires_resolve():
    mods = _yaml("modules.yaml")["modules"]
    ids = {m["id"] for m in mods}
    assert len(ids) == len(mods)  # dublikat id yoxdur
    for m in mods:
        assert m["hours"] > 0, m["id"]
        for key in ("title", "desc"):
            for lang in ("az", "en", "ru"):
                assert m[key].get(lang), (m["id"], key, lang)
        for r in m.get("requires", []):
            assert r in ids, (m["id"], r)


@pytest.mark.parametrize("site,page", [("Xəbər saytı", "Xəbərlər"), ("Məktəb / təhsil saytı", "Qəbul"),
                                       ("Kataloq / directory", "Kataloq")])
def test_new_site_types_start_a_chat_and_offer_a_structure(client, site, page):
    """Yeni sayt növü seçiləndə söhbət çökmür və şablon strukturu yaranır."""
    sid = start(client)["session_id"]
    r = None
    for text in (site, "Test layihə", "Məlumat vermək", "Oxucular", "Yeni sayt (sıfırdan)"):
        r = client.post(f"/sessions/{sid}/messages", json={"text": text})
        assert r.status_code == 200, (site, r.text)
    tree = r.json()["state"]["page_tree"]
    assert page in [p["name"] for p in tree], [p["name"] for p in tree]
    assert all(p["purpose"] and not p["purpose"].startswith("{") for p in tree)
