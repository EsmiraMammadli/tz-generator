"""Rate limit, PII maskalama və strukturlu JSON log."""
from __future__ import annotations

import json
import logging
import re
import threading
import time
from collections import defaultdict, deque

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE = re.compile(r"(?<!\w)\+?\d[\d\s()\-]{7,}\d")


def mask_pii(text: str) -> str:
    """E-poçt və telefonu loglara/analitikaya düz mətn göndərməmək üçün maskalayır."""
    text = _EMAIL.sub(lambda m: m.group(0)[0] + "***@***", text)
    return _PHONE.sub("[telefon]", text)


class RateLimiter:
    """Sadə sürüşən pəncərə (prosesdaxili). Çoxprosesli deploy-da Redis və ya proxy səviyyəsi lazımdır."""

    def __init__(self, limit: int, window: float = 60.0):
        self.limit, self.window = limit, window
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str) -> float:
        """0 qaytarırsa icazə var; əks halda neçə saniyə gözləmək lazımdır."""
        now = time.monotonic()
        with self._lock:
            q = self._hits[key]
            while q and now - q[0] > self.window:
                q.popleft()
            if len(q) >= self.limit:
                return max(1.0, self.window - (now - q[0]))
            q.append(now)
            return 0.0


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {"ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"), "level": record.levelname,
                   "logger": record.name, "msg": mask_pii(record.getMessage())}
        extra = getattr(record, "ctx", None)
        if extra:
            payload.update(extra)
        return json.dumps(payload, ensure_ascii=False)


def setup_logging() -> None:
    h = logging.StreamHandler()
    h.setFormatter(JsonFormatter())
    root = logging.getLogger("tz")
    root.handlers[:] = [h]
    root.setLevel(logging.INFO)
    root.propagate = False
