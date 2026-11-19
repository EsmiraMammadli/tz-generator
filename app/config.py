"""Konfiqurasiya yalnız env dəyişənləri ilə."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

try:  # .env faylını avtomatik oxu (mövcud env dəyişənlərini əvəz etmir)
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:  # python-dotenv yoxdursa yalnız sistem env-i işləyir
    pass


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default


DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{ROOT / 'storage' / 'app.db'}")
FILES_DIR = Path(os.getenv("FILES_DIR", ROOT / "storage" / "files"))

# Sənəd başlığı (agentlik loqosu və adı). Loqo yoxdursa yalnız ad yazılır.
AGENCY_NAME = os.getenv("AGENCY_NAME", "AI TZ Generatoru")
AGENCY_TAGLINE = os.getenv("AGENCY_TAGLINE", "")
_logo = Path(os.getenv("AGENCY_LOGO_PATH", ROOT / "static" / "agency-logo.png"))
AGENCY_LOGO_PATH = _logo if _logo.is_file() else None
AGENCY_COLOR = os.getenv("AGENCY_COLOR", "1E2A5E").lstrip("#")

# Admin səhifəsi: boşdursa /admin 404 qaytarır (gizli qalır)
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")

# Təsdiqlənmiş TZ bildirişi (uğursuzluq sənədi pozmur)
NOTIFY_EMAIL = os.getenv("NOTIFY_EMAIL", "")
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = _int("SMTP_PORT", 587)
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", "")
SMTP_TLS = os.getenv("SMTP_TLS", "1") != "0"
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# LiteLLM model adları tez-tez dəyişir: rəsmi sənədlərdən yoxlayın.
# Hər model öz provayderinin açarını tələb edir; açarı olmayan modellər avtomatik atlanır.
# Sıra = prioritet: biri 503/429/timeout verəndə növbətiyə keçilir.
PROVIDER_KEYS = {
    "gemini": "GEMINI_API_KEY",
    "groq": "GROQ_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "mistral": "MISTRAL_API_KEY",
    "cerebras": "CEREBRAS_API_KEY",
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
}
DEFAULT_MODELS = ",".join([
    "gemini/gemini-2.5-flash",
    "gemini/gemini-2.5-flash-lite",
    "groq/llama-3.3-70b-versatile",
    "cerebras/llama-3.3-70b",
    "mistral/mistral-small-latest",
    "openrouter/meta-llama/llama-3.3-70b-instruct:free",
    "groq/llama-3.1-8b-instant",
    "openai/gpt-4o-mini",
    "anthropic/claude-haiku-4-5",
    "deepseek/deepseek-chat",
])


def _has_key(model: str) -> bool:
    env = PROVIDER_KEYS.get(model.split("/", 1)[0])
    return bool(env and os.getenv(env))


_ALL_MODELS = [m.strip() for m in os.getenv("LLM_MODELS", DEFAULT_MODELS).split(",") if m.strip()]
# yalnız açarı olan modellər
LLM_MODELS = [m for m in _ALL_MODELS if _has_key(m)]
LLM_TIMEOUT = _int("LLM_TIMEOUT", 20)
LLM_COOLDOWN = _int("LLM_COOLDOWN", 60)  # xəta verən model bu qədər saniyə atlanır
# MOCK_LLM=1 məcburi heuristik rejim; açar yoxdursa avtomatik heuristik rejimdir
MOCK_LLM = os.getenv("MOCK_LLM", "") == "1"
HAS_LLM_KEY = bool(LLM_MODELS)

MAX_MESSAGE_CHARS = _int("MAX_MESSAGE_CHARS", 4000)
# Yalnız etibarlı reverse proxy (Render, Fly və s.) arxasında 1 qoyun; əks halda X-Forwarded-For saxtalaşdırıla bilər
TRUST_PROXY = os.getenv("TRUST_PROXY", "") == "1"
RATE_LIMIT_PER_MIN = _int("RATE_LIMIT_PER_MIN", 20)
RETENTION_DAYS = _int("RETENTION_DAYS", 30)
PROMPT_VERSION = os.getenv("PROMPT_VERSION", "extract_v3")
