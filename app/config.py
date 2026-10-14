"""Application configuration.

Values are read from the environment with a ``WOMM_`` prefix, falling back to
localhost defaults that match the local compose stack. Nothing here holds a
secret; real deployments inject the URLs through the platform's secret store.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


def to_sync_url(url: str) -> str:
    """Map an async SQLAlchemy URL to the equivalent sync (psycopg) URL.

    The API uses asyncpg; the worker and Alembic use a synchronous driver. The
    two URLs differ only in the driver segment.
    """
    if url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
    if url.startswith("sqlite+aiosqlite://"):
        return url.replace("sqlite+aiosqlite://", "sqlite://", 1)
    return url


class Settings(BaseSettings):
    """Runtime settings shared by the API, worker and migrations."""

    model_config = SettingsConfigDict(
        env_prefix="WOMM_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "postgresql+asyncpg://womm:womm@localhost:5432/womm"
    redis_url: str = "redis://localhost:6379/0"
    queue_name: str = "certificates"
    log_level: str = "INFO"

    # Number of most recent render durations the worker keeps in Redis for the
    # /metrics histogram. This is a bounded, honest window, not a lifetime sum.
    render_duration_window: int = 500

    # RQ job timeout in seconds; rendering is fast, so this is generous.
    job_timeout: int = 120

    @property
    def sync_database_url(self) -> str:
        """Synchronous database URL for the worker and Alembic."""
        return to_sync_url(self.database_url)

    @property
    def is_sqlite(self) -> bool:
        """True when running against SQLite (used by the API test suite)."""
        return self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings (cached)."""
    return Settings()
