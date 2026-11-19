"""Söhbət mühərriki (slot-filling). DB-dən və HTTP-dən asılı deyil: TZState + mətn → TurnResult.

Axın: mesaj → (deterministik uyğunlaşdırma | LLM çıxarışı) → state yenilənir → asılılıqlar
→ ziddiyyət yoxlaması → növbəti sual."""
from __future__ import annotations

import logging

from . import catalog, rules
from .i18n import set_lang, t
from .llm import Ctx, Extractor, is_default_text
from .schemas import Extraction, Page, PageOp, TurnResult, TZState

log = logging.getLogger("tz.engine")
MAX_RETRIES = 2


# ---------- sual mətnləri ----------
def question_for(slot: str, state: TZState) -> tuple[str, list[str], bool]:
    cfg = catalog.questions_cfg()
    if slot == "final":
        return t("final_q"), [t("chip_summary")], False
    if slot == "structure":
        label = rules.get(state, "site_type", "sayt")
        tpl = catalog.template(rules.option_value(state, "site_type") or "") or {}
        chips = [cfg["structure_question"]["chip_ok"]]
        for mid in tpl.get("suggest", []):
            if not rules.has_module(state, mid):
                chips.append(t("add_chip", title=catalog.module_title(mid)))
        if state.structure_shown:  # təkrar: qısa sual
            text = t("struct_again", ok=cfg["structure_question"]["chip_ok"])
        else:
            text = cfg["structure_question"]["text"].format(site_type=label)
            state.structure_shown = True
        return text, chips[:4], True
    if slot.startswith("page:"):
        page = rules.find_page_by_id(state, slot.split(":", 1)[1])
        if not page:  # köhnəlmiş slot (səhifə silinib): növbəti real suala keç
            return question_for(rules.next_slot(state), state)
        pc = cfg["page_content_question"]
        intro = ""
        if not state.page_intro_shown:
            intro, state.page_intro_shown = t("page_content_intro"), True
        chips = [cfg["skip_chip"]]
        if sum(1 for p in state.structure.pages if p.content_status == "pending") > 1:
            chips.append(pc["all_later_chip"])  # qalan bütün səhifələr üçün bir kliklə
        return intro + pc["text"].format(name=page.name), chips, False
    if slot.startswith("custom:"):
        _, cid, qid = slot.split(":")
        item = next(c for c in state.custom_items if c.id == cid)
        q = cfg["custom_questions"][qid]
        intro = t("custom_intro", title=item.title) if qid == "who_uses" else ""
        return intro + q, [cfg["custom_default_chip"]], False
    fid = slot.split(":", 1)[1]
    f = catalog.field(fid)
    chips = [o["label"] for o in f.get("options", [])][:8]
    if f.get("skip_chip_label"):  # məs. "Loqonu sonra göndərəcəm"
        chips.append(f["skip_chip_label"])
    elif f.get("default_chip_label"):  # məs. "Nümunə yoxdur": faktiki cavabdır
        chips.append(f["default_chip_label"])
    elif f.get("ask", True) and rules.is_skippable(fid):
        chips.append(cfg["skip_chip"])  # təxmin yox: "developer ilə dəqiqləşdirəcəm"
    return f["question"], chips, False


def why_for(slot: str, state: TZState) -> str:
    """Qısa «niyə soruşuruq» izahı: texniki bilməyən müştəri sualın nəyə lazım olduğunu görür."""
    cfg = catalog.questions_cfg()
    if slot == "structure":
        return cfg["structure_question"].get("why", "")
    if slot.startswith("page:"):
        return cfg["page_content_question"].get("why", "")
    if slot.startswith("custom:"):
        return cfg.get("custom_why", "")
    if slot.startswith("field:"):
        return (catalog.field(slot.split(":", 1)[1]) or {}).get("why", "")
    return ""


def widget_for(slot: str) -> str | None:
    """UI-da söhbət daxilində fayl/rəng seçici göstərilən suallar."""
    return {"field:brand_logo": "logo", "field:brand_colors": "colors",
            "field:reference_screenshots": "references"}.get(slot)


def _ack(ext: Extraction, state: TZState, fallback: str = "") -> str:
    acks = t("acks")
    return (ext.ack or fallback or acks[state.turns % len(acks)]).strip()


