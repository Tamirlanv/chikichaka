"""Interview preference window columns; per-application slot uniqueness (not global booking)."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260407_0015"
down_revision: str | None = "20260406_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("uq_interview_slot_slot_time", "interview_slot_bookings", type_="unique")
    op.create_unique_constraint(
        "uq_interview_slot_app_date_time",
        "interview_slot_bookings",
        ["application_id", "slot_date", "time_range_code"],
    )

    op.add_column(
        "applications",
        sa.Column("interview_preference_window_opened_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "applications",
        sa.Column("interview_preference_window_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "applications",
        sa.Column("interview_preference_window_status", sa.String(length=64), nullable=True),
    )

    op.add_column(
        "application_commission_projections",
        sa.Column("interview_preference_window_opened_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "application_commission_projections",
        sa.Column("interview_preference_window_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "application_commission_projections",
        sa.Column("interview_preference_window_status", sa.String(length=64), nullable=True),
    )

    # Backfill: submitted preferences → submitted window (historical)
    op.execute(
        """
        UPDATE applications a
        SET
            interview_preference_window_status = 'candidate_preferences_submitted',
            interview_preference_window_opened_at = a.interview_preferences_submitted_at - interval '1 hour',
            interview_preference_window_expires_at = a.interview_preferences_submitted_at
        WHERE a.interview_preferences_submitted_at IS NOT NULL
          AND a.interview_preference_window_status IS NULL
        """
    )

    # Backfill: commission already scheduled final interview
    op.execute(
        """
        UPDATE applications a
        SET
            interview_preference_window_status = 'interview_scheduled',
            interview_preference_window_opened_at = sub.first_sched - interval '1 hour',
            interview_preference_window_expires_at = sub.first_sched
        FROM (
            SELECT application_id, min(scheduled_at) AS first_sched
            FROM interview_sessions
            WHERE scheduled_at IS NOT NULL
            GROUP BY application_id
        ) sub
        WHERE a.id = sub.application_id
          AND a.interview_preference_window_status IS NULL
        """
    )

    # Backfill: AI completed, no prefs row yet — awaiting or expired 1h window from completion
    op.execute(
        """
        UPDATE applications a
        SET
            interview_preference_window_opened_at = q.candidate_completed_at,
            interview_preference_window_expires_at = q.candidate_completed_at + interval '1 hour',
            interview_preference_window_status = CASE
                WHEN q.candidate_completed_at + interval '1 hour' < now() THEN 'candidate_preferences_expired'
                ELSE 'awaiting_candidate_preferences'
            END
        FROM ai_interview_question_sets q
        WHERE q.application_id = a.id
          AND q.candidate_completed_at IS NOT NULL
          AND a.interview_preferences_submitted_at IS NULL
          AND a.interview_preference_window_status IS NULL
          AND NOT EXISTS (
              SELECT 1 FROM interview_sessions s
              WHERE s.application_id = a.id AND s.scheduled_at IS NOT NULL
          )
        """
    )

    op.execute(
        """
        UPDATE application_commission_projections p
        SET
            interview_preference_window_opened_at = a.interview_preference_window_opened_at,
            interview_preference_window_expires_at = a.interview_preference_window_expires_at,
            interview_preference_window_status = a.interview_preference_window_status
        FROM applications a
        WHERE p.application_id = a.id
        """
    )


def downgrade() -> None:
    op.drop_constraint("uq_interview_slot_app_date_time", "interview_slot_bookings", type_="unique")
    op.create_unique_constraint(
        "uq_interview_slot_slot_time",
        "interview_slot_bookings",
        ["slot_date", "time_range_code"],
    )

    op.drop_column("application_commission_projections", "interview_preference_window_status")
    op.drop_column("application_commission_projections", "interview_preference_window_expires_at")
    op.drop_column("application_commission_projections", "interview_preference_window_opened_at")

    op.drop_column("applications", "interview_preference_window_status")
    op.drop_column("applications", "interview_preference_window_expires_at")
    op.drop_column("applications", "interview_preference_window_opened_at")
