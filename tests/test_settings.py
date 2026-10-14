"""Settings and URL-mapping unit tests."""

from __future__ import annotations

import pytest
from app.config import Settings, to_sync_url


def test_defaults_are_localhost_friendly() -> None:
    settings = Settings()
    assert settings.database_url.startswith("postgresql+asyncpg://")
    assert "localhost" in settings.database_url or "@localhost" in settings.database_url
    assert settings.redis_url.startswith("redis://")
    assert settings.queue_name == "certificates"
    assert settings.render_duration_window > 0


def test_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WOMM_DATABASE_URL", "postgresql+asyncpg://user:pw@db:5432/womm")
    monkeypatch.setenv("WOMM_REDIS_URL", "rediss://user:pw@cache:6379/0")
    settings = Settings()
    assert settings.database_url == "postgresql+asyncpg://user:pw@db:5432/womm"
    assert settings.redis_url == "rediss://user:pw@cache:6379/0"
    assert settings.sync_database_url == "postgresql+psycopg://user:pw@db:5432/womm"


def test_to_sync_url_maps_drivers() -> None:
    assert (
        to_sync_url("postgresql+asyncpg://womm:womm@localhost:5432/womm")
        == "postgresql+psycopg://womm:womm@localhost:5432/womm"
    )
    assert to_sync_url("sqlite+aiosqlite:///:memory:") == "sqlite:///:memory:"
    assert to_sync_url("postgresql://already:sync@db/womm") == "postgresql://already:sync@db/womm"


def test_is_sqlite_flag() -> None:
    assert Settings(database_url="sqlite+aiosqlite:///:memory:").is_sqlite is True
    assert Settings(database_url="postgresql+asyncpg://db/womm").is_sqlite is False
