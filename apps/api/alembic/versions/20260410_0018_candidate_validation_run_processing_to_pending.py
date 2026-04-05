"""Normalize legacy candidate_validation_runs.overall_status 'processing' to 'pending'."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260410_0018"
down_revision: str | None = "20260409_0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE candidate_validation_runs SET overall_status = 'pending' "
            "WHERE overall_status = 'processing'"
        )
    )


def downgrade() -> None:
    # Cannot safely restore which rows were 'processing' vs intentionally 'pending'.
    pass
