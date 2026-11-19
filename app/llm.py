"""LLM çıxarışı: LiteLLM (Gemini → Groq fallback) və açarsız işləyən heuristik əvəzedici."""
from __future__ import annotations

import json
import logging
import re
import threading
import time
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Optional, Protocol

from . import catalog, config, i18n, rules
from .schemas import CustomRequest, Extraction, PageOp, TZState

log = logging.getLogger("tz.llm")


class LLMUnavailable(Exception):
    """Bütün provayderlər cəhdlərdən sonra cavab vermədi."""


@dataclass
class Ctx:
    state: TZState
    text: str
    slot: str
    last_question: str


class Extractor(Protocol):
    def extract(self, ctx: Ctx) -> Extraction: ...


# ---------- ortaq köməkçilər ----------
DEFAULT_WORDS = ["bilmirəm", "siz təklif", "tövsiyə edin", "siz seçin", "fərqi yoxdur",
                 "don't know", "dont know", "do not know", "you suggest", "you choose", "doesn't matter",
                 "не знаю", "предложите", "на ваш выбор", "не важно"]
CONFIRM_WORDS = ["uyğundur", "bəli", "hə", "olar", "yaxşıdır", "təsdiq", "ok", "okay", "düzdür", "razıyam",
                 "looks good", "yes", "fine", "good", "approve", "confirm", "agree",
                 "да", "хорошо", "подходит", "согласен", "согласна", "устраивает", "утверждаю",
                 "yoxdur", "heç nə", "no changes", "nothing", "нет", "ничего"]
ADD_WORDS = ["əlavə", "lazımdır", "istəyirəm", "olsun", "istəyirik", "da olsun",
             "add", "want", "need", "include", "also", "добав", "хочу", "нужн", "надо", "необходим"]
REMOVE_WORDS = ["çıxar", "sil", "lazım deyil", "olmasın", "silin",
                "remove", "delete", "without", "no need", "удал", "убер", "не нужн", "без"]


def is_default_text(text: str) -> bool:
    t = catalog.fold(text)
    return any(catalog.kw_in(w, t) for w in DEFAULT_WORDS)


def _any(words: list[str], t: str) -> bool:
    return any(catalog.kw_in(w, t) for w in words)


# ---------- heuristik (açarsız / test) ----------
_LINK_RE = re.compile(
    r"(https?://\S+|www\.\S+|\S+@\S+|\b[\w-]+(?:\.[\w-]+)*\.(?:az|com|org|net|ru|io|info|biz|edu|gov|tr|uk)\b\S*)",
    re.IGNORECASE,
)


def strip_links(text: str) -> str:
    """Linkləri, e-poçtları və domen adlarını mətndən çıxarır (dil/seçim uyğunlaşdırması üçün)."""
    return _LINK_RE.sub(" ", text)


class HeuristicExtractor:
    """LLM yoxdursa: gözlənilən slota cavabı qaydalarla çıxarır. Real LLM qədər ağıllı deyil."""

    def extract(self, ctx: Ctx) -> Extraction:
        ext = Extraction()
        text, slot = ctx.text.strip(), ctx.slot
        t = catalog.fold(text)
        if is_default_text(text):
            ext.wants_default = True
            return ext
        if slot.startswith("field:"):
            fid = slot.split(":", 1)[1]
            f = catalog.field(fid) or {}
            if f.get("type") == "email":
                m = re.search(r"[^@\s]+@[^@\s]+\.[^@\s]{2,}", text)
                if m:
                    ext.fields[fid] = m.group(0)
            elif f.get("type") == "text":
                ext.fields[fid] = text
            else:
                v = rules.coerce_field(fid, text)
                if v:
                    ext.fields[fid] = v
            self._extra_fields(ctx, ext, text, fid)
            return ext
        if slot in ("structure", "final"):
            self._structure(ctx, ext, t, text)
        return ext

    def _extra_fields(self, ctx: Ctx, ext: Extraction, text: str, current: str) -> None:
        """Uzun cavabda açıq deyilən başqa seçim/dil/e-poçt sahələrini də doldur (təxmin yox)."""
        email_src = text  # e-poçt axtarışı üçün orijinal mətn
        text = strip_links(text)  # «atlas.az» kimi domenlər «AZ» dili kimi oxunmasın
        for fid in rules.applicable_fields(ctx.state):
            if fid == current or fid in ext.fields or rules.field_filled(ctx.state, fid):
                continue
            f = catalog.field(fid) or {}
            ftype = f.get("type")
            if ftype in ("choice", "languages"):
                opt = rules.match_option(fid, text) if ftype == "choice" else None
                val = opt["label"] if opt else rules.coerce_field(fid, text)
                if val and (ftype != "languages" or rules.parse_languages(text)):
                    if ftype == "choice" and not opt:
                        continue  # allow_other sərbəst mətnini başqa sahəyə yazma
                    ext.fields[fid] = val
            elif ftype == "email":
                m = re.search(r"[^@\s]+@[^@\s]+\.[^@\s]{2,}", email_src)
                if m:
                    ext.fields[fid] = m.group(0)

    def _structure(self, ctx: Ctx, ext: Extraction, t: str, text: str) -> None:
        if _any(REMOVE_WORDS, t):
            for p in ctx.state.structure.pages:
                if catalog.fold(p.name) in t:
                    ext.page_ops.append(PageOp(op="remove", name=p.name))
            return
        if _any(ADD_WORDS, t):
            mid = catalog.match_module(text)
            if mid:
                ext.page_ops.append(PageOp(op="add", name=catalog.module_title(mid), module_types=[mid]))
            else:
                ext.custom_requests.append(CustomRequest(title=text[:80], description=text[:300]))
            return
        if _any(CONFIRM_WORDS, t):
            ext.structure_confirmed = True
        elif ctx.slot == "structure" and text.strip():
            # strukturda sərbəst yazılan hər şey (təsdiq/silmə olmayan) əlavə tələbi kimi qəbul edilir
            mid = catalog.match_module(text)
            if mid:
                ext.page_ops.append(PageOp(op="add", name=catalog.module_title(mid), module_types=[mid]))
            else:
                ext.custom_requests.append(CustomRequest(title=text[:80], description=text[:300]))