# ---------- başlanğıc ----------
def start(state: TZState) -> TurnResult:
    set_lang(state.language)
    rules.autofill(state)
    state.pending_slot = rules.next_slot(state)
    q, chips, tree = question_for(state.pending_slot, state)
    return TurnResult(reply=t("greeting") + q, chips=chips, show_tree=tree, widget=widget_for(state.pending_slot),
                      why=why_for(state.pending_slot, state))


# ---------- strukturun dəyişdirilməsi ----------
def apply_page_ops(state: TZState, ops: list[PageOp]) -> list[str]:
    """Səhifə/modul əməliyyatları. Kataloqda olmayan hər şey custom tələbə çevrilir. Qeydlər qaytarır."""
    set_lang(state.language)
    notes: list[str] = []
    for op in ops:
        name = op.name.strip()
        if not name:
            continue
        mods = [m for m in op.module_types if catalog.module(m)]
        unknown = [m for m in op.module_types if not catalog.module(m)]
        if op.op == "add":
            if rules.find_page(state, name):  # eyni/bənzər səhifə artıq var
                continue
            if not mods and not unknown:
                mid = catalog.match_module(name)
                mods = [mid] if mid else []
            page = Page(name=name, purpose=op.purpose or "", source="user",
                        modules=[rules.make_module(m, "user") for m in mods])
            state.structure.pages.append(page)
            if not mods:
                rules.add_custom(state, name, op.purpose or "", page=name)
            for u in unknown:
                rules.add_custom(state, u, "", page=name)
            page.kind = "custom" if any(m.kind == "custom" for m in page.modules) else "standard"
            notes.append(t("note_page_added", name=name))
        elif op.op == "remove":
            page = rules.find_page(state, name)
            if page:
                titles = {catalog.fold(m.description) for m in page.modules if m.kind == "custom"}
                state.custom_items = [c for c in state.custom_items
                                      if c.page != page.name and catalog.fold(c.title) not in titles]
                state.structure.pages.remove(page)
                notes.append(t("note_page_removed", name=page.name))
        elif op.op == "rename" and (op.new_name or op.purpose is not None):
            page = rules.find_page(state, name)
            if page:
                old_name = page.name
                new_name = (op.new_name or page.name).strip()[:80] or page.name
                for c in state.custom_items:
                    if c.page == old_name:
                        c.page = new_name
                page.name, page.source = new_name, "user"
                if op.purpose is not None:
                    page.purpose = op.purpose.strip()[:300]
                notes.append(t("note_renamed", old=old_name, new=new_name) if new_name != old_name
                             else t("note_page_edited", name=new_name))
        elif op.op in ("add_module", "remove_module"):
            page = rules.find_page(state, name)
            holder = page.modules if page else state.structure.global_features
            if op.op == "add_module":
                for m in mods:
                    if not any(x.type == m for x in holder):
                        holder.append(rules.make_module(m, "user"))
                        notes.append(t("note_module_added", title=catalog.module_title(m)))
                for u in unknown:
                    rules.add_custom(state, u, "", page=page.name if page else None)
            else:
                before = len(holder)
                holder[:] = [x for x in holder if x.type not in mods]
                if len(holder) != before:
                    notes.append(t("note_module_removed"))
    return notes


# ---------- çıxarışın tətbiqi ----------
def _mark_open(state: TZState, slot: str) -> bool:
    """Müştəri bilmir / sonra verəcək. Dəyər UYDURULMUR: sahə 'açıq sual' kimi TZ-də qeyd olunur."""
    if slot.startswith("page:"):
        page = rules.find_page_by_id(state, slot.split(":", 1)[1])
        if page:
            page.content, page.content_status = "", "open"
            return True
        return False
    if slot.startswith("field:"):
        fid = slot.split(":", 1)[1]
        if rules.is_skippable(fid):
            rules.mark_open(state, fid)
            return True
        return False
    if slot.startswith("custom:"):
        _, cid, qid = slot.split(":")
        next(c for c in state.custom_items if c.id == cid).answers[qid] = t("unspecified")
        return True
    return False


