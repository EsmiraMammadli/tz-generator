"""State-dən yekun TZ sənədini (JSON) qurur. UI paneli, xülasə ekranı, DOCX/PDF və snapshot eyni mənbədən gəlir."""
from __future__ import annotations

from datetime import date
from typing import Any

from . import catalog, i18n, rules
from .schemas import TZState

def sections_titles() -> dict[int, str]:
    return {n: i18n.t(f"sec{n}") for n in range(1, 11)}


NEEDS_STRUCTURE = {5, 6, 7, 8, 10}


def _item(label: str, value: Any, source: str, req: bool = False, swatches: list[str] | None = None,
          field_id: str | None = None, editable: bool = False, input_type: str | None = None,
          options: list | None = None, page_id: str | None = None, skippable: bool | None = None) -> dict:
    it = {"label": label, "value": value, "source": source, "req": req, "editable": editable}
    if swatches:
        it["swatches"] = swatches  # seçilmiş HEX rənglər: xülasədə və sənəddə rəng nümunəsi kimi göstərilir
    if field_id:
        it["field_id"] = field_id
    if input_type:
        it["input"] = input_type
    if options:
        it["options"] = options
    if page_id:
        it["page_id"] = page_id
    if skippable is not None:
        it["skippable"] = skippable  # false: məcburi sahə, «developer ilə dəqiqləşdirəcəm» göstərilmir
    return it


def _edit_opts(f: dict) -> list[str]:
    return [o["label"] for o in f.get("options", [])]


def _field_items(state: TZState, sec: int) -> list[dict]:
    items = []
    for fid, f in catalog.fields().items():
        if f["section"] != sec:
            continue
        can = f.get("ask", True) is not False and f.get("type") != "file" and fid != "site_type"
        extra = dict(field_id=fid, editable=can, input_type=f.get("type"),
                     options=_edit_opts(f) if f.get("type") in ("choice", "languages") else None,
                     skippable=rules.is_skippable(fid))
        if fid in state.fields:
            fv = state.fields[fid]
            sw = rules.parse_hex_colors(str(fv.value)) if fid == "brand_colors" else None
            items.append(_item(f["label"], fv.value, fv.source, swatches=sw, **extra))
        elif fid in state.skipped:
            items.append(_item(f["label"], i18n.t("unspecified"), "open", **extra))
    return items


def page_tree(state: TZState) -> list[dict]:
    out = []
    for p in state.structure.pages:
        out.append({
            "id": p.id, "name": p.name, "sub": False, "kind": p.kind, "purpose": p.purpose, "source": p.source,
            "content": p.content, "content_status": p.content_status,
            "modules": [{"type": m.type, "title": (m.description if m.kind == "custom" else catalog.module_title(m.type)),
                         "source": m.source, "custom": m.kind == "custom"} for m in p.modules],
        })
    return out


def _status(state: TZState, sec: int) -> str:
    if sec == 3:
        if state.structure_confirmed:
            return "completed"
        return "in_progress" if state.structure.pages else "pending"
    req = [fid for fid in rules.applicable_fields(state) if catalog.field(fid)["section"] == sec]
    if req:
        done = [f for f in req if rules.field_filled(state, f)]
        base = "completed" if len(done) == len(req) else ("in_progress" if done else "pending")
    else:
        base = "completed"
    if sec in NEEDS_STRUCTURE and not state.structure_confirmed:
        base = "in_progress" if (base != "pending" or state.structure.pages) else "pending"
    return base


def _section_source(items: list[dict]) -> str:
    srcs = {i["source"] for i in items}
    if not srcs:
        return "none"  # hələ məlumat yoxdur: UI etiket göstərmir
    if "open" in srcs:
        return "open"  # bu bölmədə müştərinin dəqiqləşdirməli olduğu məlumat var
    if srcs == {"user"}:
        return "user"
    if "inferred" in srcs:  # yalnız köhnə sessiyalar
        return "inferred"
    return "calculated" if "calculated" in srcs and "user" not in srcs else "template"


def progress(state: TZState) -> int:
    req = rules.applicable_fields(state)  # soruşulan bütün sahələr (loqo/rəng daxil)
    done = sum(1 for f in req if rules.field_filled(state, f))
    pages = state.structure.pages
    total = len(req) + 1 + sum(1 for c in state.custom_items) + len(pages)
    cust_done = sum(1 for c in state.custom_items
                    if all(q in c.answers for q in catalog.questions_cfg()["custom_questions"]))
    done += (1 if state.structure_confirmed else 0) + cust_done
    done += sum(1 for p in pages if p.content_status != "pending")
    return int(round(100 * done / total)) if total else 0


