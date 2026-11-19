"""TZ JSON snapshot-dan DOCX (python-docx) və PDF (WeasyPrint) yaradır. Dil snapshot-dakı `language` sahəsindən gəlir."""
from __future__ import annotations

import base64
import html
import logging
from pathlib import Path

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

from . import config
from .i18n import t

log = logging.getLogger("tz.docgen")
MAX_LOGOS_IN_DOC, MAX_REFS_IN_DOC = 3, 6
SRC_KEYS = {"inferred": "est_tag", "calculated": "est_tag", "open": "open_tag"}


def _lang(tz: dict) -> str:
    return tz.get("language", "az")


def _fmt(item: dict, lang: str) -> str:
    tag = t(SRC_KEYS[item["source"]], lang) if item["source"] in SRC_KEYS else ""
    return f"{item['value']}{tag}"


def _is_req(it: dict) -> bool:
    return bool(it.get("req"))


def _contrast(hex_color: str) -> str:
    """Rəng nümunəsinin üstündəki yazı üçün ağ/qara (parlaqlığa görə)."""
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return "000000" if (0.299 * r + 0.587 * g + 0.114 * b) > 150 else "FFFFFF"


def _shade(cell, hex_color: str) -> None:
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_color.lstrip("#"))
    tcPr.append(shd)


def _swatch_table(cell, colors: list[str]) -> None:
    """Xananın içində rənglə doldurulmuş kiçik xanalar: hər birində HEX kodu."""
    tb = cell.add_table(rows=1, cols=len(colors))
    for i, c in enumerate(colors):
        cc = tb.rows[0].cells[i]
        _shade(cc, c)
        cc.text = ""
        run = cc.paragraphs[0].add_run(c)
        run.font.size = Pt(9)
        run.font.color.rgb = RGBColor.from_string(_contrast(c))


def _existing_files(tz: dict, files_dir: Path | None, kind: str, limit: int) -> list[tuple[dict, Path]]:
    out = []
    for f in tz.get("files", []):
        if f.get("kind") != kind or f.get("ext") not in ("png", "jpg") or not files_dir:
            continue
        p = files_dir / f"{f['id']}.{f['ext']}"
        if p.exists():  # hostinqdə disk sıfırlanıbsa sənəd şəkilsiz yaradılır, səhv vermir
            out.append((f, p))
    return out[:limit]


def _set_cell_text(cell, text: str, *, size=11, bold=False, color=None, align=None) -> None:
    cell.text = ""
    run = cell.paragraphs[0].add_run(text)
    run.font.size = Pt(size)
    run.bold = bold
    if color:
        run.font.color.rgb = RGBColor.from_string(color)
    if align:
        cell.paragraphs[0].alignment = align


def _agency_banner(doc, L: str) -> None:
    """Sənədin öz başlığı: agentlik adı, loqo (varsa) və rəngli zolaq."""
    name, tag, color = config.AGENCY_NAME, config.AGENCY_TAGLINE, config.AGENCY_COLOR
    table = doc.add_table(rows=1, cols=2 if config.AGENCY_LOGO_PATH else 1)
    table.autofit = True
    cells = table.rows[0].cells
    if config.AGENCY_LOGO_PATH:
        try:
            cells[0].paragraphs[0].add_run().add_picture(str(config.AGENCY_LOGO_PATH), height=Cm(1.4))
        except Exception:  # noqa: BLE001
            log.warning("agency_logo_failed")
        _set_cell_text(cells[1], name + (f"\n{tag}" if tag else ""), size=14, bold=True, color=color)
    else:
        _set_cell_text(cells[0], name + (f"\n{tag}" if tag else ""), size=14, bold=True, color=color)
    for cell in cells:
        _shade(cell, color)
        for p in cell.paragraphs:
            for run in p.runs:
                run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
    doc.add_paragraph()


def _open_questions_docx(doc, tz: dict, L: str) -> None:
    doc.add_heading(t("doc_open_head", L), level=1)
    items = tz.get("clarifications") or []
    if not items:
        doc.add_paragraph(t("doc_open_none", L))
        return
    for c in items:
        doc.add_paragraph(c, style="List Bullet")


