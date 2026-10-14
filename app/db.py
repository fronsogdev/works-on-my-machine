"""Async database wiring for the API.

The engine is created once at app startup and stored on ``app.state``; request
handlers get a session through the ``get_session`` dependency.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.config import Settings


def create_engine(settings: Settings) -> AsyncEngine:
    """Build the async engine.

    In-memory SQLite (used by the API tests) needs a shared connection pool so
    that every session sees the same database.
    """
    if settings.is_sqlite:
        return create_async_engine(
            settings.database_url,
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )
    return create_async_engine(settings.database_url, pool_pre_ping=True)


def create_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Return a session factory bound to the engine."""
    return async_sessionmaker(engine, expire_on_commit=False)


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """FastAPI dependency yielding a session from the app-wide factory."""
    maker: async_sessionmaker[AsyncSession] = request.app.state.sessionmaker
    async with maker() as session:
        yield session
