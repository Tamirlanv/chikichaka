"""Candidate activity events for engagement scoring."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260411_0019"
down_revision: str | None = "20260410_0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "candidate_activity_events",
        sa.Column("application_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("candidate_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("stage", sa.String(length=64), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["applications.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["candidate_user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_candidate_activity_app_time",
        "candidate_activity_events",
        ["application_id", "occurred_at"],
        unique=False,
    )
    op.create_index(
        "ix_candidate_activity_event_type",
        "candidate_activity_events",
        ["event_type"],
        unique=False,
    )
    op.create_index(
        "ix_candidate_activity_events_application_id",
        "candidate_activity_events",
        ["application_id"],
        unique=False,
    )
    op.create_index(
        "ix_candidate_activity_events_candidate_user_id",
        "candidate_activity_events",
        ["candidate_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_candidate_activity_user_time",
        "candidate_activity_events",
        ["candidate_user_id", "occurred_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_candidate_activity_user_time", table_name="candidate_activity_events")
    op.drop_index("ix_candidate_activity_events_candidate_user_id", table_name="candidate_activity_events")
    op.drop_index("ix_candidate_activity_events_application_id", table_name="candidate_activity_events")
    op.drop_index("ix_candidate_activity_event_type", table_name="candidate_activity_events")
    op.drop_index("ix_candidate_activity_app_time", table_name="candidate_activity_events")
    op.drop_table("candidate_activity_events")
