"""API tests: httpx AsyncClient over the app with SQLite + fakeredis."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI
from httpx import AsyncClient

from app.config import Settings
from app.db import get_session
from app.excuses import EXCUSES
from app.main import create_app
from app.metrics import record_render_duration
from app.models import STATUS_DONE, Certificate

PNG_BYTES = b"\x89PNG\r\n\x1a\nfake-png-bytes"


async def _seed_done(app: FastAPI, **overrides: Any) -> Certificate:
    values: dict[str, Any] = {
        "id": "11111111-1111-1111-1111-111111111111",
        "name": "Ada Lovelace",
        "project": "analytical-engine",
        "excuse": "It worked on my machine.",
        "status": STATUS_DONE,
        "serial_number": "WOMM-2026-LGTM-0F3A",
        "notary": "Baroness Ada von Segfault",
        "image_png": PNG_BYTES,
        "issued_at": datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC),
    }
    values.update(overrides)
    certificate = Certificate(**values)
    async with app.state.sessionmaker() as session:
        session.add(certificate)
        await session.commit()
    return certificate


async def test_create_certificate_enqueues_job(client: AsyncClient, app: FastAPI) -> None:
    response = await client.post(
        "/certificates",
        json={"name": "Ada", "project": "engine", "excuse": "Works locally."},
    )

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "queued"
    assert body["job_id"]
    assert len(body["id"]) == 36

    assert app.state.redis.llen(f"rq:queue:{app.state.settings.queue_name}") == 1


async def test_create_certificate_validation(client: AsyncClient) -> None:
    missing = await client.post("/certificates", json={"name": "", "project": "p", "excuse": "e"})
    assert missing.status_code == 422

    blank = await client.post("/certificates", json={"name": "   ", "project": "p", "excuse": "e"})
    assert blank.status_code == 422

    too_long = await client.post(
        "/certificates", json={"name": "x" * 81, "project": "p", "excuse": "e"}
    )
    assert too_long.status_code == 422


async def test_get_certificate_returns_status_json(client: AsyncClient) -> None:
    created = await client.post(
        "/certificates", json={"name": "Ada", "project": "engine", "excuse": "Works locally."}
    )
    certificate_id = created.json()["id"]

    response = await client.get(f"/certificates/{certificate_id}?output=json")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "queued"
    assert body["image_url"] is None


async def test_get_certificate_returns_png_when_done(client: AsyncClient, app: FastAPI) -> None:
    certificate = await _seed_done(app)

    response = await client.get(f"/certificates/{certificate.id}")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content == PNG_BYTES

    metadata = await client.get(f"/certificates/{certificate.id}?output=json")
    assert metadata.json()["image_url"] == f"/certificates/{certificate.id}"
    assert metadata.json()["serial_number"] == "WOMM-2026-LGTM-0F3A"


async def test_get_unknown_certificate_returns_404(client: AsyncClient) -> None:
    response = await client.get("/certificates/does-not-exist?output=json")
    assert response.status_code == 404


async def test_hall_of_shame_lists_done_certificates(client: AsyncClient, app: FastAPI) -> None:
    await _seed_done(app, id="22222222-2222-2222-2222-222222222222", name="Grace")

    response = await client.get("/hall-of-shame")

    assert response.status_code == 200
    entries = response.json()
    assert len(entries) == 1
    assert entries[0]["name"] == "Grace"
    assert entries[0]["project"] == "analytical-engine"


async def test_healthz_is_always_ok(client: AsyncClient) -> None:
    response = await client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_readyz_ok_with_dependencies(client: AsyncClient) -> None:
    response = await client.get("/readyz")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


async def test_readyz_reports_dependency_failure(
    client: AsyncClient, app: FastAPI, monkeypatch: Any
) -> None:
    class BrokenRedis:
        def ping(self) -> None:
            raise ConnectionError("redis is on strike")

    monkeypatch.setattr(app.state, "redis", BrokenRedis())

    response = await client.get("/readyz")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "unready"
    assert any("redis" in problem for problem in body["problems"])


async def test_metrics_reflects_database_and_redis(client: AsyncClient, app: FastAPI) -> None:
    await _seed_done(app)
    record_render_duration(app.state.redis, 150, window=500)

    response = await client.get("/metrics")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    text = response.text
    assert "certificates_issued_total 1.0" in text
    assert "machines_certified_total 1.0" in text
    assert "womm_render_duration_seconds_count 1.0" in text


async def test_create_certificate_returns_503_when_queue_is_down(
    client: AsyncClient, app: FastAPI
) -> None:
    class BrokenQueue:
        def enqueue(self, *_args: Any, **_kwargs: Any) -> None:
            raise ConnectionError("queue is on strike")

    app.state.queue = BrokenQueue()

    response = await client.post(
        "/certificates", json={"name": "Ada", "project": "engine", "excuse": "Works locally."}
    )

    assert response.status_code == 503
    assert "coffee break" in response.json()["detail"]


async def test_unhandled_error_returns_an_excuse(client: AsyncClient, app: FastAPI) -> None:
    async def broken_session() -> Any:
        raise RuntimeError("everything is on fire")

    app.dependency_overrides[get_session] = broken_session

    response = await client.get("/certificates/anything?output=json")

    assert response.status_code == 500
    body = response.json()
    assert body["error"] == "internal_server_error"
    assert body["excuse"] in EXCUSES


async def test_static_front_page_is_served(client: AsyncClient) -> None:
    response = await client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Works On My Machine" in response.text


async def test_lifespan_creates_and_releases_owned_resources(api_settings: Settings) -> None:
    """The production path: no injected engine/redis, so the app owns them."""
    app = create_app(api_settings)

    async with app.router.lifespan_context(app):
        assert app.state.sessionmaker is not None
        assert app.state.queue is not None
        assert app.state.owns_engine is True
        assert app.state.owns_redis is True

    assert app.state.engine is not None
