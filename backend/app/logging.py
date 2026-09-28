"""Logging setup with masking of personal data and credentials.

Masking is a safety net, not a licence: do not log personal data or secrets on purpose.
"""

import logging
import re
from typing import Final

_EMAIL_RE: Final = re.compile(
    r"\b([A-Za-z0-9._%+-])[A-Za-z0-9._%+-]*@([A-Za-z0-9.-]+\.[A-Za-z]{2,})\b"
)
# 13-19 digits, optionally separated by spaces or dashes: card numbers (PAN).
_PAN_RE: Final = re.compile(r"\b(?:\d[ -]?){9,15}(\d{4})\b")
_PHONE_RE: Final = re.compile(r"(?<![\w+])\+\d[\d ()-]{7,}(\d{2})\b")
_BEARER_RE: Final = re.compile(r"(?i)\b(bearer)\s+[A-Za-z0-9._~+/=-]+")
_SECRET_KV_RE: Final = re.compile(
    r"(?i)\b(password|passwd|secret|token|api[_-]?key|authorization|signature)"
    r"(\"?\s*[:=]\s*\"?)(?:bearer\s+|basic\s+)?[^\s\",}&]+"
)
_URL_CREDENTIALS_RE: Final = re.compile(r"(://[^:/@\s]+):[^@/\s]+@")


def mask_sensitive(text: str) -> str:
    """Mask emails, card numbers, phones, tokens and passwords in free text."""
    text = _URL_CREDENTIALS_RE.sub(r"\1:***@", text)
    text = _SECRET_KV_RE.sub(r"\1\2***", text)
    text = _BEARER_RE.sub(r"\1 ***", text)
    text = _EMAIL_RE.sub(r"\1***@\2", text)
    text = _PAN_RE.sub(r"****\1", text)
    return _PHONE_RE.sub(r"+***\1", text)


class MaskingFormatter(logging.Formatter):
    """Formats the record as usual, then masks the final string (message, args and traceback)."""

    def format(self, record: logging.LogRecord) -> str:
        return mask_sensitive(super().format(record))


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(MaskingFormatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
    # Route uvicorn logs through the same masking handler.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers = []
        uvicorn_logger.propagate = True
