"""Synchronous database wiring for the worker and Alembic.

The worker uses psycopg (sync) so a single-level control flow drives the RQ
job; the API keeps using asyncpg.
"""

from __future__ import annotations

from app.config import Settings
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker


def create_sync_engine(settings: Settings) -> Engine:
    """Build the synchronous engine from the settings' sync URL."""
    url = settings.sync_database_url
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, connect_args=connect_args, pool_pre_ping=not url.startswith("sqlite"))


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Return a synchronous session factory."""
    return sessionmaker(engine, expire_on_commit=False)
