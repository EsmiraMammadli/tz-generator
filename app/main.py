"""FastAPI tətbiqi: API müqaviləsi (kontekst Bölmə 5) + statik UI."""
from __future__ import annotations

import logging
import shutil
import time
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from . import admin, config, db, docgen, engine, files, i18n, llm, notify, rules, tz_builder
from .db import FeedbackRow, MessageRow, SessionRow, TZVersionRow
from .schemas import AnswersIn, CreateSessionIn, FeedbackIn, FileIn, FilesIn, LogoIn, MessageIn, PageOpIn, TurnResult, TZState
from .security import RateLimiter, setup_logging

log = logging.getLogger("tz.api")
limiter = RateLimiter(config.RATE_LIMIT_PER_MIN)
extractor = llm.get_extractor()


@asynccontextmanager
async def lifespan(_: FastAPI):
    setup_logging()
    db.init_db()
    with db._Session() as s:
        purged = db.purge_stale(s)
    if config.ADMIN_TOKEN and len(config.ADMIN_TOKEN) < 16:
        log.warning("admin_token_too_short", extra={"ctx": {"min_length": 16}})
    log.info("startup", extra={"ctx": {"llm_mode": llm.llm_mode(), "db": db.backend(), "purged_sessions": purged}})
    yield


app = FastAPI(title="AI TZ Generatoru", lifespan=lifespan)

CSP = ("default-src 'self'; script-src 'self'; "
       "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdnjs.cloudflare.com; "
       "font-src https://fonts.gstatic.com https://cdnjs.cloudflare.com; img-src 'self' data:; "
       "connect-src 'self'; frame-ancestors 'none'")


@app.middleware("http")
async def security_headers(request: Request, call_next):
    resp = await call_next(request)
    resp.headers.setdefault("Content-Security-Policy", CSP)
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("Referrer-Policy", "no-referrer")
    return resp


# ---------- köməkçilər ----------
def err(status: int, code: str, **extra) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, **extra})


