"""Yüklənən fayllar: yoxlama (magic bytes), limitlər, diskdə saxlama və state ilə sinxron.

Qəsdən qəbul olunmur: SVG/HTML (XSS riski). Loqo və nümunələr PNG/JPG, brend bələdçisi PDF ola bilər."""
from __future__ import annotations

import base64
import binascii
import io
import zipfile
from dataclasses import dataclass
from pathlib import Path

from . import config, i18n, rules
from .schemas import FileIn, FileMeta, TZState

MAGIC = {b"\x89PNG\r\n\x1a\n": "png", b"\xff\xd8\xff": "jpg", b"%PDF-": "pdf"}
MIME = {"png": "image/png", "jpg": "image/jpeg", "pdf": "application/pdf"}
ALLOWED = {"logo": {"png", "jpg"}, "guide": {"pdf"}, "reference": {"png", "jpg"}}
KIND_LIMIT = {"logo": 6, "guide": 2, "reference": 8}
MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_TOTAL_BYTES = 20 * 1024 * 1024
MAX_FILES = 15


class FileError(Exception):
    def __init__(self, status: int, code: str, **extra):
        super().__init__(code)
        self.status, self.code, self.extra = status, code, extra


@dataclass
class Checked:
    raw: bytes
    ext: str
    name: str
    kind: str


def safe_name(filename: str, ext: str) -> str:
    return "".join(ch for ch in Path(filename).name if ch.isprintable())[:80] or f"file.{ext}"


def check(item: FileIn) -> Checked:
    try:
        raw = base64.b64decode(item.data, validate=True)
    except (binascii.Error, ValueError):
        raise FileError(400, "bad_file")
    if len(raw) > MAX_FILE_BYTES:
        raise FileError(413, "file_too_large")
    ext = next((e for m, e in MAGIC.items() if raw.startswith(m)), None)
    if not ext or ext not in ALLOWED[item.kind]:
        raise FileError(415, "unsupported_type", kind=item.kind)
    return Checked(raw, ext, safe_name(item.filename, ext), item.kind)


def folder(sid: str) -> Path:
    return config.FILES_DIR / sid / "uploads"


def path_of(sid: str, meta: FileMeta) -> Path:
    return folder(sid) / f"{meta.id}.{meta.ext}"


def of_kind(state: TZState, kind: str) -> list[FileMeta]:
    return [f for f in state.files if f.kind == kind]


def add_files(state: TZState, sid: str, items: list[FileIn]) -> list[FileMeta]:
    """Hamısı ya qəbul olunur, ya heç biri (yarımçıq yükləmə qalmasın). State-i və sahələri yeniləyir."""
    checked = [check(i) for i in items]
    if len(state.files) + len(checked) > MAX_FILES:
        raise FileError(409, "too_many_files", limit=MAX_FILES)
    for kind, limit in KIND_LIMIT.items():
        if len(of_kind(state, kind)) + sum(1 for c in checked if c.kind == kind) > limit:
            raise FileError(409, "too_many_files", kind=kind, limit=limit)
    if sum(f.size for f in state.files) + sum(len(c.raw) for c in checked) > MAX_TOTAL_BYTES:
        raise FileError(413, "total_too_large")
    out = []
    folder(sid).mkdir(parents=True, exist_ok=True)
    for c in checked:
        meta = FileMeta(kind=c.kind, filename=c.name, ext=c.ext, size=len(c.raw))
        path_of(sid, meta).write_bytes(c.raw)
        state.files.append(meta)
        out.append(meta)
    sync_fields(state)
    return out


def remove_file(state: TZState, sid: str, fid: str) -> FileMeta | None:
    meta = next((f for f in state.files if f.id == fid), None)
    if not meta:
        return None
    state.files.remove(meta)
    path_of(sid, meta).unlink(missing_ok=True)
    sync_fields(state)
    return meta


def sync_fields(state: TZState) -> None:
    """brand_logo / reference_screenshots sahələri fayl siyahısından törəyir. Hamısı silinibsə sahə «açıq sual» olur (dəyər uydurulmur)."""
    logos = of_kind(state, "logo")
    if logos:
        rules.set_field(state, "brand_logo", i18n.t("logo_saved", name=", ".join(f.filename for f in logos)), "user")
    elif "brand_logo" in state.fields:
        rules.mark_open(state, "brand_logo")
    refs = of_kind(state, "reference")
    if refs:
        rules.set_field(state, "reference_screenshots",
                        i18n.t("refs_value", n=len(refs), names=", ".join(f.filename for f in refs)), "user")
    elif "reference_screenshots" in state.fields and state.fields["reference_screenshots"].source == "user" \
            and not _is_default(state):
        rules.mark_open(state, "reference_screenshots")


def _is_default(state: TZState) -> bool:
    from . import catalog
    f = catalog.field("reference_screenshots") or {}
    return state.fields["reference_screenshots"].value == f.get("default")


def assets_zip(state: TZState, sid: str) -> bytes:
    """Bütün yüklənmiş fayllar bir arxivdə (developer üçün). Ad toqquşmasında nömrə əlavə olunur."""
    buf = io.BytesIO()
    used: set[str] = set()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for f in state.files:
            p = path_of(sid, f)
            if not p.exists():  # hostinqdə disk sıfırlanıbsa
                continue
            name, n = f"{f.kind}/{f.filename}", 1
            while name in used:
                n += 1
                stem, dot, ext = f.filename.rpartition(".")
                name = f"{f.kind}/{stem or f.filename}_{n}{dot}{ext}"
            used.add(name)
            z.write(p, name)
    return buf.getvalue()
