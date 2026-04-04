"""is_archived on application_commission_projections for history vs active board."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260406_0014"
down_revision: str | None = "20260405_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "application_commission_projections",
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.create_index(
        "ix_comm_proj_archived",
        "application_commission_projections",
        ["is_archived"],
        unique=False,
    )
    op.execute(
        """
        UPDATE application_commission_projections p
        SET is_archived = a.is_archived
        FROM applications a
        WHERE p.application_id = a.id
        """
    )
    op.alter_column(
        "application_commission_projections",
        "is_archived",
        server_default=None,
    )


def downgrade() -> None:
    op.drop_index("ix_comm_proj_archived", table_name="application_commission_projections")
    op.drop_column("application_commission_projections", "is_archived")
