"""AI interview resolution summary JSONB on question sets."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260405_0013"
down_revision: str | None = "20260404_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ai_interview_question_sets",
        sa.Column("resolution_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "ai_interview_question_sets",
        sa.Column("resolution_summary_error", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("ai_interview_question_sets", "resolution_summary_error")
    op.drop_column("ai_interview_question_sets", "resolution_summary")
