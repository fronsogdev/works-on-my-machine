"""Integration test: real Postgres via testcontainers.

Runs the full enqueue -> render -> fetch loop. Skips cleanly (with a visible
reason) when Docker is unavailable, so ``make test`` still passes on a machine
without it.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import fakeredis
import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from rq import Queue, SimpleWorker

import worker.tasks as tasks
from app.config import Settings, get_settings
from app.db import create_engine
from app.main import create_app

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def postgres_urls() -> Iterator[tuple[str, str]]:
    """Start a Postgres container, or skip when Docker is not available."""
    try:
        from testcontainers.community.postgres import PostgresContainer

        container = PostgresContainer("postgres:16-alpine")
        container.start()
    except Exception as exc:  # noqa: BLE001 - any startup failure means "skip"
        pytest.skip(f"Docker/Postgres unavailable: {exc}")

    try:
        yield (
            container.get_connection_url(driver="asyncpg"),
            container.get_connection_url(driver="psycopg"),
        )
    finally:
        container.stop()


async def test_full_enqueue_render_fetch_loop(
    postgres_urls: tuple[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async_url, _sync_url = postgres_urls
    monkeypatch.setenv("WOMM_DATABASE_URL", async_url)
    get_settings.cache_clear()

    alembic_config = Config(str(REPO_ROOT / "migrations" / "alembic.ini"))
    command.upgrade(alembic_config, "head")

    settings = Settings(database_url=async_url)
    connection = fakeredis.FakeRedis()
    engine = create_engine(settings)

    tasks.reset_connections()
    monkeypatch.setattr(tasks, "get_settings", lambda: settings)
    monkeypatch.setattr(tasks, "_redis_for", lambda _settings: connection)

    app = create_app(settings, engine=engine, redis_conn=connection)
    transport = ASGITransport(app=app, raise_app_exceptions=False)

    try:
        async with (
            app.router.lifespan_context(app),
            AsyncClient(transport=transport, base_url="http://testserver") as client,
        ):
            created = await client.post(
                "/certificates",
                json={
                    "name": "Ada Lovelace",
                    "project": "analytical-engine",
                    "excuse": "It worked on my machine.",
                },
            )
            assert created.status_code == 202
            certificate_id = created.json()["id"]

            # Dequeue and run the real RQ job in-process (no fork).
            queue = Queue(settings.queue_name, connection=connection)
            SimpleWorker([queue], connection=connection).work(burst=True)

            image = await client.get(f"/certificates/{certificate_id}")
            assert image.status_code == 200
            assert image.headers["content-type"] == "image/png"
            assert image.content.startswith(b"\x89PNG\r\n\x1a\n")

            hall = await client.get("/hall-of-shame")
            assert hall.status_code == 200
            assert hall.json()[0]["serial_number"]

            metrics = await client.get("/metrics")
            assert "certificates_issued_total 1.0" in metrics.text
            assert "womm_render_duration_seconds_count 1.0" in metrics.text
    finally:
        await engine.dispose()
        connection.close()
        tasks.reset_connections()
        get_settings.cache_clear()
        os.environ.pop("WOMM_DATABASE_URL", None)
