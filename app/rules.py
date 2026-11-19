"""Qaydalar: şablon tətbiqi, asılılıqlar, büdcə/vaxt hesablaması, ziddiyyət yoxlaması.
LLM heç vaxt qiymət və ya saat yazmır: hamısı burada və data/modules.yaml-dan gəlir."""
from __future__ import annotations

import math
import re
from typing import Any, Iterable, Optional

from . import catalog, i18n
from .schemas import CustomItem, FieldValue, Module, Page, Source, TZState

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")
LANG_WORDS = {
    "az": ["az", "azərbaycan", "azərbaycanca", "azeri", "azerbaijani", "азербайджан"],
    "en": ["en", "ingilis", "ingiliscə", "english", "английск", "англ"],
    "ru": ["ru", "rus", "rusca", "russian", "русск", "русский"],
    "tr": ["tr", "türk", "türkcə", "turkish", "турецк"],
}


# ---------- dillər ----------
def parse_languages(text: str) -> list[str]:
    t = catalog.fold(text)
    found = []
    for code, words in LANG_WORDS.items():
        if any(catalog.kw_in(w, t) for w in words):
            found.append(code)
    return found


def langs(state: TZState) -> list[str]:
    fv = state.fields.get("languages")
    if not fv:
        return ["az"]
    opt = catalog.option_by_label("languages", fv.value)
    if opt:
        return list(opt["value"])
    return parse_languages(str(fv.value)) or ["az"]


# ---------- rənglər ----------
HEX_RE = re.compile(r"(?<![\w#])#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})(?![\w])")


def parse_hex_colors(text: str, limit: int = 6) -> list[str]:
    """Mətndəki HEX rənglər (#RGB / #RRGGBB) böyük hərflə 6 rəqəmli formada, təkrarsız. Söz ilə yazılan rənglərdən HEX uydurulmur."""
    out: list[str] = []
    for m in HEX_RE.finditer(text or ""):
        h = m.group(1).upper()
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        c = "#" + h
        if c not in out:
            out.append(c)
    return out[:limit]


# ---------- sahə yoxlaması ----------
def coerce_field(fid: str, value: Any) -> Optional[str]:
    """LLM/istifadəçi dəyərini sahənin tipinə görə yoxlayır. Etibarsızdırsa None."""
    f = catalog.field(fid)
    if not f or value is None:
        return None
    if isinstance(value, (list, tuple)):
        value = ", ".join(str(v) for v in value)
    value = str(value).strip()
    if not value or len(value) > 500:
        return None
    ftype = f["type"]
    if ftype == "file":  # fayl yalnız yükləmə endpoint-i ilə gəlir; mətndən yalnız sahənin öz «yoxdur» cavabı qəbul olunur
        return value if f.get("default") and value == f["default"] else None
    if ftype == "email":
        return value if EMAIL_RE.match(value) else None
    if ftype == "text":
        return value
    if ftype == "languages":
        codes = parse_languages(value)
        for o in f["options"]:
            if o["value"] == codes:
                return o["label"]
        if codes:
            return " + ".join(c.upper() for c in codes)
        return None
    # choice
    opt = catalog.option_by_label(fid, value)
    if opt:
        return opt["label"]
    opt = match_option(fid, value)
    if opt:
        return opt["label"]
    return value if f.get("allow_other") and len(value) <= 200 else None


def match_option(fid: str, text: str) -> Optional[dict]:
    """Açar sözə görə tək seçim tapılırsa qaytarır (qeyri-müəyyənlikdə None)."""
    f = catalog.field(fid) or {}
    t = catalog.fold(text)
    hits = [o for o in f.get("options", []) if any(catalog.kw_in(k, t) for k in o.get("kw", []))]
    return hits[0] if len(hits) == 1 else None


def get(state: TZState, fid: str, default: Any = None) -> Any:
    fv = state.fields.get(fid)
    return fv.value if fv else default


def set_field(state: TZState, fid: str, value: str, source: Source, confidence: float = 1.0) -> None:
    state.fields[fid] = FieldValue(value=value, source=source, confidence=confidence)
    if fid in state.skipped:
        state.skipped.remove(fid)


def option_value(state: TZState, fid: str) -> Any:
    opt = catalog.option_by_label(fid, get(state, fid))
    return opt["value"] if opt else None


# ---------- struktur köməkçiləri ----------
def all_modules(state: TZState) -> Iterable[Module]:
    for p in state.structure.pages:
        yield from p.modules
    yield from state.structure.global_features


