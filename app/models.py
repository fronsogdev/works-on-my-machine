"""SQLAlchemy models shared by the API and the worker.

Kept in ``app/`` so the worker can import a single definition rather than
duplicating a schema. ``app/__init__.py`` stays empty, so importing this module
does not pull in FastAPI.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, LargeBinary, String, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Certificate lifecycle states.
STATUS_QUEUED = "queued"
STATUS_PROCESSING = "processing"
STATUS_DONE = "done"
STATUS_FAILED = "failed"

SERIAL_NUMBER_UNIQUE_CONSTRAINT = "uq_certificates_serial_number"


class Base(DeclarativeBase):
    """Declarative base for all tables."""


class Certificate(Base):
    """A single issued (or in-flight) certificate."""

    __tablename__ = "certificates"
    __table_args__ = (UniqueConstraint("serial_number", name=SERIAL_NUMBER_UNIQUE_CONSTRAINT),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    project: Mapped[str] = mapped_column(String(120))
    excuse: Mapped[str] = mapped_column(String(280))
    status: Mapped[str] = mapped_column(String(20), default=STATUS_QUEUED, index=True)
    job_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    serial_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    notary: Mapped[str | None] = mapped_column(String(120), nullable=True)
    render_duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    image_png: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
