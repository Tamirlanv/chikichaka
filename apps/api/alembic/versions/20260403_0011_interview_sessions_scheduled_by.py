"""Add scheduled_by_user_id to interview_sessions for commission board scope."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "20260403_0011"
down_revision: str | None = "20260403_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "interview_sessions",
        sa.Column("scheduled_by_user_id", UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_interview_sessions_scheduled_by_user",
        "interview_sessions",
        "users",
        ["scheduled_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_interview_sessions_scheduled_by_user", "interview_sessions", type_="foreignkey")
    op.drop_column("interview_sessions", "scheduled_by_user_id")