def has_module(state: TZState, mtype: str) -> bool:
    return any(m.type == mtype for m in all_modules(state))


def find_page(state: TZState, name: str) -> Optional[Page]:
    n = catalog.fold(name)
    for p in state.structure.pages:
        if catalog.fold(p.name) == n:
            return p
    for p in state.structure.pages:
        pn = catalog.fold(p.name)
        if n and (n in pn or pn in n):
            return p
    return None


def make_module(mtype: str, source: Source) -> Module:
    meta = catalog.module(mtype)
    return Module(type=mtype, description=meta["desc"] if meta else "", source=source,
                  kind="standard", estimated_hours=meta["hours"] if meta else None)


def add_custom(state: TZState, title: str, description: str = "", page: Optional[str] = None) -> CustomItem:
    """Kataloqda olmayan tələb: saatı uydurulmur, 'əl ilə qiymətləndirilməlidir'."""
    for c in state.custom_items:
        if catalog.fold(c.title) == catalog.fold(title):
            return c
    item = CustomItem(title=title.strip()[:120], description=description.strip()[:500], page=page)
    state.custom_items.append(item)
    target = find_page(state, page) if page else None
    mod = Module(type="custom", description=item.title, source="user", kind="custom", estimated_hours=None)
    if target:
        target.modules.append(mod)
    else:
        state.structure.global_features.append(mod)
    return item


def apply_template(state: TZState, site_type_value: str) -> None:
    tpl = catalog.template(site_type_value)
    if not tpl:
        return
    state.structure.pages = [
        Page(name=p["name"], purpose=p.get("purpose", ""), source="template",
             modules=[make_module(m, "template") for m in p.get("modules", [])])
        for p in tpl["pages"]
    ]
    state.structure.global_features = [make_module(m, "template") for m in tpl.get("global", [])]
    state.custom_items = []
    state.structure_confirmed = False
    state.structure_shown = False
    if tpl.get("custom_item"):
        add_custom(state, tpl["custom_item"], i18n.t("custom_item_desc"))


def ensure_requirements(state: TZState) -> None:
    """Asılılıq qaydaları: çoxdillilik və modul tələbləri avtomatik əlavə olunur."""
    g = state.structure.global_features
    multi = len(langs(state)) > 1
    present = next((m for m in g if m.type == "multilingual"), None)
    if multi and not present:
        g.append(make_module("multilingual", "calculated"))
    elif not multi and present and present.source != "user":
        g.remove(present)
    for _ in range(2):
        for m in list(all_modules(state)):
            meta = catalog.module(m.type) if m.kind == "standard" else None
            for req in (meta or {}).get("requires", []):
                if not has_module(state, req):
                    g.append(make_module(req, "calculated"))


# ---------- sahələrin tətbiq olunması ----------
def field_applicable(fid: str, state: TZState) -> bool:
    f = catalog.field(fid)
    if not f:
        return False
    when = f.get("when")
    if not when:
        return True
    if "module" in when:
        return has_module(state, when["module"])
    if "field" in when:  # başqa sahənin cavabından asılı (məs. loqo yalnız "loqo var" deyiləndə)
        return option_value(state, when["field"]) in when.get("in", [])
    return True


def applicable_fields(state: TZState, only_asked: bool = True) -> list[str]:
    out = []
    for fid in catalog.flow():
        f = catalog.field(fid)
        if f and field_applicable(fid, state) and (not only_asked or f.get("ask", True)):
            out.append(fid)
    return out


def autofill(state: TZState) -> None:
    """ask:false sahələr şablon dəyəri ilə dolur."""
    for fid, f in catalog.fields().items():
        if f.get("ask", True) is False and fid not in state.fields and f.get("default"):
            set_field(state, fid, f["default"], "template")


# ---------- törəmə tələblər ----------
def _dedupe(items: list[str]) -> list[str]:
    seen, out = set(), []
    for i in items:
        if i not in seen:
            seen.add(i)
            out.append(i)
    return out


