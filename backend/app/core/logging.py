"""Structured JSON logging with sensitive data masking.

Masking rules:
- Keys matched by substring (case-insensitive) against a deny list.
- String values scanned for patterns (emails, JWTs, long hex strings).
- Masking is recursive: dicts, lists, and exception tracebacks are processed.
- Timestamp uses record.created, not formatting time.
"""

from __future__ import annotations

import json
import logging
import re
import sys
import traceback
from datetime import UTC, datetime
from typing import Any

_SENSITIVE_KEY_SUBSTRINGS = (
    "password",
    "token",
    "refresh",
    "access",
    "csrf",
    "secret",
    "email",
    "fingerprint",
    "authorization",
    "credential",
    "cookie",
    "hash",
)

_SENSITIVE_PATTERNS = [
    re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"),
    re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
    re.compile(r"\b[0-9a-fA-F]{32,}\b"),
]

_MASK = "***"


def _is_sensitive_key(key: str) -> bool:
    lower = key.lower()
    return any(sub in lower for sub in _SENSITIVE_KEY_SUBSTRINGS)


def _mask_value(value: str) -> str:
    result = value
    for pattern in _SENSITIVE_PATTERNS:
        result = pattern.sub(_MASK, result)
    return result


def _mask_any(value: Any) -> Any:
    if isinstance(value, dict):
        return _mask_dict(value)
    if isinstance(value, list):
        return [_mask_any(item) for item in value]
    if isinstance(value, str):
        return _mask_value(value)
    return value


def _mask_dict(data: dict[str, Any]) -> dict[str, Any]:
    masked: dict[str, Any] = {}
    for key, value in data.items():
        if _is_sensitive_key(key):
            masked[key] = _MASK
        else:
            masked[key] = _mask_any(value)
    return masked


def _mask_exception(exc_info: Any) -> str | None:
    if not exc_info or not exc_info[1]:
        return None
    raw = "".join(traceback.format_exception(*exc_info))
    return _mask_value(raw)


class JsonFormatter(logging.Formatter):
    """Structured JSON formatter with sensitive data masking."""

    def format(self, record: logging.LogRecord) -> str:
        log_data: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": _mask_value(record.getMessage()),
        }

        if record.exc_info and record.exc_info[1]:
            log_data["exception"] = _mask_exception(record.exc_info)

        for key in ("request_id", "method", "path", "status_code", "duration_ms"):
            value = getattr(record, key, None)
            if value is not None:
                log_data[key] = _mask_value(value) if isinstance(value, str) else value

        return json.dumps(_mask_dict(log_data), ensure_ascii=False)


def setup_logging() -> None:
    """Configure structured logging for the application."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)

    # uvicorn access logs replaced by AccessLogMiddleware
    logging.getLogger("uvicorn.access").setLevel(logging.CRITICAL)
    logging.getLogger("uvicorn.error").setLevel(logging.WARNING)
    logging.getLogger("pymongo").setLevel(logging.WARNING)
