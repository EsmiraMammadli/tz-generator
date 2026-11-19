"""Admin səhifəsi: sessiyalar, açıq suallar, LLM provayder statistikası.

- `ADMIN_TOKEN` boşdursa bütün /admin yolları 404 qaytarır (səhifənin varlığı belə gizli qalır).
- API `Authorization: Bearer <token>` tələb edir; müqayisə sabit vaxtlıdır, uğursuz cəhdlər IP üzrə məhdudlaşdırılır.
- Səhifə (HTML/JS) özündə məlumat daşımır; məlumat yalnız düzgün token ilə API-dən gəlir.
- Burada müştərinin əlaqə məlumatları görünür: tokeni yalnız etibar etdiyiniz şəxslərə verin.
"""
from __future__ import annotations

import hmac
import logging
from collections import Counter
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import catalog, config, db, i18n, llm, notify, rules, tz_builder
from .db import FeedbackRow, MessageRow, SessionRow, TZVersionRow, utcnow
from .schemas import TZState
from .security import RateLimiter

log = logging.getLogger("tz.admin")
router = APIRouter(prefix="/admin")
_failures = RateLimiter(10)  # IP başına dəqiqədə ən çox 10 səhv token

SCAN_LIMIT = 500   # siyahı/statistika üçün ən son bu qədər sessiya hesablanır
MAX_PAGE = 100
NO_STORE = {"Cache-Control": "no-store"}


