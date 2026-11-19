"""Təsdiqlənmiş TZ bildirişi: e-poçt (SMTP, DOCX əlavə ilə) və/və ya Telegram.

Heç vaxt istisna atmır: bildiriş uğursuz olarsa müştərinin təsdiqi pozulmur, yalnız log yazılır.
Mətn agentliyin özü üçündür (Azərbaycan dilində); müştərinin TZ dili ayrıca qeyd olunur.
Telegram tokeni və SMTP parolu loglara düşmür.
"""
from __future__ import annotations

import logging
import re
import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path

import httpx

from . import config

log = logging.getLogger("tz.notify")

DOCX_MIME = ("application", "vnd.openxmlformats-officedocument.wordprocessingml.document")


def enabled() -> dict:
    return {"email": bool(config.NOTIFY_EMAIL and config.SMTP_HOST),
            "telegram": bool(config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_ID)}


def _one_line(s: str, limit: int = 120) -> str:
    """Müştərinin yazdığı mətn başlığa düşür: sətir keçidləri (header injection) və idarəedici simvollar atılır."""
    s = re.sub(r"[\x00-\x1f\x7f]+", " ", str(s)).strip()
    return s if len(s) <= limit else s[: limit - 1] + "…"


def _redact(text: str) -> str:
    for secret in (config.TELEGRAM_BOT_TOKEN, config.SMTP_PASSWORD):
        if secret:
            text = text.replace(secret, "***")
    return text


def _field(tz: dict, fid: str) -> str:
    for sec in tz.get("sections", []):
        for it in sec.get("items", []):
            if it.get("field_id") == fid:
                return str(it.get("value", ""))
    return ""


def build_text(tz: dict, sid: str) -> str:
    b = tz.get("budget", {})
    lines = [
        f"Yeni təsdiqlənmiş TZ: {_one_line(tz.get('project_name', ''), 200)}",
        f"Tarix: {tz.get('date', '')} · TZ dili: {str(tz.get('language', 'az')).upper()}",
        f"Sayt növü: {_field(tz, 'site_type') or '—'}",
        f"Əlaqə: {_field(tz, 'contact_email') or '—'}; {_field(tz, 'contact_details') or '—'}",
    ]
    if b.get("cost_min") is not None:
        lines.append(f"Təxmini büdcə: {int(b['cost_min'])}–{int(b['cost_max'])} AZN, "
                     f"{b['weeks_range'][0]}–{b['weeks_range'][1]} həftə")
    open_q = tz.get("clarifications") or []
    lines.append(f"Açıq suallar: {len(open_q)}" if open_q else "Açıq sual yoxdur")
    lines += [f"- {_one_line(q, 200)}" for q in open_q[:15]]
    if len(open_q) > 15:
        lines.append(f"… və daha {len(open_q) - 15} sual (sənədə baxın)")
    lines.append(f"Sessiya: {sid}")
    return "\n".join(lines)


def send_email(subject: str, text: str, attachment: tuple[str, bytes] | None = None) -> None:
    msg = EmailMessage()
    msg["Subject"] = _one_line(subject)
    msg["From"] = config.SMTP_FROM or config.SMTP_USER or config.NOTIFY_EMAIL
    msg["To"] = ", ".join(a.strip() for a in config.NOTIFY_EMAIL.split(",") if a.strip())
    msg.set_content(text)
    if attachment:
        name, data = attachment
        msg.add_attachment(data, maintype=DOCX_MIME[0], subtype=DOCX_MIME[1], filename=name)
    ctx = ssl.create_default_context()
    if config.SMTP_PORT == 465:
        smtp = smtplib.SMTP_SSL(config.SMTP_HOST, config.SMTP_PORT, timeout=15, context=ctx)
    else:
        smtp = smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=15)
    with smtp:
        if config.SMTP_PORT != 465 and config.SMTP_TLS:
            smtp.starttls(context=ctx)
        if config.SMTP_USER:
            smtp.login(config.SMTP_USER, config.SMTP_PASSWORD)
        smtp.send_message(msg)


def send_telegram(text: str, attachment: tuple[str, bytes] | None = None) -> None:
    base = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}"
    r = httpx.post(f"{base}/sendMessage", data={"chat_id": config.TELEGRAM_CHAT_ID, "text": text[:4096]}, timeout=20)
    r.raise_for_status()
    if attachment:
        name, data = attachment
        r = httpx.post(f"{base}/sendDocument", data={"chat_id": config.TELEGRAM_CHAT_ID},
                       files={"document": (name, data, "/".join(DOCX_MIME))}, timeout=30)
        r.raise_for_status()


def notify_confirmed(tz: dict, docx_path: Path | str | None, sid: str) -> dict:
    """Hər kanal ayrıca yoxlanılır: biri çökərsə digəri yenə göndərilir. Nəticə: off | ok | failed."""
    on = enabled()
    out = {"email": "off", "telegram": "off"}
    if not (on["email"] or on["telegram"]):
        return out
    attachment = None
    try:
        p = Path(docx_path) if docx_path else None
        if p and p.is_file():
            attachment = (f"Texniki_Tapsiriq_{sid[:8]}.docx", p.read_bytes())
    except OSError:
        log.warning("notify_attachment_unreadable")
    try:
        text = build_text(tz, sid)
    except Exception:  # noqa: BLE001 - mətn qurula bilmirsə də ən azı qısa bildiriş getsin
        text = f"Yeni təsdiqlənmiş TZ. Sessiya: {sid}"
    subject = f"Yeni TZ: {tz.get('project_name', '')}"
    for channel, send in (("email", lambda: send_email(subject, text, attachment)),
                          ("telegram", lambda: send_telegram(text, attachment))):
        if not on[channel]:
            continue
        try:
            send()
            out[channel] = "ok"
        except Exception as e:  # noqa: BLE001 - heç vaxt təsdiqi pozmasın
            out[channel] = "failed"
            log.error("notify_failed", extra={"ctx": {"channel": channel, "sid": sid,
                                                      "error": f"{type(e).__name__}: {_redact(str(e))[:200]}"}})
    log.info("notify_done", extra={"ctx": {"sid": sid, **out}})
    return out
