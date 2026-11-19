import io
import zipfile

import pytest
from fastapi.testclient import TestClient

from app.main import app

FLOWS = {
    "en": ["Corporate website", "Atlas Logistics", "Freight transport and collecting inquiries", "Companies (B2B)", "New website (from scratch)", "Structure looks good", "I will send the content for all pages later", "AZ + EN", "I will manage it myself", "Neither", "Not needed", "Minimalist and corporate", "I have both", "I will send the logo later", "#0A3D91", "No examples", "I have no screenshots", "No competitors to share", "+994 12 345 67 89, Baku, 09:00-18:00", "I have no social media pages", "Baku, Nizami str. 10", "info@atlas.az", "Within 2-3 months", "Ali Aliyev, director", "2 rounds", "I will provide them", "3000-8000 AZN"],
    "ru": ["Корпоративный сайт", "Атлас Логистика", "Грузоперевозки и сбор заявок", "Компании (B2B)", "Новый сайт (с нуля)", "Структура подходит", "Контент всех страниц отправлю позже", "AZ + EN", "Буду управлять сам(а)", "Нет ни того ни другого", "Не нужно", "Минималистичный и корпоративный", "Есть и то и другое", "Логотип отправлю позже", "#0A3D91", "Примеров нет", "Скриншотов нет", "Конкурентов не указываю", "+994 12 345 67 89, Баку, 09:00-18:00", "Соцсетей нет", "Баку, ул. Низами 10", "info@atlas.az", "В течение 2-3 месяцев", "Алиев Али, директор", "2 раунда", "Я предоставлю сам(а)", "3000-8000 AZN"],
}
EXPECT = {"en": ("Technical Specification", "Platform (recommended)", "WordPress"),
          "ru": ("Техническое задание", "Платформа (рекомендация)", "WordPress")}


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


@pytest.mark.parametrize("lang", ["en", "ru"])
def test_full_flow_in_language(client, lang):
    s = client.post("/sessions", json={"consent": True, "language": lang}).json()
    sid = s["session_id"]
    assert "Корпоративный сайт" in s["chips"] if lang == "ru" else "Corporate website" in s["chips"]
    last = None
    for a in FLOWS[lang]:
        last = client.post(f"/sessions/{sid}/messages", json={"text": a}).json()
    assert last["ready_for_summary"] and last["state"]["progress"] == 100
    summ = client.get(f"/sessions/{sid}/summary").json()
    title, platform_label, wp = EXPECT[lang]
    assert summ["title"].startswith(title) and summ["language"] == lang
    sec2 = next(x for x in summ["sections"] if x["number"] == 2)
    assert any(i["label"] == platform_label for i in sec2["items"])
    assert client.get(f"/sessions/{sid}/state").json()["language"] == lang
    assert client.post(f"/sessions/{sid}/confirm").status_code == 200
    d = client.get(f"/sessions/{sid}/download?format=docx")
    xml = zipfile.ZipFile(io.BytesIO(d.content)).read("word/document.xml").decode("utf-8")
    assert title.upper() in xml.upper() and FLOWS[lang][1] in xml
    # AZ mətni sənədə sızmamalıdır
    assert "Texniki" not in xml and "Büdcə" not in xml


def test_typed_free_text_in_english_and_structure_edit(client):
    sid = client.post("/sessions", json={"consent": True, "language": "en"}).json()["session_id"]
    for a in FLOWS["en"][:5]:  # mövcud sayt sualına qədər: struktur sualı gəlir
        client.post(f"/sessions/{sid}/messages", json={"text": a})
    r = client.post(f"/sessions/{sid}/messages", json={"text": "I also want a blog"}).json()
    assert any(p["name"] == "Blog / News" or any(m["type"] == "blog" for m in p["modules"]) for p in r["state"]["page_tree"])
    # səhifə adı + təsviri redaktəsi
    ops = {"ops": [{"op": "rename", "name": "Home page", "new_name": "Start", "purpose": "Intro"}]}
    r = client.post(f"/sessions/{sid}/page-ops", json=ops).json()
    names = [p["name"] for p in r["state"]["page_tree"]]
    assert "Start" in names and "Home page" not in names
    assert next(p for p in r["state"]["page_tree"] if p["name"] == "Start")["purpose"] == "Intro"


def test_az_unchanged_and_unknown_language_falls_back(client):
    s = client.post("/sessions", json={"consent": True, "language": "xx"}).json()
    assert "Korporativ sayt" in s["chips"]
