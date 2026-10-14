"""Worker task unit tests: real renderer, real SQLite file, fakeredis."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import fakeredis
import pytest
import worker.tasks as tasks
from app.config import Settings
from app.metrics import read_render_durations
from app.models import STATUS_DONE, STATUS_FAILED, Base, Certificate
from sqlalchemy.orm import Session, sessionmaker
from worker.db import create_session_factory, create_sync_engine
from worker.tasks import render_certificate, reset_connections


@pytest.fixture
def worker_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[tuple[Settings, sessionmaker[Session], fakeredis.FakeRedis]]:
    settings = Settings(database_url=f"sqlite+aiosqlite:///{tmp_path / 'worker.db'}")
    engine = create_sync_engine(settings)
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    connection = fakeredis.FakeRedis()

    reset_connections()
    monkeypatch.setattr(tasks, "get_settings", lambda: settings)
    monkeypatch.setattr(tasks, "_redis_for", lambda _settings: connection)

    yield settings, factory, connection

    engine.dispose()
    connection.close()
    reset_connections()


def _insert(factory: sessionmaker[Session], **values: Any) -> None:
    with factory() as session:
        session.add(Certificate(**values))
        session.commit()


def test_render_certificate_persists_png_and_duration(
    worker_env: tuple[Settings, sessionmaker[Session], fakeredis.FakeRedis],
) -> None:
    _, factory, connection = worker_env
    _insert(factory, id="cert-1", name="Ada", project="engine", excuse="Works locally.")

    render_certificate("cert-1")

    with factory() as session:
        certificate = session.get(Certificate, "cert-1")
        assert certificate is not None
        assert certificate.status == STATUS_DONE
        assert certificate.image_png is not None
        assert certificate.image_png.startswith(b"\x89PNG\r\n\x1a\n")
        assert certificate.serial_number
        assert certificate.notary
        assert certificate.issued_at is not None
        assert certificate.render_duration_ms is not None
        assert certificate.render_duration_ms >= 0

    assert len(read_render_durations(connection)) == 1


def test_render_certificate_ignores_unknown_id(
    worker_env: tuple[Settings, sessionmaker[Session], fakeredis.FakeRedis],
) -> None:
    _, _, connection = worker_env

    render_certificate("does-not-exist")

    assert read_render_durations(connection) == []


def test_render_failure_marks_certificate_failed(
    worker_env: tuple[Settings, sessionmaker[Session], fakeredis.FakeRedis],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, factory, connection = worker_env
    _insert(factory, id="cert-2", name="Grace", project="compiler", excuse="Works locally.")

    def explode(**_kwargs: Any) -> bytes:
        raise RuntimeError("out of pixels")

    monkeypatch.setattr(tasks, "render_certificate_png", explode)

    with pytest.raises(RuntimeError):
        render_certificate("cert-2")

    with factory() as session:
        certificate = session.get(Certificate, "cert-2")
        assert certificate is not None
        assert certificate.status == STATUS_FAILED
        assert certificate.image_png is None

    assert read_render_durations(connection) == []