# ---------- provayder statistikası və hər növbənin izi ----------
class LLMStats:
    """Hər model üçün say: hansı provayderin ən çox çökdüyünü görmək üçün (prosesdaxili, yenidən başlayanda sıfırlanır)."""

    def __init__(self):
        self._lock = threading.Lock()
        self._m: dict[str, dict] = {}

    def record(self, model: str, ok: bool, ms: int, err: str = "") -> None:
        with self._lock:
            d = self._m.setdefault(model, {"ok": 0, "fail": 0, "last_error": "", "last_ms": 0})
            d["ok" if ok else "fail"] += 1
            d["last_ms"] = ms
            if err:
                d["last_error"] = err

    def snapshot(self) -> list[dict]:
        with self._lock:
            rows = [{"model": m, **d, "fail_rate": round(d["fail"] / max(1, d["ok"] + d["fail"]), 2)}
                    for m, d in self._m.items()]
        return sorted(rows, key=lambda r: (-r["fail"], r["model"]))

    def reset(self) -> None:
        with self._lock:
            self._m.clear()


STATS = LLMStats()
# bu sorğunun (növbənin) izi: hansı modellər sınandı, hansı cavab verdi. Eyni thread-də oxunur (main.py)
_run: ContextVar[dict | None] = ContextVar("llm_run", default=None)


def begin_run(order: list[str]) -> dict:
    run = {"order": list(order), "tried": [], "answered_by": None}
    _run.set(run)
    return run


def take_run() -> dict | None:
    """Son LLM çağırışının izini qaytarır və təmizləyir (yoxdursa None: məs. chip cavabı LLM-siz keçib)."""
    run = _run.get()
    _run.set(None)
    return run


# ---------- LiteLLM ----------
def _load_prompt() -> str:
    return (config.ROOT / "prompts" / f"{config.PROMPT_VERSION}.md").read_text(encoding="utf-8")


def build_system_prompt(ctx: Ctx) -> str:
    fields = []
    for fid, f in catalog.fields().items():
        if f.get("ask", True) is False or f.get("type") == "file":
            continue
        opts = " / ".join(o["label"] for o in f.get("options", []))
        fields.append(f"- {fid}: {f['label']} | {f['type']} | {opts}")
    mods = "\n".join(f"- {mid}: {m['title']}" for mid, m in catalog.modules().items())
    filled = {fid: fv.value for fid, fv in ctx.state.fields.items()}
    pages = [p.name for p in ctx.state.structure.pages]
    # hazırda tətbiq olunan, hələ cavablanmamış sahələr: LLM bir cavabdan bir neçəsini birdən doldura bilər
    unfilled = [fid for fid in rules.applicable_fields(ctx.state) if not rules.field_filled(ctx.state, fid)
                and (catalog.field(fid) or {}).get("type") != "file"]
    return (_load_prompt()
            .replace("{{LAST_QUESTION}}", ctx.last_question)
            .replace("{{PENDING_SLOT}}", ctx.slot)
            .replace("{{LANG_NAME}}", i18n.LANG_NAMES.get(ctx.state.language, "Azərbaycan"))
            .replace("{{FIELDS}}", "\n".join(fields))
            .replace("{{MODULES}}", mods)
            .replace("{{PAGES}}", json.dumps(pages, ensure_ascii=False))
            .replace("{{UNFILLED}}", ", ".join(unfilled) or "—")
            .replace("{{FILLED}}", json.dumps(filled, ensure_ascii=False)))


