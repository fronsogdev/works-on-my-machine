"""unique serial numbers

Revision ID: 0002_unique_serial_number
Revises: 0001_create_certificates
Create Date: 2026-01-02 00:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_unique_serial_number"
down_revision: str | None = "0001_create_certificates"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CONSTRAINT_NAME = "uq_certificates_serial_number"


def upgrade() -> None:
    # Postgres (and SQLite) both allow multiple NULLs under a UNIQUE constraint,
    # so in-flight rows with no serial yet are unaffected.
    op.create_unique_constraint(CONSTRAINT_NAME, "certificates", ["serial_number"])


def downgrade() -> None:
    op.drop_constraint(CONSTRAINT_NAME, "certificates", type_="unique")
