"""RQ job: render a certificate and persist the result.

Runs in the worker process with synchronous SQLAlchemy and Redis. The database
is the single source of truth for issued-certificate counts; Redis only holds
the bounded render-duration window used by the API's histogram.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime

import redis
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings, get_settings
from app.logging_setup import get_logger
from app.metrics import record_render_duration
from app.models import (
    STATUS_DONE,
    STATUS_FAILED,
    STATUS_PROCESSING,
    Certificate,
)
from worker.db import create_session_factory, create_sync_engine
from worker.renderer import choose_notary, generate_serial_number, render_certificate_png

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None
_redis: redis.Redis | None = None


def _session_factory_for(settings: Settings) -> sessionmaker[Session]:
    global _engine, _session_factory
    if _session_factory is None:
        _engine = create_sync_engine(settings)
        _session_factory = create_session_factory(_engine)
    return _session_factory


def _redis_for(settings: Settings) -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = redis.Redis.from_url(settings.redis_url)
    return _redis


def reset_connections() -> None:
    """Drop cached connections (used by tests to isolate runs)."""
    global _engine, _session_factory, _redis
    if _engine is not None:
        _engine.dispose()
    if _redis is not None:
        _redis.close()
    _engine = None
    _session_factory = None
    _redis = None


def render_certificate(certificate_id: str) -> None:
    """RQ entrypoint: render one certificate and update its row."""
    settings = get_settings()
    factory = _session_factory_for(settings)
    connection = _redis_for(settings)
    log = get_logger(certificate_id=certificate_id)

    with factory() as session:
        certificate = session.get(Certificate, certificate_id)
        if certificate is None:
            log.error("certificate_not_found")
            return

        certificate.status = STATUS_PROCESSING
        session.commit()

        issued_at = datetime.now(UTC)
        serial_number = generate_serial_number(issued_at.year)
        notary = choose_notary()

        started = time.perf_counter()
        try:
            png = render_certificate_png(
                name=certificate.name,
                project=certificate.project,
                excuse=certificate.excuse,
                serial_number=serial_number,
                notary=notary,
                issued_at=issued_at,
            )
        except Exception:
            certificate.status = STATUS_FAILED
            session.commit()
            log.exception("certificate_render_failed")
            raise

        duration_ms = int((time.perf_counter() - started) * 1000)
        certificate.status = STATUS_DONE
        certificate.serial_number = serial_number
        certificate.notary = notary
        certificate.image_png = png
        certificate.render_duration_ms = duration_ms
        certificate.issued_at = issued_at
        session.commit()

    record_render_duration(connection, duration_ms, settings.render_duration_window)
    log.info("certificate_rendered", duration_ms=duration_ms, serial_number=serial_number)