def _apply_site_type(state: TZState, old_value) -> None:
    new_value = rules.option_value(state, "site_type")
    if not new_value:
        return
    edited = any(p.source != "template" for p in state.structure.pages)
    if (new_value != old_value and not edited) or not state.structure.pages:
        rules.apply_template(state, new_value)


def apply_extraction(state: TZState, slot: str, text: str, ext: Extraction) -> bool:
    changed = False
    slot_fid = slot.split(":", 1)[1] if slot.startswith("field:") else None
    order = {fid: i for i, fid in enumerate(catalog.flow())}
    # axın sırası ilə: əvvəlki sahə (məs. domain_hosting) sonrakının (domain_name) tətbiq olunmasını müəyyən edir
    for fid in sorted(ext.fields, key=lambda f: order.get(f, 999)):
        f = catalog.field(fid)
        if not f:
            continue
        extra = fid != slot_fid  # uzun cavabdan çıxarılan, hazırkı sualdan kənar sahə
        if extra and (f.get("ask", True) is False or not rules.field_applicable(fid, state)):
            continue  # indi tətbiq olunmur (məs. modul yoxdur): vaxtı gələndə soruşulacaq
        val = rules.coerce_field(fid, ext.fields[fid])
        if val is None:
            continue
        old_val = rules.get(state, fid)
        old_type = rules.option_value(state, "site_type") if fid == "site_type" else None
        rules.set_field(state, fid, val, "user")
        changed = True
        if extra and old_val != val and slot not in ("structure", "final"):
            ext.noted.append(f"{f['label']}: {val}")
        if fid == "site_type":
            _apply_site_type(state, old_type)
    if ext.skip and slot != "final":
        changed |= _mark_open(state, slot)
    if ext.skip_rest:  # düymə: qalan bütün səhifələrin məzmunu sonra göndəriləcək
        for p in state.structure.pages:
            if p.content_status == "pending":
                p.content, p.content_status = "", "open"
                changed = True
    if ext.page_ops:
        notes = apply_page_ops(state, ext.page_ops)
        if notes:
            state.structure_confirmed = False
            changed = True
    for cr in ext.custom_requests:
        if cr.title.strip():
            rules.add_custom(state, cr.title, cr.description, cr.page)
            state.structure_confirmed = False
            changed = True
    if ext.structure_confirmed and state.structure.pages:
        state.structure_confirmed = True
        changed = True
    # slotun xüsusi halları
    if (slot.startswith("page:") and text.strip() and not ext.wants_default
            and not (ext.page_ops or ext.custom_requests or ext.skip or ext.skip_rest)):
        page = rules.find_page_by_id(state, slot.split(":", 1)[1])
        if page and page.content_status == "pending":  # cavabın özü səhifənin məzmunudur
            page.content, page.content_status = text.strip()[:800], "answered"
            changed = True
    if slot.startswith("custom:") and not ext.wants_default and text.strip():
        _, cid, qid = slot.split(":")
        item = next((c for c in state.custom_items if c.id == cid), None)
        if item and qid not in item.answers:
            item.answers[qid] = text.strip()[:500]
            changed = True
    if slot.startswith("field:"):
        fid = slot.split(":", 1)[1]
        f = catalog.field(fid)
        if (fid not in state.fields and f["type"] == "text" and not ext.wants_default and text.strip()
                and not ext.noted):  # LLM başqa sahələri çıxarıbsa bütün mətni bu sahəyə yazma (uydurma olar)
            rules.set_field(state, fid, text.strip()[:500], "user")  # mətn sahəsində cavab özü dəyərdir
            changed = True
    rules.ensure_requirements(state)
    return changed


