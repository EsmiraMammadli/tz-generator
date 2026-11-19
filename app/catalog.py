"""YAML data fayllarının yüklənməsi və mətn uyğunlaşdırma köməkçiləri."""
from __future__ import annotations

import re
from functools import lru_cache
from typing import Any, Optional

import yaml

from . import i18n
from .config import ROOT

DATA = ROOT / "data"
_AZ = str.maketrans("əıöüşçğ", "eiouscg")


def _load(name: str) -> Any:
    with open(DATA / name, encoding="utf-8") as f:
        return yaml.safe_load(f)


@lru_cache
def _modules_file_l(lang: str) -> dict:
    return i18n.loc(_load("modules.yaml"), lang)


@lru_cache
def _templates_l(lang: str) -> dict:
    return i18n.loc(_load("templates.yaml"), lang)


@lru_cache
def _questions_l(lang: str) -> dict:
    return i18n.loc(_load("questions.yaml"), lang)


# cari dilə (i18n.cur()) görə lokallaşdırılmış data
def _modules_file() -> dict:
    return _modules_file_l(i18n.cur())


def _templates() -> dict:
    return _templates_l(i18n.cur())


def _questions() -> dict:
    return _questions_l(i18n.cur())


def reload() -> None:
    for f in (_modules_file_l, _templates_l, _questions_l):
        f.cache_clear()


# ---------- mətn normallaşdırma ----------
def norm(s: str) -> str:
    s = str(s).replace("İ", "i").replace("I", "ı").lower()
    s = re.sub(r"[^\w\s+@.\-]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def fold(s: str) -> str:
    """Diakritiksiz forma: telefonda ə/ı/ş yazmayanlar üçün."""
    return norm(s).translate(_AZ)


def kw_in(kw: str, text_folded: str) -> bool:
    k = fold(kw)
    if " " in k or len(k) <= 2:
        return re.search(rf"(?<!\w){re.escape(k)}(?!\w)", text_folded) is not None
    return any(t == k or (len(k) >= 3 and t.startswith(k)) for t in text_folded.split())


# ---------- modullar ----------
def pricing() -> dict:
    return _modules_file()["pricing"]


def base_requirements() -> dict:
    return _modules_file()["base_requirements"]


def heavy_modules() -> set[str]:
    return set(_modules_file().get("heavy_modules", []))


def analytics_requirements() -> dict:
    return _modules_file().get("analytics_requirements", {})


def modules() -> dict[str, dict]:
    return {m["id"]: m for m in _modules_file()["modules"]}


def module(mid: str) -> Optional[dict]:
    return modules().get(mid)


def module_title(mid: str) -> str:
    m = module(mid)
    return m["title"] if m else mid


def match_module(text: str) -> Optional[str]:
    """Mətndə modul açar sözü varsa onun id-sini qaytarır (ən uzun açar söz qalib)."""
    t = fold(text)
    best, best_len = None, 0
    for mid, m in modules().items():
        for kw in m.get("kw", []):
            if kw_in(kw, t) and len(kw) > best_len:
                best, best_len = mid, len(kw)
    return best


# ---------- şablonlar ----------
def template(site_type_value: str) -> Optional[dict]:
    return _templates().get(site_type_value)


# ---------- sahələr ----------
def flow() -> list[str]:
    return _questions()["flow"]


def fields() -> dict[str, dict]:
    return _questions()["fields"]


def field(fid: str) -> Optional[dict]:
    return fields().get(fid)


def option_by_label(fid: str, label: Any) -> Optional[dict]:
    f = field(fid) or {}
    if not isinstance(label, str):
        return None
    n = fold(label)
    for o in f.get("options", []):
        if fold(o["label"]) == n:
            return o
    return None


def questions_cfg() -> dict:
    return _questions()
