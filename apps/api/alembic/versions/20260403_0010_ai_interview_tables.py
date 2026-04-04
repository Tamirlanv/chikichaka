"""ai interview question sets and answers

Revision ID: 20260403_0010
Revises: 20260402_0009
Create Date: 2026-04-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260403_0010"
down_revision: str | None = "20260402_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_interview_question_sets",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("questions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("generated_from_signals", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["approved_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("application_id", name="uq_ai_interview_question_sets_app"),
    )
    op.create_index("ix_ai_interview_qs_app", "ai_interview_question_sets", ["application_id"])
    op.create_index("ix_ai_interview_qs_status", "ai_interview_question_sets", ["status"])

    op.create_table(
        "ai_interview_answers",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("question_id", sa.String(length=64), nullable=False),
        sa.Column("answer_text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("application_id", "question_id", name="uq_ai_interview_answer_app_q"),
    )
    op.create_index("ix_ai_interview_answers_app", "ai_interview_answers", ["application_id"])


def downgrade() -> None:
    op.drop_index("ix_ai_interview_answers_app", table_name="ai_interview_answers")
    op.drop_table("ai_interview_answers")
    op.drop_index("ix_ai_interview_qs_status", table_name="ai_interview_question_sets")
    op.drop_index("ix_ai_interview_qs_app", table_name="ai_interview_question_sets")
    op.drop_table("ai_interview_question_sets")