def _deterministic(state: TZState, slot: str, text: str) -> Extraction | None:
    """Chips və dəqiq uyğunluqlar LLM çağırışı olmadan (kvota qənaəti + uydurmasız)."""
    cfg = catalog.questions_cfg()
    txt = text.strip()
    if txt == cfg["skip_chip"] and slot.startswith("field:"):
        return Extraction(skip=True)
    if txt == cfg["custom_default_chip"]:
        return Extraction(wants_default=True)
    if slot.startswith("page:"):
        if txt == cfg["skip_chip"]:
            return Extraction(skip=True)
        if txt == cfg["page_content_question"]["all_later_chip"]:
            return Extraction(skip_rest=True)
    if slot == "structure" and txt == cfg["structure_question"]["chip_ok"]:
        return Extraction(structure_confirmed=True)
    if slot == "structure":
        tpl = catalog.template(rules.option_value(state, "site_type") or "") or {}
        for mid in tpl.get("suggest", []):
            if txt == t("add_chip", title=catalog.module_title(mid)):
                return Extraction(page_ops=[PageOp(op="add", name=catalog.module_title(mid), module_types=[mid])])
    if slot.startswith("field:"):
        fid = slot.split(":", 1)[1]
        f = catalog.field(fid)
        if f.get("skip_chip_label") and txt == f["skip_chip_label"]:
            return Extraction(skip=True)
        if f.get("default_chip_label") and txt == f["default_chip_label"]:
            return Extraction(fields={fid: f["default"]})
        if f["type"] in ("choice", "languages") and catalog.option_by_label(fid, txt):
            return Extraction(fields={fid: txt})
    return None


# ---------- əsas növbə ----------
def _finish(state: TZState, ext: Extraction, changed: bool, notes_ack: str = "") -> TurnResult:
    slot = rules.next_slot(state)
    state.pending_slot = slot
    q, chips, tree = question_for(slot, state)
    warns = [w for w in rules.check_contradictions(state) if w not in state.shown_warnings]
    state.shown_warnings += warns
    ack = _ack(ext, state, notes_ack)
    if ext.noted:  # bir cavabdan çıxarılan əlavə sahələr: müştəri nəyin qeyd olunduğunu görür və düzəldə bilər
        ack += "\n\n" + t("also_noted", items="; ".join(ext.noted))
    reply = f"{ack}\n\n{q}"
    if warns:
        reply = f"{ack}\n\n⚠️ " + "\n⚠️ ".join(warns) + f"\n\n{q}"
    return TurnResult(reply=reply, chips=chips, show_tree=tree or bool(state.structure.pages and slot == "structure"),
                      ready_for_summary=slot == "final", widget=widget_for(slot), why=why_for(slot, state))


def _reask(state: TZState, slot: str, lead: str) -> TurnResult:
    q, chips, tree = question_for(slot, state)
    return TurnResult(reply=f"{lead}\n\n{q}", chips=chips, show_tree=tree, widget=widget_for(slot),
                      why=why_for(slot, state))


def _handle_unknown(state: TZState, slot: str) -> TurnResult:
    """\"Bilmirəm\" cavabı: təxmin YOXDUR. Əvvəl izah + yenidən sual, ikinci dəfə (və sahə icazə verirsə) açıq sual kimi qeyd."""
    if slot.startswith("custom:"):
        _mark_open(state, slot)
        return _finish(state, Extraction(), True)
    n = state.retries.get(slot, 0) + 1
    state.retries[slot] = n
    if slot.startswith("page:"):
        if n >= 2:
            _mark_open(state, slot)
            return _finish(state, Extraction(ack=t("marked_open")), True)
        return _reask(state, slot, t("dont_guess_page", skip=catalog.questions_cfg()["skip_chip"]))
    if slot.startswith("field:"):
        fid = slot.split(":", 1)[1]
        if rules.is_skippable(fid):
            if n >= 2:
                _mark_open(state, slot)
                return _finish(state, Extraction(ack=t("marked_open")), True)
            return _reask(state, slot, t("dont_guess", skip=catalog.questions_cfg()["skip_chip"]))
        return _reask(state, slot, t("dont_guess_required"))
    return _reask(state, slot, t("dont_guess_structure"))


