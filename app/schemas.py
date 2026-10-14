"""Request/response schemas for the certificate API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CertificateRequest(BaseModel):
    """Payload accepted by ``POST /certificates``."""

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=80, description="Who is certified.")
    project: str = Field(min_length=1, max_length=120, description="What works, allegedly.")
    excuse: str = Field(min_length=1, max_length=280, description="The official reason.")


class CertificateStatus(BaseModel):
    """JSON representation of a certificate's current state."""

    id: str
    status: str
    name: str
    project: str
    excuse: str
    serial_number: str | None = None
    notary: str | None = None
    job_id: str | None = None
    created_at: datetime | None = None
    issued_at: datetime | None = None
    image_url: str | None = None


class CertificateCreated(BaseModel):
    """Returned by ``POST /certificates``."""

    id: str
    status: str
    job_id: str | None = None


class HallOfShameEntry(BaseModel):
    """One row of the hall of shame."""

    name: str
    project: str
    excuse: str
    serial_number: str | None = None
    issued_at: datetime | None = None
