"""AI interview completion, interview preferences, slot bookings, projection flags."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260404_0012"
down_revision: str | None = "20260403_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ai_interview_question_sets",
        sa.Column("candidate_completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "applications",
        sa.Column("interview_preferences_submitted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "application_commission_projections",
        sa.Column("ai_interview_completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "application_commission_projections",
        sa.Column("interview_preferences_submitted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "interview_slot_bookings",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("slot_date", sa.Date(), nullable=False),
        sa.Column("time_range_code", sa.String(length=16), nullable=False),
        sa.Column("sort_order", sa.SmallInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slot_date", "time_range_code", name="uq_interview_slot_slot_time"),
    )
    op.create_index("ix_interview_slot_bookings_app", "interview_slot_bookings", ["application_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_interview_slot_bookings_app", table_name="interview_slot_bookings")
    op.drop_table("interview_slot_bookings")
    op.drop_column("application_commission_projections", "interview_preferences_submitted_at")
    op.drop_column("application_commission_projections", "ai_interview_completed_at")
    op.drop_column("applications", "interview_preferences_submitted_at")
    op.drop_column("ai_interview_question_sets", "candidate_completed_at")