def process_turn(state: TZState, text: str, extractor: Extractor) -> TurnResult:
    set_lang(state.language)
    state.turns += 1
    slot = state.pending_slot or rules.next_slot(state)
    ext = _deterministic(state, slot, text)
    if ext is None:
        q_text, _, _ = question_for(slot, state)
        ext = extractor.extract(Ctx(state=state, text=text, slot=slot, last_question=q_text))
    if ext.wants_default and slot != "final" and not (ext.fields or ext.page_ops or ext.custom_requests):
        return _handle_unknown(state, slot)
    changed = apply_extraction(state, slot, text, ext)
    if changed and ext.page_ops and not ext.ack:
        ext.ack = t("ack_struct")
    if not changed:
        if slot == "final":
            q, chips, _ = question_for("final", state)
            return TurnResult(reply=t("final_more"), chips=chips, ready_for_summary=True)
        state.retries[slot] = state.retries.get(slot, 0) + 1
        fid = slot.split(":", 1)[1] if slot.startswith("field:") else None
        if state.retries[slot] >= MAX_RETRIES and fid and rules.is_skippable(fid):
            _mark_open(state, slot)  # 2 uğursuz cəhd: dəyər uydurulmur, açıq sual kimi qeyd olunur
            ext.ack = t("marked_open")
        else:
            return _reask(state, slot, t("not_understood"))
    return _finish(state, ext, changed)


def after_files(state: TZState, names: list[str]) -> TurnResult:
    """Fayl(lar) yüklənəndən sonra: təsdiq + növbəti sual (məs. loqodan sonra rənglər). Fayl başqa vaxt (📎 menyusu) yüklənibsə eyni sual təkrar verilir."""
    set_lang(state.language)
    rules.ensure_requirements(state)
    return _finish(state, Extraction(ack=t("files_received", names=", ".join(names))), True)


def apply_answers(state: TZState, fields: dict[str, str], page_content: dict[str, str],
                  open_ids: list[str]) -> tuple[list[str], list[str], list[str]]:
    """Xülasədən gələn düzəlişlər: söhbət mətnlərini dəyişmir, yalnız state-i yeniləyir.
    Qaytarır: (yenilənənlər, rədd edilənlər, artıq tətbiq olunmadığına görə silinənlər). Etibarsız dəyər heç vaxt yazılmır."""
    set_lang(state.language)
    notes: list[str] = []
    rejected: list[str] = []

    def label_of(fid: str) -> str:
        return (catalog.field(fid) or {}).get("label", fid)

    for fid in open_ids:
        f = catalog.field(fid)
        if f and rules.is_skippable(fid) and f.get("type") != "file" and rules.field_applicable(fid, state):
            rules.mark_open(state, fid)
            notes.append(f["label"])
        else:
            rejected.append(label_of(fid))
    for fid, raw in fields.items():
        f = catalog.field(fid)
        # sayt növü burada dəyişmir: struktur və səhifə məzmunu ondan asılıdır (söhbətdə dəyişdirilə bilər)
        if (not f or f.get("ask", True) is False or f.get("type") == "file" or fid == "site_type"
                or not rules.field_applicable(fid, state)):
            rejected.append(label_of(fid))
            continue
        if fid in open_ids:
            continue
        val = rules.coerce_field(fid, raw)
        if val is None:
            rejected.append(f["label"])
            continue
        rules.set_field(state, fid, val, "user")
        notes.append(f["label"])
    for pid, text in page_content.items():
        page = rules.find_page_by_id(state, pid)
        if not page:
            rejected.append(pid)
            continue
        val = (text or "").strip()[:800]
        if not val:
            page.content, page.content_status = "", "open"
        else:
            page.content, page.content_status = val, "answered"
        notes.append(page.name)
    rules.ensure_requirements(state)
    dropped = rules.prune_inapplicable(state)
    return notes, rejected, dropped


def after_answers(state: TZState, notes: list[str], dropped: list[str]) -> TurnResult | None:
    """Xülasədəki düzəlişdən sonra: yeni sual açılıbsa (məs. «domen var» seçilib, domen adı lazımdır) onu söhbətə verir,
    əks halda None (xülasədə qalmaq olar)."""
    set_lang(state.language)
    slot = rules.next_slot(state)
    state.pending_slot = slot
    if slot == "final":
        return None
    return _finish(state, Extraction(ack=t("answers_new_questions")), bool(notes or dropped))


def after_edit(state: TZState, notes: list[str]) -> TurnResult:
    """UI-dakı səhifə ağacı düymələrindən (əlavə/sil/dəyiş) sonra: state-i yenilə və növbəti sualı ver."""
    set_lang(state.language)
    if notes:
        state.structure_confirmed = False
    rules.ensure_requirements(state)
    ack = t("after_edit_ok", notes="; ".join(notes)) if notes else t("after_edit_none")
    return _finish(state, Extraction(ack=ack), bool(notes))
