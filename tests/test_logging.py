"""Logging configuration unit tests."""

from __future__ import annotations

from app.logging_setup import configure_logging, get_logger


def test_configure_logging_is_idempotent() -> None:
    configure_logging("INFO")
    configure_logging("INFO")
    get_logger().info("logging is configured once")


def test_get_logger_binds_context() -> None:
    logger = get_logger(request_id="abc")
    assert logger is not None