def derive(state: TZState) -> dict:
    base = catalog.base_requirements()
    tech, func, sec = list(base["tech"]), list(base["functional"]), list(base["security"])
    for m in all_modules(state):
        meta = catalog.module(m.type) if m.kind == "standard" else None
        eff = (meta or {}).get("effects", {})
        tech += eff.get("tech", [])
        func += eff.get("functional", [])
        sec += eff.get("security", [])
        if meta:
            func.append(i18n.t("module_prefix", title=meta["title"]))
    # müştərinin cavablarından törəyən tələblər (domen/hostinq, redesign, analitika)
    dh = option_value(state, "domain_hosting")
    if dh in ("both", "domain", "hosting", "none"):
        tech.append(i18n.t(f"req_domain_{dh}"))
    if option_value(state, "existing_site") == "redesign":
        tech.append(i18n.t("req_redesign"))
    acfg = catalog.analytics_requirements()
    ans = get(state, "seo_analytics")
    aopt = option_value(state, "seo_analytics")
    if aopt in acfg:
        func += acfg[aopt]
    elif ans:  # sərbəst cavab: müştərinin sözləri olduğu kimi
        func.append(i18n.t("req_analytics_custom", value=ans))
    elif "seo_analytics" not in state.skipped:  # sual hələ verilməyib: əvvəlki standart
        func += acfg.get("default", [])
    heavy = catalog.heavy_modules()
    has_heavy = any(m.type in heavy for m in all_modules(state))
    has_custom = bool(state.custom_items)
    if has_heavy or has_custom:
        platform, why = i18n.t("platform_laravel"), i18n.t("why_heavy")
    else:
        platform, why = i18n.t("platform_wp"), i18n.t("why_wp")
    return {"tech": _dedupe(tech), "functional": _dedupe(func), "security": _dedupe(sec),
            "platform": platform, "platform_why": why}


# ---------- büdcə və vaxt ----------
def estimate(state: TZState) -> dict:
    cfg = catalog.pricing()
    rate = cfg["hourly_rate_azn"]
    module_rows, custom_rows, module_hours = [], [], 0.0
    for p in state.structure.pages:
        for m in p.modules:
            if m.kind == "custom":
                custom_rows.append({"page": p.name, "title": m.description})
                continue
            h = (catalog.module(m.type) or {}).get("hours", 0)
            module_hours += h
            module_rows.append({"page": p.name, "module": catalog.module_title(m.type), "hours": h})
    for m in state.structure.global_features:
        if m.kind == "custom":
            custom_rows.append({"page": i18n.t("page_general"), "title": m.description})
            continue
        h = (catalog.module(m.type) or {}).get("hours", 0)
        module_hours += h
        module_rows.append({"page": i18n.t("page_general"), "module": catalog.module_title(m.type), "hours": h})
    extra_lang = max(0, len(langs(state)) - 1) * cfg["extra_language_hours_per_page"] * len(state.structure.pages)
    fixed = sum(f["hours"] for f in cfg["fixed"])
    subtotal = module_hours + extra_lang + fixed
    overhead = [{"id": o["id"], "label": o["label"], "hours": round(subtotal * o["pct"], 1)} for o in cfg["overhead"]]
    total = round(subtotal + sum(o["hours"] for o in overhead), 1)
    per_day = cfg["hours_per_week"] / 5
    od = {o["id"]: o["hours"] for o in overhead}
    dev_hours = module_hours + extra_lang
    phases = [
        {"phase": i18n.t("phase_design"), "hours": od.get("design", 0)},
        {"phase": i18n.t("phase_dev"), "hours": dev_hours},
        {"phase": i18n.t("phase_qa"), "hours": od.get("qa", 0)},
        {"phase": i18n.t("phase_setup"), "hours": fixed + od.get("pm", 0)},
    ]
    for ph in phases:
        ph["hours"] = round(ph["hours"], 1)
        ph["days"] = max(1, math.ceil(ph["hours"] / per_day)) if ph["hours"] else 0
    weeks = max(1, math.ceil(total / cfg["hours_per_week"]))
    pct = cfg["range_pct"]
    return {
        "hourly_rate_azn": rate,
        "module_rows": module_rows,
        "custom_rows": custom_rows,
        "extra_language_hours": round(extra_lang, 1),
        "fixed_hours": fixed,
        "overhead": overhead,
        "total_hours": total,
        "weeks": weeks,
        "weeks_range": (max(1, math.floor(weeks * (1 - pct))), math.ceil(weeks * (1 + pct))),
        "cost_min": round(total * rate * (1 - pct), -1),
        "cost_max": round(total * rate * (1 + pct), -1),
        "phases": phases,
        "payment_plan": cfg["payment_plan"],
        "has_custom": bool(custom_rows),
    }


