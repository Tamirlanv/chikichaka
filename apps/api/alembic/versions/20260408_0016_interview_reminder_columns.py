"""Commission interview email reminder (request + sent timestamps on interview_sessions)."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260408_0016"
down_revision: str | None = "20260407_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "interview_sessions",
        sa.Column("reminder_requested_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "interview_sessions",
        sa.Column("reminder_sent_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("interview_sessions", "reminder_sent_at")
    op.drop_column("interview_sessions", "reminder_requested_at")