# bu açarları LLM təyin edə bilməz: yalnız mühərrik/düymələr
ENGINE_ONLY = ("skip", "skip_rest", "noted")


def parse_extraction(raw: str) -> Extraction:
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw)
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("JSON obyekti gözlənilirdi")
    return Extraction.model_validate({k: v for k, v in data.items() if k in Extraction.model_fields and k not in ENGINE_ONLY})


# Bu xətalar təkrar cəhdlə düzəlmir: modeli cooldown-a qoy, dərhal növbətiyə keç
_PERMANENT = ("AuthenticationError", "PermissionDeniedError", "NotFoundError", "BadRequestError")


class LiteLLMExtractor:
    """Modellər zənciri: 503/429/timeout → növbəti model. Xəta verən model `cooldown` saniyə atlanır."""

    def __init__(self, models: list[str], timeout: int, cooldown: int = 60):
        self.models, self.timeout, self.cooldown = models, timeout, cooldown
        self._down: dict[str, float] = {}  # model -> yenidən cəhd vaxtı (monotonic)

    def _available(self) -> list[str]:
        now = time.monotonic()
        live = [m for m in self.models if self._down.get(m, 0) <= now]
        return live or list(self.models)  # hamısı cooldown-dadırsa yenə də hamısını yoxla

    def extract(self, ctx: Ctx) -> Extraction:
        import litellm  # tənbəl import: açarsız rejimdə lazım deyil

        litellm.drop_params = True  # model dəstəkləmədiyi parametri (response_format) səssizcə atsın
        messages = [
            {"role": "system", "content": build_system_prompt(ctx)},
            {"role": "user", "content": f"<musteri_mesaji>\n{ctx.text}\n</musteri_mesaji>"},
        ]
        last: Optional[Exception] = None
        order = self._available()
        run = begin_run(order)
        for model in order:
            for attempt in range(2):
                t0 = time.monotonic()
                try:
                    resp = litellm.completion(model=model, messages=messages, temperature=0.1,
                                              response_format={"type": "json_object"}, timeout=self.timeout)
                    ext = parse_extraction(resp.choices[0].message.content)
                    ms = int((time.monotonic() - t0) * 1000)
                    self._down.pop(model, None)
                    STATS.record(model, True, ms)
                    run["tried"].append({"model": model, "attempt": attempt, "outcome": "ok", "ms": ms})
                    run["answered_by"] = model
                    return ext
                except Exception as e:  # noqa: BLE001 - provayder xətaları müxtəlifdir
                    last = e
                    name = type(e).__name__
                    ms = int((time.monotonic() - t0) * 1000)
                    STATS.record(model, False, ms, name)
                    run["tried"].append({"model": model, "attempt": attempt, "outcome": name, "ms": ms})
                    log.warning("llm_fail model=%s attempt=%s err=%s ms=%s", model, attempt, name, ms,
                                extra={"ctx": {"model": model, "attempt": attempt, "error": name, "ms": ms}})
                    if name in _PERMANENT:  # yanlış açar/ad: təkrarın mənası yoxdur
                        self._down[model] = time.monotonic() + 600
                        break
                    if name in ("JSONDecodeError", "ValidationError", "ValueError"):
                        continue  # model pis JSON verdi: eyni modeli bir də yoxla
                    time.sleep(0.3)  # 503/429/timeout: qısa fasilə
                    self._down[model] = time.monotonic() + self.cooldown
                    break  # overloaded modeli təkrarlama, növbətiyə keç
        raise LLMUnavailable(str(last))


class ResilientExtractor:
    """LLM zənciri hamısı çökəndə söhbət dayanmasın: sadə qaydalarla davam edir (503 əvəzinə)."""

    def __init__(self, primary: Extractor, fallback: Extractor):
        self.primary, self.fallback = primary, fallback

    def extract(self, ctx: Ctx) -> Extraction:
        try:
            return self.primary.extract(ctx)
        except LLMUnavailable:
            log.error("llm_all_failed: heuristic fallback")
            run = _run.get()
            if run is not None:
                run["answered_by"] = "heuristic"
            return self.fallback.extract(ctx)


def get_extractor() -> Extractor:
    if config.MOCK_LLM or not config.HAS_LLM_KEY:
        return HeuristicExtractor()
    return ResilientExtractor(
        LiteLLMExtractor(config.LLM_MODELS, config.LLM_TIMEOUT, config.LLM_COOLDOWN), HeuristicExtractor())


def llm_mode() -> str:
    return "heuristic" if (config.MOCK_LLM or not config.HAS_LLM_KEY) else "litellm"
