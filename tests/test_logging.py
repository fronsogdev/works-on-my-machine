"""Logging tests: JSON emission, structured context, and the 500 handler log."""

from __future__ import annotations

import io
import json
import sys
from typing import Any

import structlog
import structlog.testing
from fastapi import FastAPI
from httpx import AsyncClient

from app.db import get_session
from app.excuses import EXCUSES
from app.logging_setup import configure_logging, get_logger


def test_configure_logging_emits_structured_json() -> None:
    stream = io.StringIO()
    configure_logging("INFO", stream=stream)

    get_logger().info("certificate_requested", certificate_id="abc", project="engine")

    payload = json.loads(stream.getvalue().strip().splitlines()[-1])
    assert payload["event"] == "certificate_requested"
    assert payload["certificate_id"] == "abc"
    assert payload["project"] == "engine"
    assert payload["level"] == "info"
    assert "timestamp" in payload

    # Restore the default output target for the rest of the session.
    configure_logging("INFO", stream=sys.stdout)


def test_configure_logging_is_idempotent() -> None:
    configure_logging("INFO")
    configure_logging("INFO")
    get_logger().info("still logging after a second configure")


def test_get_logger_binds_structured_context() -> None:
    with structlog.testing.capture_logs(processors=[structlog.processors.add_log_level]) as logs:
        get_logger(request_id="abc").info("bound", project="engine")

    assert len(logs) == 1
    assert logs[0]["event"] == "bound"
    assert logs[0]["request_id"] == "abc"
    assert logs[0]["project"] == "engine"
    assert logs[0]["level"] == "info"


async def test_unhandled_error_logs_and_returns_an_excuse(
    client: AsyncClient, app: FastAPI
) -> None:
    async def broken_session() -> Any:
        raise RuntimeError("everything is on fire")

    app.dependency_overrides[get_session] = broken_session

    with structlog.testing.capture_logs(processors=[structlog.processors.add_log_level]) as logs:
        response = await client.get("/certificates/anything?output=json")

    assert response.status_code == 500
    assert response.json()["excuse"] in EXCUSES

    events = [entry for entry in logs if entry["event"] == "unhandled_error"]
    assert len(events) == 1
    assert events[0]["path"] == "/certificates/anything"
    assert events[0]["method"] == "GET"
    assert events[0]["level"] == "error"