# ---------- ziddiyyət yoxlaması ----------
def check_contradictions(state: TZState) -> list[str]:
    warns: list[str] = []
    if not state.structure.pages:
        return warns
    est = estimate(state)
    opt = catalog.option_by_label("budget_range", get(state, "budget_range"))
    if opt and opt["value"] is not None and est["cost_min"] > opt["value"]:
        warns.append(i18n.t("warn_budget", lo=int(est["cost_min"]), hi=int(est["cost_max"]), budget=get(state, "budget_range")))
    dl = catalog.option_by_label("deadline", get(state, "deadline"))
    if dl and dl["value"] is not None:
        months_weeks = dl["value"] * 4.3
        if est["weeks_range"][0] > months_weeks:
            warns.append(i18n.t("warn_deadline", deadline=get(state, "deadline"), lo=est["weeks_range"][0], hi=est["weeks_range"][1]))
    if not opt and get(state, "budget_range"):  # sərbəst mətn büdcə ("5000 AZN"): rəqəmi çıxar
        nums = [int(n) for n in re.findall(r"\d+", str(get(state, "budget_range")).replace(" ", ""))]
        if nums and est["cost_min"] > max(nums):
            warns.append(i18n.t("warn_budget_short", lo=int(est["cost_min"]), hi=int(est["cost_max"]), budget=get(state, "budget_range")))
    if len(langs(state)) >= 3 and opt and opt["value"] is not None and opt["value"] <= 1000:
        warns.append(i18n.t("warn_langs"))
    return warns


# ---------- slot məntiqi ----------
def is_skippable(fid: str) -> bool:
    """False: sayt növü, ad, məqsəd kimi məlumatlar olmadan TZ yazmaq olmaz."""
    f = catalog.field(fid) or {}
    return f.get("skippable", True) is not False


def prune_inapplicable(state: TZState) -> list[str]:
    """Cavab dəyişəndən sonra artıq tətbiq olunmayan sahələri silir (məs. «yeni sayt» seçilibsə köhnə saytın linki).
    Silinən sahələrin adlarını qaytarır. Fayllara toxunmur."""
    removed: list[str] = []
    for _ in range(3):  # asılılıq zənciri (məs. brand_assets -> brand_logo) üçün bir neçə keçid
        gone = [fid for fid in list(state.fields) + list(state.skipped)
                if (catalog.field(fid) or {}).get("when") and not field_applicable(fid, state)]
        if not gone:
            break
        for fid in gone:
            state.fields.pop(fid, None)
            if fid in state.skipped:
                state.skipped.remove(fid)
            label = (catalog.field(fid) or {}).get("label", fid)
            if label not in removed:
                removed.append(label)
    return removed


def mark_open(state: TZState, fid: str) -> None:
    """Müştəri bilmir/sonra verəcək: dəyər UYDURULMUR, 'açıq sual' kimi qeyd olunur."""
    state.fields.pop(fid, None)
    if fid not in state.skipped:
        state.skipped.append(fid)


def field_filled(state: TZState, fid: str) -> bool:
    return fid in state.fields or fid in state.skipped


def next_slot(state: TZState) -> str:
    """Növbəti sual: əvvəl custom tələblər, sonra axındakı ilk boş sahə/struktur."""
    for c in state.custom_items:
        for qid in catalog.questions_cfg()["custom_questions"]:
            if qid not in c.answers:
                return f"custom:{c.id}:{qid}"
    for fid in catalog.flow():
        if fid == "structure":
            if "site_type" in state.fields and not state.structure_confirmed:
                return "structure"
            continue
        if fid == "page_content":  # struktur təsdiqlənəndən sonra hər səhifənin məzmunu
            pid = next_page_pending(state)
            if pid:
                return f"page:{pid}"
            continue
        f = catalog.field(fid)
        if not f or f.get("ask", True) is False or not field_applicable(fid, state):
            continue
        if not field_filled(state, fid):
            return f"field:{fid}"
    return "final"


def next_page_pending(state: TZState) -> Optional[str]:
    """Məzmunu hələ soruşulmamış ilk səhifənin id-si (struktur təsdiqlənməyibsə None)."""
    if not state.structure_confirmed:
        return None
    return next((p.id for p in state.structure.pages if p.content_status == "pending"), None)


def find_page_by_id(state: TZState, pid: str) -> Optional[Page]:
    return next((p for p in state.structure.pages if p.id == pid), None)


def missing_required(state: TZState) -> list[str]:
    miss = []
    for fid in applicable_fields(state):
        f = catalog.field(fid)
        if f.get("required") and not field_filled(state, fid):
            miss.append(f["label"])
    if not state.structure_confirmed:
        miss.append(i18n.t("miss_structure"))
    qs = catalog.questions_cfg()["custom_questions"]
    for c in state.custom_items:
        if any(q not in c.answers for q in qs):
            miss.append(i18n.t("miss_clar", title=c.title))
    return miss