def _docx_attachments(doc, tz: dict, files_dir: Path | None, L: str) -> None:
    logos = _existing_files(tz, files_dir, "logo", MAX_LOGOS_IN_DOC)
    refs = _existing_files(tz, files_dir, "reference", MAX_REFS_IN_DOC)
    if not (logos or refs):
        return
    doc.add_heading(t("doc_attachments", L), level=2)
    for f, p in logos:
        try:
            doc.add_picture(str(p), height=Cm(2.2))
            doc.add_paragraph(f["filename"]).runs[0].font.size = Pt(9)
        except Exception:  # noqa: BLE001 - zədəli şəkil sənədi pozmasın
            log.warning("docx_picture_failed", extra={"ctx": {"file": f["id"]}})
    for f, p in refs:
        try:
            doc.add_picture(str(p), width=Cm(8))
            doc.add_paragraph(f["filename"]).runs[0].font.size = Pt(9)
        except Exception:  # noqa: BLE001
            log.warning("docx_picture_failed", extra={"ctx": {"file": f["id"]}})


def build_docx(tz: dict, path: Path, files_dir: Path | None = None) -> Path:
    L = _lang(tz)
    doc = Document()
    doc.styles["Normal"].font.name = "Calibri"
    doc.styles["Normal"].font.size = Pt(11)
    _agency_banner(doc, L)
    doc.add_heading(t("doc_title", L), 0)
    p = doc.add_paragraph()
    p.add_run(f"{t('doc_project', L)}: {tz['project_name']}\n{t('doc_date', L)}: {tz['date']}").font.color.rgb = RGBColor(0x55, 0x65, 0x7A)
    _open_questions_docx(doc, tz, L)

    for s in tz["sections"]:
        doc.add_heading(s["title"], level=1)
        if not s["items"]:
            doc.add_paragraph(t("doc_no_data", L))
            continue
        if s["number"] in (5, 6, 7):  # uzun tələb siyahıları
            for it in s["items"]:
                doc.add_paragraph(_fmt(it, L) if _is_req(it) else f"{it['label']}: {_fmt(it, L)}", style="List Bullet")
        else:
            table = doc.add_table(rows=0, cols=2)
            table.style = "Light Grid Accent 1"
            for it in s["items"]:
                row = table.add_row().cells
                row[0].text, row[1].text = it["label"], _fmt(it, L)
                if it.get("swatches"):
                    _swatch_table(row[1], it["swatches"])
        if s["number"] == 4:
            _docx_attachments(doc, tz, files_dir, L)

    b = tz["budget"]
    doc.add_heading(t("doc_annex", L), level=1)
    tb = doc.add_table(rows=1, cols=3)
    tb.style = "Light Grid Accent 1"
    for i, h in enumerate([t("doc_th_page", L), t("doc_th_module", L), t("doc_th_hours", L)]):
        tb.rows[0].cells[i].text = h
    for r in b["module_rows"]:
        c = tb.add_row().cells
        c[0].text, c[1].text, c[2].text = r["page"], r["module"], str(r["hours"])
    for r in b["custom_rows"]:
        c = tb.add_row().cells
        c[0].text, c[1].text, c[2].text = r["page"], r["title"], t("doc_manual", L)
    doc.add_paragraph(t("doc_rate", L, rate=b["hourly_rate_azn"]))
    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(path)
    return path


def _data_uri(p: Path, ext: str) -> str:
    mime = "image/png" if ext == "png" else "image/jpeg"
    return f"data:{mime};base64," + base64.b64encode(p.read_bytes()).decode()


def _html_value(it: dict, L: str) -> str:
    e = html.escape
    out = e(_fmt(it, L))
    for c in it.get("swatches", []):  # c yalnız rules.parse_hex_colors-dan keçmiş #RRGGBB-dir, yenə də escape olunur
        out += f"<br><span class='sw' style=\"background:{e(c)}\"></span> {e(c)}"
    return out


def _html_attachments(tz: dict, files_dir: Path | None, L: str) -> str:
    e = html.escape
    logos = _existing_files(tz, files_dir, "logo", MAX_LOGOS_IN_DOC)
    refs = _existing_files(tz, files_dir, "reference", MAX_REFS_IN_DOC)
    if not (logos or refs):
        return ""
    parts = [f"<h3>{e(t('doc_attachments', L))}</h3><div class='att'>"]
    for f, p in logos:
        parts.append(f"<figure><img class='logo' src='{_data_uri(p, f['ext'])}' alt=''><figcaption>{e(f['filename'])}</figcaption></figure>")
    for f, p in refs:
        parts.append(f"<figure><img class='ref' src='{_data_uri(p, f['ext'])}' alt=''><figcaption>{e(f['filename'])}</figcaption></figure>")
    return "".join(parts) + "</div>"


