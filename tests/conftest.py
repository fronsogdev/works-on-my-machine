"""Shared fixtures.

The API test suite runs entirely in-memory: SQLite (aiosqlite) for the database
and fakeredis for the queue. No Docker, Postgres or Redis is required.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator

import fakeredis
import pytest
from app.config import Settings
from app.db import create_engine
from app.main import create_app
from app.models import Base
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine


@pytest.fixture
def api_settings() -> Settings:
    """Settings pointing at in-memory SQLite."""
    return Settings(
        database_url="sqlite+aiosqlite:///:memory:",
        redis_url="redis://localhost:6379/0",
    )


@pytest.fixture
def fake_redis() -> Iterator[fakeredis.FakeRedis]:
    """A fakeredis connection shared by the app and assertions."""
    connection = fakeredis.FakeRedis()
    yield connection
    connection.close()


@pytest.fixture
async def engine(api_settings: Settings) -> AsyncIterator[AsyncEngine]:
    """An async SQLite engine with the schema created."""
    engine = create_engine(api_settings)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
def app(api_settings: Settings, engine: AsyncEngine, fake_redis: fakeredis.FakeRedis) -> FastAPI:
    """The FastAPI app wired to the in-memory engine and fakeredis."""
    return create_app(api_settings, engine=engine, redis_conn=fake_redis)


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    """An httpx client that runs the app's lifespan around each test."""
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=transport, base_url="http://testserver") as http_client,
    ):
        yield http_client
