"""create certificates table

Revision ID: 0001_create_certificates
Revises:
Create Date: 2026-01-01 00:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001_create_certificates"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "certificates",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("project", sa.String(length=120), nullable=False),
        sa.Column("excuse", sa.String(length=280), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("job_id", sa.String(length=64), nullable=True),
        sa.Column("serial_number", sa.String(length=64), nullable=True),
        sa.Column("notary", sa.String(length=120), nullable=True),
        sa.Column("render_duration_ms", sa.Integer(), nullable=True),
        sa.Column("image_png", sa.LargeBinary(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_certificates_status", "certificates", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_certificates_status", table_name="certificates")
    op.drop_table("certificates")
