"""structlog configuration: one JSON line per event, configured once per process."""

from __future__ import annotations

import logging
import sys
from typing import Any, TextIO

import structlog

_configured = False


def configure_logging(level: str = "INFO", *, stream: TextIO | None = None) -> None:
    """Configure structlog to emit JSON and route stdlib logging through it.

    Idempotent for the default stream: repeat calls are no-ops so importing the
    app in tests does not reconfigure logging on every app factory call. Passing
    an explicit ``stream`` (used by tests) reconfigures the output target.
    """
    global _configured
    numeric_level = logging.getLevelName(level.upper())
    if not isinstance(numeric_level, int):
        numeric_level = logging.INFO

    if _configured and stream is None:
        structlog.contextvars.clear_contextvars()
        return

    output = stream if stream is not None else sys.stdout
    logging.basicConfig(format="%(message)s", stream=output, level=numeric_level)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(numeric_level),
        logger_factory=structlog.PrintLoggerFactory(file=output),
        cache_logger_on_first_use=True,
    )
    _configured = True


def get_logger(**initial_values: Any) -> structlog.stdlib.BoundLogger:
    """Return a bound structlog logger."""
    return structlog.get_logger(**initial_values)  # type: ignore[no-any-return]
