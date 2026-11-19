import logging

import httpx

from app import config, notify

from tests.test_api import client, finish_chat, start  # noqa: F401


class FakeSMTP:
    sent: list = []
    fail = False

    def __init__(self, host, port, timeout=None, context=None):
        self.host, self.port = host, port

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def starttls(self, context=None):
        self.tls = True

    def login(self, user, pw):
        self.creds = (user, pw)

    def send_message(self, msg):
        if FakeSMTP.fail:
            raise OSError("smtp down, password=" + config.SMTP_PASSWORD)
        FakeSMTP.sent.append(msg)


def _configure(monkeypatch, email=True, telegram=True):
    FakeSMTP.sent, FakeSMTP.fail = [], False
    monkeypatch.setattr(notify.smtplib, "SMTP", FakeSMTP)
    monkeypatch.setattr(config, "NOTIFY_EMAIL", "dev@agency.az, boss@agency.az" if email else "")
    monkeypatch.setattr(config, "SMTP_HOST", "smtp.example.com" if email else "")
    monkeypatch.setattr(config, "SMTP_USER", "bot@agency.az")
    monkeypatch.setattr(config, "SMTP_PASSWORD", "s3cret-pass")
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "123:TOKEN-XYZ" if telegram else "")
    monkeypatch.setattr(config, "TELEGRAM_CHAT_ID", "555" if telegram else "")
    calls = []

    def fake_post(url, data=None, files=None, timeout=None):
        calls.append((url, data, files))
        return httpx.Response(200, request=httpx.Request("POST", url))

    monkeypatch.setattr(notify.httpx, "post", fake_post)
    return calls


def test_disabled_by_default_sends_nothing(client, monkeypatch):
    calls = _configure(monkeypatch, email=False, telegram=False)
    sid = start(client)["session_id"]
    finish_chat(client, sid)
    assert client.post(f"/sessions/{sid}/confirm").status_code == 200
    assert not FakeSMTP.sent and not calls
    assert notify.enabled() == {"email": False, "telegram": False}


def test_confirm_sends_email_with_docx_and_telegram(client, monkeypatch):
    calls = _configure(monkeypatch)
    sid = start(client)["session_id"]
    finish_chat(client, sid)
    assert client.post(f"/sessions/{sid}/confirm").status_code == 200
    assert len(FakeSMTP.sent) == 1
    msg = FakeSMTP.sent[0]
    assert "Atlas Logistika" in msg["Subject"] and msg["To"] == "dev@agency.az, boss@agency.az"
    names = [p.get_filename() for p in msg.iter_attachments()]
    assert names and names[0].endswith(".docx")
    body = msg.get_body().get_content()
    assert "Atlas Logistika" in body and "Təxmini büdcə" in body
    urls = [c[0] for c in calls]
    assert urls[0].endswith("/sendMessage") and urls[1].endswith("/sendDocument")
    assert calls[0][1]["chat_id"] == "555" and calls[1][2]["document"][0].endswith(".docx")


def test_repeated_confirm_does_not_resend(client, monkeypatch):
    calls = _configure(monkeypatch)
    sid = start(client)["session_id"]
    finish_chat(client, sid)
    client.post(f"/sessions/{sid}/confirm")
    client.post(f"/sessions/{sid}/confirm")
    assert len(FakeSMTP.sent) == 1 and len(calls) == 2


def test_failure_never_breaks_confirm_and_other_channel_still_sends(client, monkeypatch, caplog):
    calls = _configure(monkeypatch)
    FakeSMTP.fail = True
    sid = start(client)["session_id"]
    finish_chat(client, sid)
    with caplog.at_level(logging.INFO):
        r = client.post(f"/sessions/{sid}/confirm")
    assert r.status_code == 200 and r.json()["status"] == "ready"
    assert len(calls) == 2  # Telegram yenə göndərildi
    assert "s3cret-pass" not in caplog.text  # parol loga düşmür
    assert client.get(f"/sessions/{sid}/download?format=docx").status_code == 200


def test_telegram_token_redacted_from_error_log(client, monkeypatch, caplog):
    _configure(monkeypatch, email=False)

    def boom(url, **kw):
        raise httpx.ConnectError(f"cannot reach {url}")

    monkeypatch.setattr(notify.httpx, "post", boom)
    sid = start(client)["session_id"]
    finish_chat(client, sid)
    with caplog.at_level(logging.INFO):
        assert client.post(f"/sessions/{sid}/confirm").status_code == 200
    assert "TOKEN-XYZ" not in caplog.text and "notify_failed" in caplog.text


def test_subject_header_injection_is_neutralised():
    assert "\n" not in notify._one_line("Ad\r\nBcc: attacker@evil.com")
    assert len(notify._one_line("x" * 500)) <= 120


def test_open_questions_listed_in_message(client, monkeypatch):
    _configure(monkeypatch)
    sid = start(client)["session_id"]
    finish_chat(client, sid)
    client.post(f"/sessions/{sid}/answers", json={"open": ["competitors"]})
    client.post(f"/sessions/{sid}/confirm")
    body = FakeSMTP.sent[0].get_body().get_content()
    assert "Açıq suallar" in body and "Rəqib" in body