def _html_banner() -> str:
    e = html.escape
    name, tag, color = e(config.AGENCY_NAME), e(config.AGENCY_TAGLINE), e(config.AGENCY_COLOR)
    logo = ""
    if config.AGENCY_LOGO_PATH:
        ext = config.AGENCY_LOGO_PATH.suffix.lstrip(".").lower()
        if ext in ("png", "jpg", "jpeg"):
            logo = f"<img class='aglogo' src='{_data_uri(config.AGENCY_LOGO_PATH, 'jpg' if ext in ('jpg', 'jpeg') else 'png')}' alt=''>"
    return (f"<header class='banner' style='background:#{color}'>{logo}"
            f"<div><strong>{name}</strong>{f'<span>{tag}</span>' if tag else ''}</div></header>")


def _html_open(tz: dict, L: str) -> str:
    e = html.escape
    items = tz.get("clarifications") or []
    body = "".join(f"<li>{e(c)}</li>" for c in items) if items else f"<li>{e(t('doc_open_none', L))}</li>"
    return f"<h2>{e(t('doc_open_head', L))}</h2><ul class='open'>{body}</ul>"


def build_html(tz: dict, files_dir: Path | None = None) -> str:
    e = html.escape
    L = _lang(tz)
    parts = [_html_banner(),
             f"<h1>{e(t('doc_title', L))}</h1><p class='meta'>{e(t('doc_project', L))}: {e(tz['project_name'])} · "
             f"{e(t('doc_date', L))}: {e(tz['date'])}</p>",
             _html_open(tz, L)]
    for s in tz["sections"]:
        parts.append(f"<h2>{e(s['title'])}</h2>")
        if not s["items"]:
            parts.append(f"<p>{e(t('doc_no_data', L))}</p>")
        elif s["number"] in (5, 6, 7):
            parts.append("<ul>" + "".join(
                f"<li>{e(_fmt(i, L) if _is_req(i) else i['label'] + ': ' + _fmt(i, L))}</li>" for i in s["items"]) + "</ul>")
        else:
            parts.append("<table>" + "".join(
                f"<tr><th>{e(i['label'])}</th><td>{_html_value(i, L)}</td></tr>" for i in s["items"]) + "</table>")
        if s["number"] == 4:
            parts.append(_html_attachments(tz, files_dir, L))
    b = tz.get("budget", {})
    if b.get("module_rows") or b.get("custom_rows"):
        rows = "".join(f"<tr><td>{e(r['page'])}</td><td>{e(r['module'])}</td><td>{r['hours']}</td></tr>" for r in b["module_rows"])
        rows += "".join(f"<tr><td>{e(r['page'])}</td><td>{e(r['title'])}</td><td>{e(t('doc_manual', L))}</td></tr>" for r in b["custom_rows"])
        parts.append(f"<h2>{e(t('doc_annex', L))}</h2><table><tr><th>{e(t('doc_th_page', L))}</th><th>{e(t('doc_th_module', L))}</th>"
                     f"<th>{e(t('doc_th_hours', L))}</th></tr>" + rows + f"</table><p>{e(t('doc_rate', L, rate=b.get('hourly_rate_azn')))}</p>")
    css = ("body{font-family:'DejaVu Sans',Arial,sans-serif;font-size:10.5pt;color:#0f172a}"
           "h1{color:#1e2a5e}h2{font-size:13pt;border-bottom:1px solid #cbd5e1;padding-bottom:3px;margin-top:20px}"
           "table{width:100%;border-collapse:collapse}th,td{border:1px solid #e2e8f0;padding:5px 8px;text-align:left;vertical-align:top}"
           "th{background:#f1f5f9;width:30%}.meta{color:#64748b}"
           ".sw{display:inline-block;width:14px;height:14px;border:1px solid #94a3b8;border-radius:3px;vertical-align:middle}"
           "h3{font-size:11pt;margin-top:14px}.att{display:flex;flex-wrap:wrap;gap:10px}figure{margin:0}"
           "figcaption{font-size:8pt;color:#64748b}img.logo{height:60px}img.ref{width:250px}"
           ".banner{color:#fff;padding:10px 14px;display:flex;align-items:center;gap:12px;margin:-8px -8px 16px}"
           ".banner strong{display:block;font-size:13pt}.banner span{font-size:9pt;opacity:.9}"
           "img.aglogo{height:36px;background:#fff;border-radius:4px;padding:2px}"
           "ul.open{background:#fffbeb;border:1px solid #fde68a;padding:10px 10px 10px 28px}")
    return f"<!doctype html><html lang='{L}'><meta charset='utf-8'><style>{css}</style><body>{''.join(parts)}</body></html>"


def build_pdf(tz: dict, path: Path, files_dir: Path | None = None) -> Path:
    from weasyprint import HTML  # tənbəl import: sistem kitabxanaları lazımdır

    path.parent.mkdir(parents=True, exist_ok=True)
    HTML(string=build_html(tz, files_dir)).write_pdf(str(path))
    return path
