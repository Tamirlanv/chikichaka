"""admissions domain: stage artifacts, extractions, analysis

Revision ID: 20250328_0002
Revises: 20250328_0001
Create Date: 2025-03-28

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20250328_0002"
down_revision: str | None = "20250328_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("sha256_hex", sa.String(length=64), nullable=True))
    op.create_index("ix_documents_sha256", "documents", ["sha256_hex"], unique=False)

    op.create_table(
        "document_extractions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sha256_hex", sa.String(length=64), nullable=False),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column("extraction_status", sa.String(length=32), nullable=False),
        sa.Column("extractor_version", sa.String(length=32), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_document_extractions_document", "document_extractions", ["document_id"], unique=False)

    op.add_column(
        "documents",
        sa.Column("primary_extraction_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_documents_primary_extraction",
        "documents",
        "document_extractions",
        ["primary_extraction_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "initial_screening_results",
        sa.Column("application_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("screening_status", sa.String(length=64), nullable=False),
        sa.Column("missing_items", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("issues_found", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("screening_notes", sa.Text(), nullable=True),
        sa.Column("screening_result", sa.String(length=64), nullable=True),
        sa.Column("screening_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("application_id"),
    )

    op.create_table(
        "application_review_snapshot",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("review_status", sa.String(length=64), nullable=False),
        sa.Column("review_packet", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("summary_by_block", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("authenticity_risk_flag", sa.Boolean(), nullable=False),
        sa.Column("consistency_flags", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("reviewer_notes_internal", sa.Text(), nullable=True),
        sa.Column("ai_summary_draft", sa.Text(), nullable=True),
        sa.Column("explainability_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("application_id", name="uq_application_review_snapshot_app"),
    )

    op.create_table(
        "interview_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_index", sa.Integer(), nullable=False),
        sa.Column("interview_status", sa.String(length=64), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("interview_mode", sa.String(length=64), nullable=True),
        sa.Column("location_or_link", sa.String(length=512), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("transcript", sa.Text(), nullable=True),
        sa.Column("follow_up_questions", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("interview_summary_draft", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_interview_sessions_application", "interview_sessions", ["application_id"], unique=False)

    op.create_table(
        "admission_decisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("final_decision_status", sa.String(length=64), nullable=False),
        sa.Column("decision_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("candidate_message", sa.Text(), nullable=True),
        sa.Column("internal_note", sa.Text(), nullable=True),
        sa.Column("next_steps", sa.Text(), nullable=True),
        sa.Column("issued_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("audit_reference", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["issued_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("application_id", name="uq_admission_decisions_app"),
    )

    op.create_table(
        "text_analysis_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("block_key", sa.String(length=64), nullable=False),
        sa.Column("source_kind", sa.String(length=32), nullable=False),
        sa.Column("source_document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("model", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("dimensions", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("explanations", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("flags", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_document_id"], ["documents.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_text_analysis_runs_application", "text_analysis_runs", ["application_id"], unique=False)
    op.create_index(
        "ix_text_analysis_runs_block",
        "text_analysis_runs",
        ["application_id", "block_key"],
        unique=False,
    )

    op.create_table(
        "analysis_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_type", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_analysis_jobs_app_status", "analysis_jobs", ["application_id", "status"], unique=False)

    op.add_column("committee_reviews", sa.Column("committee_review_status", sa.String(length=64), nullable=True))
    op.add_column("committee_reviews", sa.Column("recommendation_band", sa.String(length=64), nullable=True))
    op.add_column("committee_reviews", sa.Column("recommendation_reasoning", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("committee_reviews", "recommendation_reasoning")
    op.drop_column("committee_reviews", "recommendation_band")
    op.drop_column("committee_reviews", "committee_review_status")

    op.drop_index("ix_analysis_jobs_app_status", table_name="analysis_jobs")
    op.drop_table("analysis_jobs")

    op.drop_index("ix_text_analysis_runs_block", table_name="text_analysis_runs")
    op.drop_index("ix_text_analysis_runs_application", table_name="text_analysis_runs")
    op.drop_table("text_analysis_runs")

    op.drop_table("admission_decisions")

    op.drop_index("ix_interview_sessions_application", table_name="interview_sessions")
    op.drop_table("interview_sessions")

    op.drop_table("application_review_snapshot")

    op.drop_table("initial_screening_results")

    op.drop_constraint("fk_documents_primary_extraction", "documents", type_="foreignkey")
    op.drop_column("documents", "primary_extraction_id")

    op.drop_index("ix_document_extractions_document", table_name="document_extractions")
    op.drop_table("document_extractions")

    op.drop_index("ix_documents_sha256", table_name="documents")
    op.drop_column("documents", "sha256_hex")
