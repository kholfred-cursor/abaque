"""Tests for structured logging, masking and the access-log middleware."""

from __future__ import annotations

import json
import logging
import sys
from typing import Any

import httpx
import pytest
from fastapi import FastAPI

from app.core.logging import JsonFormatter, setup_logging
from app.core.middleware import AccessLogMiddleware


def _format(message: str, *args: Any, exc: bool = False, **extra: Any) -> dict[str, Any]:
    exc_info = None
    if exc:
        try:
            raise ValueError("boom for bob@example.com")
        except ValueError:
            exc_info = sys.exc_info()
    record = logging.LogRecord("t", logging.INFO, __file__, 1, message, args, exc_info)
    for key, value in extra.items():
        setattr(record, key, value)
    return dict(json.loads(JsonFormatter().format(record)))


def test_message_patterns_are_masked() -> None:
    jwt_like = "eyJ" + "a" * 20 + "." + "b" * 20 + "." + "c" * 20
    data = _format("user %s token %s hex %s", "bob@example.com", jwt_like, "f" * 40)
    assert "bob@example.com" not in data["message"]
    assert jwt_like not in data["message"]
    assert "f" * 40 not in data["message"]
    assert data["level"] == "INFO"


def test_exceptions_are_masked() -> None:
    data = _format("failure", exc=True)
    assert "ValueError" in data["exception"]
    assert "bob@example.com" not in data["exception"]


def test_extra_fields_are_kept_and_masked() -> None:
    data = _format("request", method="GET", path="/x/bob@example.com", status_code=200)
    assert data["method"] == "GET"
    assert data["status_code"] == 200
    assert "bob@example.com" not in data["path"]


def test_setup_logging_installs_json_handler() -> None:
    setup_logging()
    root = logging.getLogger()
    assert len(root.handlers) == 1
    assert isinstance(root.handlers[0].formatter, JsonFormatter)
    assert logging.getLogger("uvicorn.access").level == logging.CRITICAL


async def test_access_log_never_contains_query_string(caplog: pytest.LogCaptureFixture) -> None:
    app = FastAPI()

    @app.get("/ping")
    async def ping() -> dict[str, str]:
        return {"ok": "yes"}

    app.add_middleware(AccessLogMiddleware)
    caplog.set_level(logging.INFO, logger="app.access")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/ping?token=secret-value")
    assert response.status_code == 200
    record = next(r for r in caplog.records if r.name == "app.access")
    assert record.getMessage().startswith("GET /ping 200")
    assert "secret-value" not in record.getMessage()
    assert "token" not in record.getMessage()
