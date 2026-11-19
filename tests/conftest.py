import os
import tempfile

_tmp = tempfile.mkdtemp(prefix="tz_test_")
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL") or f"sqlite:///{_tmp}/test.db"
os.environ["FILES_DIR"] = f"{_tmp}/files"
os.environ["MOCK_LLM"] = "1"
os.environ["RATE_LIMIT_PER_MIN"] = "1000"


def _pdf_available() -> bool:
    """WeasyPrint Windows-da GTK kitabxanası olmadan işləmir: PDF testləri orada atlanır (DOCX təsir olunmur)."""
    try:
        import weasyprint  # noqa: F401
        return True
    except (ImportError, OSError):
        return False


PDF_OK = _pdf_available()