def build_tz(state: TZState) -> dict:
    i18n.set_lang(state.language)
    SECTIONS = sections_titles()
    d = rules.derive(state)
    est = rules.estimate(state)
    warnings = rules.check_contradictions(state)
    sections: dict[int, list[dict]] = {n: _field_items(state, n) for n in SECTIONS}

    # 2: platforma
    sections[2].insert(0, _item(i18n.t("platform_label"), f"{d['platform']}. {d['platform_why']}", "calculated"))
    # 4: brend bələdçisi (PDF) sahə deyil, yüklənmiş fayldır
    guides = [f.filename for f in state.files if f.kind == "guide"]
    if guides:
        sections[4].append(_item(i18n.t("brand_guide_label"), ", ".join(guides), "user"))
    # 3: səhifə strukturu
    for p in state.structure.pages:
        mods = ", ".join(m.description if m.kind == "custom" else catalog.module_title(m.type) for m in p.modules)
        tag = i18n.t("tag_manual") if any(m.kind == "custom" for m in p.modules) else ""
        content = f" {i18n.t('content_line', text=p.content)}" if p.content_status == "answered" and p.content else ""
        sections[3].append(_item(p.name, (f"{p.purpose}. " if p.purpose else "") + i18n.t("modules_line", mods=mods or "—") + tag + content,
                                 "open" if p.content_status == "open" else p.source,
                                 page_id=p.id, editable=True, input_type="page_content"))
    for m in state.structure.global_features:
        title = m.description if m.kind == "custom" else catalog.module_title(m.type)
        sections[3].append(_item(i18n.t("global_feature"), title, m.source))
    # 5, 6, 7: törəmə tələblər
    rq = i18n.t("req_label")
    sections[5] += [_item(rq, x, "template", req=True) for x in d["tech"]]
    sections[6] += [_item(rq, x, "template", req=True) for x in d["functional"]]
    sections[7] += [_item(rq, x, "template", req=True) for x in d["security"]]
    # 8: çatdırılma
    if state.structure.pages:
        lo, hi = est["weeks_range"]
        sections[8].append(_item(i18n.t("est_duration"), i18n.t("weeks_range", lo=lo, hi=hi) + (i18n.t("custom_not_included") if est["has_custom"] else ""), "calculated"))
        for ph in est["phases"]:
            sections[8].append(_item(ph["phase"], i18n.t("work_days", n=ph["days"]), "calculated"))
        sections[8].append(_item(i18n.t("first_demo"), i18n.t("first_demo_val"), "template"))
    # 9: əlavələr
    if state.fields.get("brand_assets") and rules.option_value(state, "brand_assets") in ("none", "logo", "colors"):
        sections[9].append(_item(i18n.t("brand_note_label"), i18n.t("brand_note"), "calculated"))
    # 10: büdcə
    if state.structure.pages:
        extra = i18n.t("extra_cost") if est["has_custom"] else ""
        sections[10].append(_item(i18n.t("est_total"), i18n.t("est_total_val", lo=int(est["cost_min"]), hi=int(est["cost_max"]), h=est["total_hours"], extra=extra), "calculated"))
        for pp in est["payment_plan"]:
            sections[10].append(_item(i18n.t("payment_plan_label"), f"{pp['label']}: {pp['pct']}%", "template"))

    out_sections = []
    for n, title in SECTIONS.items():
        items = sections[n]
        out_sections.append({
            "id": f"s{n}", "number": n, "title": f"{n}. {title}", "name": title,
            "status": _status(state, n),
            "snippet": _snippet(items),
            "source": _section_source(items),
            "items": items,
        })

    def _clar(c):
        d = c.description.strip()
        head = c.title if not d or catalog.fold(d) == catalog.fold(c.title) else f"{c.title}: {d}"
        return f"{head}. {i18n.t('clar_tail')}"
    clar = [_clar(c) for c in state.custom_items]
    for fid in state.skipped:
        f = catalog.field(fid)
        if f:
            clar.append(i18n.t("clar_skipped", label=f["label"]))
    for p in state.structure.pages:
        if p.content_status == "open":
            clar.append(i18n.t("clar_page_content", name=p.name))
    missing = rules.missing_required(state)
    return {
        "title": i18n.t("tz_title"),
        "project_name": rules.get(state, "company_name", i18n.t("unnamed")),
        "date": date.today().isoformat(),
        "language": state.language,
        "progress": progress(state),
        "sections": out_sections,
        "page_tree": page_tree(state),
        "files": files_list(state),
        "clarifications": clar,
        "custom_items": [c.model_dump() for c in state.custom_items],
        "warnings": warnings,
        "budget": est,
        "missing": missing,
        "ready": not missing,
    }


def files_list(state: TZState) -> list[dict]:
    return [{"id": f.id, "kind": f.kind, "filename": f.filename, "ext": f.ext, "size": f.size} for f in state.files]


def _snippet(items: list[dict]) -> str:
    vals = [str(i["value"]) for i in items if not i.get("req")][:2]
    s = "; ".join(vals) if vals else i18n.t("snippet_wait")
    return s if len(s) <= 90 else s[:87] + "…"


def ui_state(state: TZState) -> dict:
    """UI-ın irəliləyiş paneli üçün yığcam state."""
    tz = build_tz(state)
    return {"progress": tz["progress"], "sections": tz["sections"], "page_tree": tz["page_tree"],
            "warnings": tz["warnings"], "ready": tz["ready"], "files": tz["files"]}
