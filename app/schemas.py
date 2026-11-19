"""Pydantic sxemlər: TZ state, səhifə/modul modeli, LLM çıxarışı və API müqaviləsi."""
from __future__ import annotations

import uuid
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

# user=müştəri dedi, template=şablon, calculated=qaydalarla hesablanıb (saat/qiymət/platforma),
# open=müştəri bilmir, dəqiqləşdirilməlidir, inferred=köhnə sessiyalar üçün (artıq yeni təxmin yaradılmır)
Source = Literal["user", "inferred", "template", "calculated", "open"]


def new_id() -> str:
    return uuid.uuid4().hex[:8]


# ---------- Struktur (Page / Module modeli) ----------
class Module(BaseModel):
    type: str  # kataloq id-si, ya da "custom"
    description: str = ""
    source: Source = "template"
    kind: Literal["standard", "custom"] = "standard"
    estimated_hours: Optional[float] = None  # custom üçün həmişə None


class Page(BaseModel):
    id: str = Field(default_factory=new_id)
    name: str
    kind: Literal["standard", "custom"] = "standard"
    purpose: str = ""
    modules: list[Module] = Field(default_factory=list)
    source: Source = "template"
    # səhifənin məzmunu (müştəri dediyi). pending=hələ soruşulmayıb, open=müştəri bilmir/sonra verəcək
    content: str = ""
    content_status: Literal["pending", "answered", "open"] = "pending"


class SiteStructure(BaseModel):
    pages: list[Page] = Field(default_factory=list)
    global_features: list[Module] = Field(default_factory=list)


# ---------- Sessiya state-i ----------
class FieldValue(BaseModel):
    value: Any
    source: Source
    confidence: float = 1.0


class CustomItem(BaseModel):
    id: str = Field(default_factory=new_id)
    title: str
    description: str = ""
    page: Optional[str] = None
    answers: dict[str, str] = Field(default_factory=dict)


FileKind = Literal["logo", "guide", "reference"]


class FileMeta(BaseModel):
    """Yüklənmiş fayl (loqo variantı, brend bələdçisi, dizayn nümunəsi). Fayl diskdə id ilə saxlanılır, ad yalnız göstərmək üçündür."""
    id: str = Field(default_factory=new_id)
    kind: FileKind
    filename: str
    ext: Literal["png", "jpg", "pdf"]
    size: int = 0


class TZState(BaseModel):
    language: str = "az"
    fields: dict[str, FieldValue] = Field(default_factory=dict)
    structure: SiteStructure = Field(default_factory=SiteStructure)
    custom_items: list[CustomItem] = Field(default_factory=list)
    structure_confirmed: bool = False
    structure_shown: bool = False
    page_intro_shown: bool = False
    skipped: list[str] = Field(default_factory=list)
    files: list[FileMeta] = Field(default_factory=list)
    pending_slot: Optional[str] = None
    retries: dict[str, int] = Field(default_factory=dict)
    shown_warnings: list[str] = Field(default_factory=list)
    turns: int = 0


# ---------- LLM çıxarışı ----------
class PageOp(BaseModel):
    op: Literal["add", "remove", "rename", "add_module", "remove_module"]
    name: str
    new_name: Optional[str] = None
    purpose: Optional[str] = None
    module_types: list[str] = Field(default_factory=list)


class CustomRequest(BaseModel):
    title: str
    description: str = ""
    page: Optional[str] = None


class Extraction(BaseModel):
    ack: str = ""
    fields: dict[str, Any] = Field(default_factory=dict)
    wants_default: bool = False  # müştəri "bilmirəm" dedi (heç vaxt təxminlə doldurulmur)
    skip: bool = False  # müştəri açıq şəkildə "developer ilə dəqiqləşdirəcəm" seçdi
    skip_rest: bool = False  # "bütün səhifələrin məzmununu sonra göndərəcəm" (yalnız düymə ilə)
    structure_confirmed: Optional[bool] = None
    page_ops: list[PageOp] = Field(default_factory=list)
    custom_requests: list[CustomRequest] = Field(default_factory=list)
    # mühərrikin doldurduğu (LLM-dən gəlmir): cavabdan çıxarılan əlavə sahələr «label: dəyər» formasında
    noted: list[str] = Field(default_factory=list, exclude=True)


# ---------- API müqaviləsi ----------
class CreateSessionIn(BaseModel):
    consent: bool
    language: str = "az"


class MessageIn(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


class AnswersIn(BaseModel):
    """Xülasə ekranından sahə və səhifə məzmununun redaktəsi (söhbətə qayıtmadan)."""
    fields: dict[str, str] = Field(default_factory=dict)
    page_content: dict[str, str] = Field(default_factory=dict)
    open: list[str] = Field(default_factory=list)  # açıq sual kimi qeyd olunacaq sahə id-ləri


class FeedbackIn(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: str = Field(default="", max_length=1000)


class LogoIn(BaseModel):
    filename: str = Field(min_length=1, max_length=120)
    data: str = Field(min_length=1, max_length=3_000_000)  # base64


class FileIn(LogoIn):
    kind: FileKind = "logo"


class FilesIn(BaseModel):
    files: list[FileIn] = Field(min_length=1, max_length=6)


class PageOpIn(BaseModel):
    ops: list[PageOp] = Field(min_length=1, max_length=20)


class TurnResult(BaseModel):
    reply: str
    chips: list[str] = Field(default_factory=list)
    show_tree: bool = False
    ready_for_summary: bool = False
    widget: Optional[str] = None  # "logo" | "colors": UI-da fayl/rəng seçici göstərir
    why: str = ""  # «niyə soruşuruq» qısa izahı (söhbətdə sualın altında göstərilir)
