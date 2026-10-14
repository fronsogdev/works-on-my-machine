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
    # batch mode recreates the table on SQLite (which cannot ALTER a constraint
    # in place) and issues a plain ALTER TABLE on Postgres. NULL serial numbers
    # stay allowed on both, so in-flight rows are unaffected.
    with op.batch_alter_table("certificates", recreate="auto") as batch_op:
        batch_op.create_unique_constraint(CONSTRAINT_NAME, ["serial_number"])


def downgrade() -> None:
    with op.batch_alter_table("certificates", recreate="auto") as batch_op:
        batch_op.drop_constraint(CONSTRAINT_NAME, type_="unique")