def _client(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if config.TRUST_PROXY and fwd:
        return fwd.split(",")[-1].strip()
    return request.client.host if request.client else "?"


def _not_found() -> HTTPException:
    return HTTPException(404, {"code": "not_found"})


def require_admin(request: Request) -> None:
    if not config.ADMIN_TOKEN:
        raise _not_found()
    auth = request.headers.get("authorization", "")
    given = auth[7:].strip() if auth.lower().startswith("bearer ") else ""
    if given and hmac.compare_digest(given.encode(), config.ADMIN_TOKEN.encode()):
        return
    ip = _client(request)
    if wait := _failures.check(ip):
        raise HTTPException(429, {"code": "rate_limited", "retry_after": int(wait)}, headers={"Retry-After": str(int(wait))})
    log.warning("admin_auth_failed", extra={"ctx": {"ip": ip}})
    raise HTTPException(401, {"code": "unauthorized"})


# ---------- köməkçilər ----------
def _iso(dt) -> str | None:
    return dt.isoformat() if dt else None


def _summary(row: SessionRow) -> tuple[TZState, dict]:
    state = TZState.model_validate(row.state)
    i18n.set_lang(state.language)  # hesablanmış mətnlər sessiyanın dilində
    return state, tz_builder.build_tz(state)


def _row_out(row: SessionRow, state: TZState, tz: dict, version: int | None) -> dict:
    b = tz.get("budget") or {}
    return {
        "id": row.id,
        "status": row.status,
        "language": row.language,
        "site_type": row.site_type,
        "project": tz["project_name"],
        "contact": rules.get(state, "contact_email") or "",
        "created_at": _iso(row.created_at),
        "updated_at": _iso(row.updated_at),
        "progress": tz["progress"],
        "ready": tz["ready"],
        "open_count": len(tz["clarifications"]),
        "version": version,
        "cost_min": b.get("cost_min"),
        "cost_max": b.get("cost_max"),
    }


def _versions(d: Session, ids: list[str]) -> dict[str, int]:
    if not ids:
        return {}
    q = select(TZVersionRow.session_id, func.max(TZVersionRow.version)).where(TZVersionRow.session_id.in_(ids)).group_by(TZVersionRow.session_id)
    return {sid: v for sid, v in d.execute(q).all()}


def _recent(d: Session, status: str = "all") -> list[SessionRow]:
    q = select(SessionRow).order_by(SessionRow.updated_at.desc()).limit(SCAN_LIMIT)
    if status in ("active", "confirmed"):
        q = q.where(SessionRow.status == status)
    return list(d.scalars(q).all())


# ---------- səhifə ----------
@router.get("", include_in_schema=False)
def page():
    """Boş HTML qabığı (məlumat daşımır). Token qurulmayıbsa səhifə də yoxdur."""
    if not config.ADMIN_TOKEN:
        raise _not_found()
    return FileResponse(config.ROOT / "static" / "admin.html", headers=NO_STORE)


# ---------- API ----------
@router.get("/api/overview", dependencies=[Depends(require_admin)])
def overview(d: Session = Depends(db.get_db)):
    total = d.scalar(select(func.count()).select_from(SessionRow)) or 0
    by_status = dict(d.execute(select(SessionRow.status, func.count()).group_by(SessionRow.status)).all())
    week = d.scalar(select(func.count()).select_from(SessionRow).where(SessionRow.created_at >= utcnow() - timedelta(days=7))) or 0
    rating = d.execute(select(func.avg(FeedbackRow.rating), func.count())).one()

    skipped, with_open = Counter(), 0
    rows = _recent(d)
    i18n.set_lang("az")
    for row in rows:
        state, tz = _summary(row)
        if tz["clarifications"]:
            with_open += 1
        skipped.update(state.skipped)
        skipped.update(f"page:{p.name}" for p in state.structure.pages if p.content_status == "open")
    i18n.set_lang("az")
    top = []
    for fid, n in skipped.most_common(8):
        f = catalog.field(fid) if not fid.startswith("page:") else None
        top.append({"id": fid, "label": (f or {}).get("label") or fid.replace("page:", "Səhifə məzmunu: "), "count": n})

    return {
        "sessions": {"total": total, "active": by_status.get("active", 0), "confirmed": by_status.get("confirmed", 0),
                     "last_7_days": week, "scanned": len(rows), "with_open_questions": with_open},
        "top_open": top,
        "feedback": {"count": rating[1], "avg": round(float(rating[0]), 2) if rating[0] is not None else None},
        "llm": {"mode": llm.llm_mode(), "models": list(config.LLM_MODELS), "prompt": config.PROMPT_VERSION,
                "stats": llm.STATS.snapshot(),
                "note": "Say prosesdaxilidir və serveri yenidən başlayanda sıfırlanır."},
        "system": {"db": db.backend(), "notify": notify.enabled(), "retention_days": config.RETENTION_DAYS},
    }


@router.get("/api/sessions", dependencies=[Depends(require_admin)])
def sessions(status: str = "all", open: int = 0, q: str = "", limit: int = 25, offset: int = 0,
             d: Session = Depends(db.get_db)):
    limit, offset = max(1, min(limit, MAX_PAGE)), max(0, offset)
    rows = _recent(d, status)
    vers = _versions(d, [r.id for r in rows])
    needle = q.strip().casefold()
    out = []
    for row in rows:
        state, tz = _summary(row)
        item = _row_out(row, state, tz, vers.get(row.id))
        if open and not item["open_count"]:
            continue
        if needle and needle not in f"{item['project']} {item['contact']} {item['id']}".casefold():
            continue
        out.append(item)
    return {"total": len(out), "items": out[offset:offset + limit], "scanned": len(rows), "limit": limit, "offset": offset}


@router.get("/api/sessions/{sid}", dependencies=[Depends(require_admin)])
def session_detail(sid: str, d: Session = Depends(db.get_db)):
    row = d.get(SessionRow, sid)
    if not row:
        raise HTTPException(404, {"code": "session_not_found"})
    state, tz = _summary(row)
    msgs = d.scalars(select(MessageRow).where(MessageRow.session_id == sid).order_by(MessageRow.id)).all()
    vers = d.scalars(select(TZVersionRow).where(TZVersionRow.session_id == sid).order_by(TZVersionRow.version)).all()
    fb = d.scalars(select(FeedbackRow).where(FeedbackRow.session_id == sid).order_by(FeedbackRow.id)).all()
    return {
        **_row_out(row, state, tz, vers[-1].version if vers else None),
        "clarifications": tz["clarifications"],
        "missing": tz["missing"],
        "sections": [{"title": s["title"], "items": [{"label": i["label"], "value": str(i["value"]), "source": i.get("source")}
                                                     for i in s["items"]]} for s in tz["sections"]],
        "files": tz["files"],
        "messages": [{"role": m.role, "content": m.content, "at": _iso(m.created_at)} for m in msgs],
        "versions": [{"version": v.version, "at": _iso(v.created_at)} for v in vers],
        "feedback": [{"rating": f.rating, "comment": f.comment, "at": _iso(f.created_at)} for f in fb],
    }


@router.get("/api/sessions/{sid}/download", dependencies=[Depends(require_admin)])
def session_download(sid: str, format: str = "docx", d: Session = Depends(db.get_db)):
    from . import main  # gec import: main bu router-i özü qoşur
    return main.download(sid, format, d)


@router.delete("/api/sessions/{sid}", dependencies=[Depends(require_admin)])
def session_delete(sid: str, d: Session = Depends(db.get_db)):
    from . import main
    log.info("admin_delete_session", extra={"ctx": {"sid": sid}})
    return main.delete_session(sid, d)