def client_key(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if config.TRUST_PROXY and fwd:  # proxy öz gördüyü IP-ni siyahının SONUNA əlavə edir; soldakılar saxtalaşdırıla bilər
        return fwd.split(",")[-1].strip()
    return request.client.host if request.client else "?"


def get_row(sid: str, d: Session) -> SessionRow:
    row = d.get(SessionRow, sid)
    if not row:
        raise err(404, "session_not_found")
    return row


def load(row: SessionRow) -> TZState:
    state = TZState.model_validate(row.state)
    i18n.set_lang(state.language)  # bu sorğunun bütün mətnləri sessiyanın dilində olsun
    return state


def save(d: Session, row: SessionRow, state: TZState) -> None:
    row.state = state.model_dump(mode="json")
    opt = rules.option_value(state, "site_type")
    row.site_type = opt if isinstance(opt, str) else None
    d.add(row)
    d.commit()


def add_msg(d: Session, sid: str, role: str, content: str, **meta) -> None:
    d.add(MessageRow(session_id=sid, role=role, content=content, meta=meta))


def response(state: TZState, res: TurnResult) -> dict:
    return {**res.model_dump(), "state": tz_builder.ui_state(state)}


# ---------- endpoint-lər ----------
@app.post("/sessions")
def create_session(body: CreateSessionIn, request: Request, d: Session = Depends(db.get_db)):
    if not body.consent:
        raise err(400, "consent_required")
    if wait := limiter.check("new:" + client_key(request)):
        raise HTTPException(429, {"code": "rate_limited", "retry_after": int(wait)}, headers={"Retry-After": str(int(wait))})
    state = TZState(language=body.language if body.language in i18n.LANGS else "az")
    res = engine.start(state)
    row = SessionRow(language=state.language, state={})
    d.add(row)
    d.flush()
    add_msg(d, row.id, "ai", res.reply, chips=res.chips, show_tree=res.show_tree, widget=res.widget, why=res.why)
    save(d, row, state)
    return {"session_id": row.id, **response(state, res)}


@app.post("/sessions/{sid}/messages")
def post_message(sid: str, body: MessageIn, request: Request, d: Session = Depends(db.get_db)):
    row = get_row(sid, d)
    if row.status != "active":
        raise err(409, "session_confirmed")
    for key in (f"ip:{client_key(request)}", f"sid:{sid}"):
        if wait := limiter.check(key):
            raise HTTPException(429, {"code": "rate_limited", "retry_after": int(wait)}, headers={"Retry-After": str(int(wait))})
    state = load(row)
    t0 = time.monotonic()
    llm.take_run()  # əvvəlki sorğunun izi qalmasın
    try:
        res = engine.process_turn(state, body.text.strip(), extractor)
    except llm.LLMUnavailable:
        log.error("llm_unavailable", extra={"ctx": {"sid": sid, "llm_run": llm.take_run()}})
        raise err(503, "llm_unavailable")
    add_msg(d, sid, "user", body.text.strip())
    add_msg(d, sid, "ai", res.reply, chips=res.chips, show_tree=res.show_tree, widget=res.widget, why=res.why)
    save(d, row, state)
    ctx = {"sid": sid, "slot": state.pending_slot, "turn": state.turns,
           "ms": int((time.monotonic() - t0) * 1000), "mode": llm.llm_mode()}
    run = llm.take_run()  # LLM çağırılıbsa: model sırası, hər cəhdin nəticəsi və cavab verən model
    if run:
        ctx.update(llm_order=run["order"], llm_tried=run["tried"], answered_by=run["answered_by"])
    log.info("turn", extra={"ctx": ctx})
    return response(state, res)


@app.get("/sessions/{sid}/state")
def get_state(sid: str, d: Session = Depends(db.get_db)):
    row = get_row(sid, d)
    state = load(row)
    msgs = d.scalars(select(MessageRow).where(MessageRow.session_id == sid).order_by(MessageRow.id)).all()
    return {
        "session_id": sid, "status": row.status, "language": state.language, "state": tz_builder.ui_state(state),
        "messages": [{"role": m.role, "content": m.content, "chips": m.meta.get("chips", []),
                      "show_tree": m.meta.get("show_tree", False), "widget": m.meta.get("widget"),
                      "why": m.meta.get("why", ""),
                      "time": m.created_at.strftime("%H:%M")} for m in msgs],
    }


@app.get("/sessions/{sid}/summary")
def get_summary(sid: str, d: Session = Depends(db.get_db)):
    return tz_builder.build_tz(load(get_row(sid, d)))


@app.post("/sessions/{sid}/page-ops")
def page_ops(sid: str, body: PageOpIn, d: Session = Depends(db.get_db)):
    """Səhifə ağacı düymələri (əlavə/sil/dəyiş). Kontekstdəki müqaviləyə əlavədir."""
    row = get_row(sid, d)
    if row.status != "active":
        raise err(409, "session_confirmed")
    state = load(row)
    notes = engine.apply_page_ops(state, body.ops)
    res = engine.after_edit(state, notes)
    add_msg(d, sid, "ai", res.reply, chips=res.chips, show_tree=res.show_tree, widget=res.widget, why=res.why)
    save(d, row, state)
    return response(state, res)


@app.post("/sessions/{sid}/answers")
def edit_answers(sid: str, body: AnswersIn, d: Session = Depends(db.get_db)):
    """Xülasə ekranından cavabları söhbətə qayıtmadan düzəltmək. Hər dəyər söhbətdəki kimi yoxlanılır;
    etibarsız dəyər yazılmır və `rejected`-də qaytarılır."""
    row = get_row(sid, d)
    if row.status != "active":
        raise err(409, "session_confirmed")
    if not (body.fields or body.page_content or body.open):
        raise err(422, "nothing_to_update")
    state = load(row)
    notes, rejected, dropped = engine.apply_answers(state, body.fields, body.page_content, body.open)
    if not notes and rejected:  # heç nə qəbul olunmayıb: dəyişiklik yoxdur
        raise err(422, "invalid_value", rejected=rejected)
    res = engine.after_answers(state, notes, dropped)
    if res:
        add_msg(d, sid, "ai", res.reply, chips=res.chips, show_tree=res.show_tree, widget=res.widget, why=res.why)
    save(d, row, state)
    return {"status": "ok", "updated": notes, "rejected": rejected, "dropped": dropped,
            "needs_chat": res is not None, "pending_slot": state.pending_slot,
            "summary": tz_builder.build_tz(state), "state": tz_builder.ui_state(state)}


def _upload_limit(request: Request) -> None:
    if wait := limiter.check(f"files:{client_key(request)}"):
        raise HTTPException(429, {"code": "rate_limited", "retry_after": int(wait)}, headers={"Retry-After": str(int(wait))})


def _file_error(e: files.FileError) -> HTTPException:
    return err(e.status, e.code, **e.extra)


def _meta_out(m) -> dict:
    return {"id": m.id, "kind": m.kind, "filename": m.filename, "ext": m.ext, "size": m.size}


def _store(sid: str, items: list[FileIn], d: Session, request: Request) -> dict:
    row = get_row(sid, d)
    if row.status != "active":
        raise err(409, "session_confirmed")
    _upload_limit(request)
    state = load(row)
    try:
        added = files.add_files(state, sid, items)
    except files.FileError as e:
        raise _file_error(e)
    res = engine.after_files(state, [m.filename for m in added])  # təsdiq + növbəti sual
    add_msg(d, sid, "ai", res.reply, chips=res.chips, show_tree=res.show_tree, widget=res.widget, why=res.why)
    save(d, row, state)
    return {"status": "ok", "filename": added[0].filename, "files": [_meta_out(m) for m in added], **response(state, res)}


@app.post("/sessions/{sid}/files")
def upload_files(sid: str, body: FilesIn, request: Request, d: Session = Depends(db.get_db)):
    """Bir neçə fayl (loqo variantları, brend bələdçisi PDF, dizayn skrinşotları). Hamısı ya qəbul olunur, ya heç biri."""
    return _store(sid, body.files, d, request)


@app.post("/sessions/{sid}/logo")
def upload_logo(sid: str, body: LogoIn, request: Request, d: Session = Depends(db.get_db)):
    """Köhnə müqavilə: tək loqo. Yeni kod /files istifadə edir."""
    return _store(sid, [FileIn(filename=body.filename, data=body.data, kind="logo")], d, request)


@app.get("/sessions/{sid}/files")
def list_files(sid: str, d: Session = Depends(db.get_db)):
    state = load(get_row(sid, d))
    return {"files": [_meta_out(m) for m in state.files]}


def _serve(sid: str, meta) -> FileResponse:
    p = files.path_of(sid, meta)
    if not p.exists():  # hostinqdə disk sıfırlanıb
        raise err(404, "file_not_found")
    headers = {"Content-Disposition": 'attachment; filename="file.pdf"'} if meta.ext == "pdf" else None
    return FileResponse(p, media_type=files.MIME[meta.ext], headers=headers)


@app.get("/sessions/{sid}/files/{fid}")
def get_file(sid: str, fid: str, d: Session = Depends(db.get_db)):
    state = load(get_row(sid, d))
    meta = next((m for m in state.files if m.id == fid), None)
    if not meta:
        raise err(404, "file_not_found")
    return _serve(sid, meta)


@app.delete("/sessions/{sid}/files/{fid}")
def delete_file(sid: str, fid: str, d: Session = Depends(db.get_db)):
    row = get_row(sid, d)
    if row.status != "active":
        raise err(409, "session_confirmed")
    state = load(row)
    if not files.remove_file(state, sid, fid):
        raise err(404, "file_not_found")
    save(d, row, state)
    return {"status": "ok", "files": [_meta_out(m) for m in state.files], "state": tz_builder.ui_state(state)}


@app.get("/sessions/{sid}/logo")
def get_logo(sid: str, d: Session = Depends(db.get_db)):
    """Köhnə müqavilə: ilk loqo. Köhnə sessiyalarda faylın adı logo.* idi."""
    state = load(get_row(sid, d))
    meta = next((m for m in state.files if m.kind == "logo"), None)
    if meta:
        return _serve(sid, meta)
    legacy = next(iter((config.FILES_DIR / sid).glob("logo.*")), None) if (config.FILES_DIR / sid).exists() else None
    if not legacy:
        raise err(404, "logo_not_found")
    return FileResponse(legacy, media_type=files.MIME.get(legacy.suffix.lstrip("."), "application/octet-stream"))


@app.post("/sessions/{sid}/confirm")
def confirm(sid: str, background: BackgroundTasks, d: Session = Depends(db.get_db)):
    row = get_row(sid, d)
    if row.status == "confirmed":  # təkrar təsdiq yeni versiya yaratmır
        last = d.scalars(select(TZVersionRow).where(TZVersionRow.session_id == sid)
                         .order_by(TZVersionRow.version.desc())).first()
        if last:
            return {"status": "ready", "version": last.version, "summary": last.json_snapshot}
    state = load(row)
    tz = tz_builder.build_tz(state)
    if not tz["ready"]:
        raise err(409, "not_ready", missing=tz["missing"])
    version = (d.scalar(select(func.max(TZVersionRow.version)).where(TZVersionRow.session_id == sid)) or 0) + 1
    path = config.FILES_DIR / sid / f"tz_v{version}.docx"
    docgen.build_docx(tz, path, files.folder(sid))
    d.add(TZVersionRow(session_id=sid, version=version, json_snapshot=tz, file_path=str(path)))
    row.status = "confirmed"
    save(d, row, state)
    background.add_task(notify.notify_confirmed, tz, path, sid)  # cavabdan sonra; uğursuzluq təsdiqi pozmur
    return {"status": "ready", "version": version, "summary": tz}


@app.get("/sessions/{sid}/download")
def download(sid: str, format: str = "docx", d: Session = Depends(db.get_db)):
    row = get_row(sid, d)
    ver = d.scalars(select(TZVersionRow).where(TZVersionRow.session_id == sid)
                    .order_by(TZVersionRow.version.desc())).first()
    if row.status != "confirmed" or not ver:
        raise err(409, "not_confirmed")
    name = f"Texniki_Tapsiriq_v{ver.version}"
    if format == "docx":
        if not ver.file_path or not Path(ver.file_path).exists():  # hostinqdə disk sıfırlanıbsa snapshot-dan bərpa et
            docgen.build_docx(ver.json_snapshot, Path(ver.file_path or config.FILES_DIR / sid / f"tz_v{ver.version}.docx"),
                              files.folder(sid))
        return FileResponse(ver.file_path, filename=f"{name}.docx",
                            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    if format == "pdf":
        pdf = config.FILES_DIR / sid / f"tz_v{ver.version}.pdf"
        if not pdf.exists():
            try:
                docgen.build_pdf(ver.json_snapshot, pdf, files.folder(sid))
            except Exception:  # noqa: BLE001 - WeasyPrint sistem kitabxanası yoxdursa
                log.exception("pdf_failed")
                raise err(501, "pdf_unavailable")
        return FileResponse(pdf, filename=f"{name}.pdf", media_type="application/pdf")
    if format == "assets":  # yüklənmiş bütün fayllar (loqolar, brend bələdçisi, skrinşotlar) bir arxivdə
        data = files.assets_zip(load(row), sid)
        return Response(data, media_type="application/zip",
                        headers={"Content-Disposition": f'attachment; filename="{name}_files.zip"'})
    raise err(400, "bad_format")


@app.delete("/sessions/{sid}")
def delete_session(sid: str, d: Session = Depends(db.get_db)):
    row = get_row(sid, d)
    d.query(MessageRow).filter_by(session_id=sid).delete()
    d.query(TZVersionRow).filter_by(session_id=sid).delete()
    d.delete(row)
    d.commit()
    shutil.rmtree(config.FILES_DIR / sid, ignore_errors=True)
    return {"success": True}


@app.post("/sessions/{sid}/feedback")
def feedback(sid: str, body: FeedbackIn, d: Session = Depends(db.get_db)):
    get_row(sid, d)
    d.add(FeedbackRow(session_id=sid, rating=body.rating, comment=body.comment.strip()))
    d.commit()
    return {"status": "received"}


@app.get("/health")
def health(deep: bool = False, d: Session = Depends(db.get_db)):
    """Standart ping yalnız DB-ni yoxlayır (LLM kvotasını yemir). ?deep=1 real LLM çağırışı edir."""
    out = {"db": "ok", "llm_mode": llm.llm_mode(), "llm": "not_checked"}
    try:
        d.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001
        out["db"] = "error"
    if deep and llm.llm_mode() == "litellm":
        try:
            getattr(extractor, "primary", extractor).extract(llm.Ctx(TZState(), "salam", "field:site_type", "Sayt növü?"))
            out["llm"] = "ok"
        except llm.LLMUnavailable:
            out["llm"] = "error"
    elif llm.llm_mode() == "heuristic":
        out["llm"] = "heuristic"
    code = 200 if out["db"] == "ok" and out["llm"] != "error" else 503
    return JSONResponse(out, status_code=code)


@app.exception_handler(HTTPException)
async def http_exc(_: Request, exc: HTTPException):
    detail = exc.detail if isinstance(exc.detail, dict) else {"code": "error", "message": str(exc.detail)}
    return JSONResponse({"detail": detail}, status_code=exc.status_code, headers=getattr(exc, "headers", None))


app.include_router(admin.router)
app.mount("/static", StaticFiles(directory=config.ROOT / "static"), name="static")


@app.get("/")
def index():
    return FileResponse(config.ROOT / "static" / "index.html")
