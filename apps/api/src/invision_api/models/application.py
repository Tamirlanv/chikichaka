import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, foreign, mapped_column, relationship

from invision_api.db.base import Base
from invision_api.models.enums import (
    ApplicationStage,
    ApplicationState,
    StageActorType,
    VerificationStatus,
)
from invision_api.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class CandidateProfile(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "candidate_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    first_name: Mapped[str] = mapped_column(String(128), nullable=False)
    last_name: Mapped[str] = mapped_column(String(128), nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="candidate_profile")
    applications: Mapped[list["Application"]] = relationship(back_populates="candidate_profile")


class Application(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "applications"
    __table_args__ = (
        Index("ix_applications_candidate_state", "candidate_profile_id", "state"),
        Index("ix_applications_stage", "current_stage"),
        Index("ix_applications_submitted_at", "submitted_at"),
        Index(
            "uq_one_active_application_per_candidate",
            "candidate_profile_id",
            unique=True,
            postgresql_where=text("is_archived = false"),
        ),
    )

    candidate_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidate_profiles.id", ondelete="CASCADE"), nullable=False
    )
    state: Mapped[str] = mapped_column(
        String(64), default=ApplicationState.draft.value, nullable=False
    )
    current_stage: Mapped[str] = mapped_column(
        String(64), default=ApplicationStage.application.value, nullable=False
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    locked_after_submit: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    candidate_profile: Mapped["CandidateProfile"] = relationship(back_populates="applications")
    section_states: Mapped[list["ApplicationSectionState"]] = relationship(
        back_populates="application", cascade="all, delete-orphan"
    )
    stage_history: Mapped[list["ApplicationStageHistory"]] = relationship(
        back_populates="application",
        cascade="all, delete-orphan",
        order_by="ApplicationStageHistory.entered_at",
    )
    education_records: Mapped[list["EducationRecord"]] = relationship(
        back_populates="application", cascade="all, delete-orphan"
    )
    internal_test_answers: Mapped[list["InternalTestAnswer"]] = relationship(
        back_populates="application", cascade="all, delete-orphan"
    )
    documents: Mapped[list["Document"]] = relationship(back_populates="application", cascade="all, delete-orphan")
    ai_reviews: Mapped[list["AIReviewMetadata"]] = relationship(
        back_populates="application", cascade="all, delete-orphan"
    )
    committee_reviews: Mapped[list["CommitteeReview"]] = relationship(
        back_populates="application", cascade="all, delete-orphan"
    )
    initial_screening_result: Mapped["InitialScreeningResult | None"] = relationship(
        back_populates="application", uselist=False, cascade="all, delete-orphan"
    )
    application_review_snapshot: Mapped["ApplicationReviewSnapshot | None"] = relationship(
        back_populates="application", uselist=False, cascade="all, delete-orphan"
    )
    interview_sessions: Mapped[list["InterviewSession"]] = relationship(
        back_populates="application", cascade="all, delete-orphan"
    )
    admission_decision: Mapped["AdmissionDecision | None"] = relationship(
        back_populates="application", uselist=False, cascade="all, delete-orphan"
    )
    text_analysis_runs: Mapped[list["TextAnalysisRun"]] = relationship(
        back_populates="application", cascade="all, delete-orphan"
    )
    analysis_jobs: Mapped[list["AnalysisJob"]] = relationship(
        back_populates="application", cascade="all, delete-orphan"
    )


class ApplicationSectionState(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "application_section_states"
    __table_args__ = (UniqueConstraint("application_id", "section_key", name="uq_app_section"),)

    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False
    )
    section_key: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    is_complete: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    last_saved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    application: Mapped["Application"] = relationship(back_populates="section_states")


class ApplicationStageHistory(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "application_stage_history"
    __table_args__ = (Index("ix_stage_history_app_entered", "application_id", "entered_at"),)

    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False
    )
    from_stage: Mapped[str | None] = mapped_column(String(64), nullable=True)
    to_stage: Mapped[str] = mapped_column(String(64), nullable=False)
    entered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    exited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    actor_type: Mapped[str] = mapped_column(String(32), default=StageActorType.system.value, nullable=False)
    candidate_visible_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    internal_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    application: Mapped["Application"] = relationship(back_populates="stage_history")


class EducationRecord(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "education_records"

    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False
    )
    institution_name: Mapped[str] = mapped_column(String(255), nullable=False)
    degree_or_program: Mapped[str | None] = mapped_column(String(255), nullable=True)
    field_of_study: Mapped[str | None] = mapped_column(String(255), nullable=True)
    start_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    end_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    application: Mapped["Application"] = relationship(back_populates="education_records")


class InternalTestQuestion(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "internal_test_questions"
    __table_args__ = (Index("ix_questions_category", "category"),)

    category: Mapped[str] = mapped_column(String(64), nullable=False)
    question_type: Mapped[str] = mapped_column(String(32), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    answers: Mapped[list["InternalTestAnswer"]] = relationship(back_populates="question")


class InternalTestAnswer(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "internal_test_answers"
    __table_args__ = (UniqueConstraint("application_id", "question_id", name="uq_app_question_answer"),)

    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("internal_test_questions.id", ondelete="CASCADE"), nullable=False
    )
    text_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    selected_options: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True)
    saved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_finalized: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    application: Mapped["Application"] = relationship(back_populates="internal_test_answers")
    question: Mapped["InternalTestQuestion"] = relationship(back_populates="answers")


class Document(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "documents"
    __table_args__ = (
        Index("ix_documents_app_type", "application_id", "document_type"),
        Index("ix_documents_verification", "verification_status"),
        Index("ix_documents_sha256", "sha256_hex"),
    )

    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False
    )
    uploaded_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    document_type: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    verification_status: Mapped[str] = mapped_column(
        String(32), default=VerificationStatus.pending.value, nullable=False
    )
    sha256_hex: Mapped[str | None] = mapped_column(String(64), nullable=True)
    primary_extraction_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("document_extractions.id", ondelete="SET NULL"),
        nullable=True,
    )

    application: Mapped["Application"] = relationship(back_populates="documents")
    primary_extraction: Mapped["DocumentExtraction | None"] = relationship(
        foreign_keys=[primary_extraction_id],
        back_populates="primary_for_document",
    )
    extractions: Mapped[list["DocumentExtraction"]] = relationship(
        back_populates="document",
        foreign_keys="DocumentExtraction.document_id",
        cascade="all, delete-orphan",
    )


class DocumentExtraction(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "document_extractions"
    __table_args__ = (Index("ix_document_extractions_document", "document_id"),)

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    sha256_hex: Mapped[str] = mapped_column(String(64), nullable=False)
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    extraction_status: Mapped[str] = mapped_column(String(32), nullable=False)
    extractor_version: Mapped[str] = mapped_column(String(32), nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    document: Mapped["Document"] = relationship(
        back_populates="extractions",
        foreign_keys=[document_id],
    )
    primary_for_document: Mapped["Document | None"] = relationship(
        "Document",
        primaryjoin="DocumentExtraction.id == foreign(Document.primary_extraction_id)",
        back_populates="primary_extraction",
        uselist=False,
    )


class InitialScreeningResult(Base, TimestampMixin):
    __tablename__ = "initial_screening_results"

    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), primary_key=True
    )
    screening_status: Mapped[str] = mapped_column(String(64), nullable=False)
    missing_items: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    issues_found: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    screening_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    screening_result: Mapped[str | None] = mapped_column(String(64), nullable=True)
    screening_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    application: Mapped["Application"] = relationship(back_populates="initial_screening_result")


class ApplicationReviewSnapshot(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "application_review_snapshot"
    __table_args__ = (UniqueConstraint("application_id", name="uq_application_review_snapshot_app"),)

    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False
    )
    review_status: Mapped[str] = mapped_column(String(64), nullable=False)
    review_packet: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    summary_by_block: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    authenticity_risk_flag: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    consistency_flags: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    reviewer_notes_internal: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_summary_draft: Mapped[str | None] = mapped_column(Text, nullable=True)
    explainability_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    application: Mapped["Application"] = relationship(back_populates="application_review_snapshot")


class InterviewSession(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "interview_sessions"
    __table_args__ = (Index("ix_interview_sessions_application", "application_id"),)

    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False
    )
    session_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    interview_status: Mapped[str] = mapped_column(String(64), nullable=False)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    interview_mode: Mapped[str | None] = mapped_column(String(64), nullable=True)
    location_or_link: Mapped[str | None] = mapped_column(String(512), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    follow_up_questions: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    interview_summary_draft: Mapped[str | None] = mapped_column(Text, nullable=True)

    application: Mapped["Application"] = relationship(back_populates="interview_sessions")


class AdmissionDecision(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "admission_decisions"
    __table_args__ = (UniqueConstraint("application_id", name="uq_admission_decisions_app"),)

    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False
    )
    final_decision_status: Mapped[str] = mapped_column(String(64), nullable=False)
    decision_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    candidate_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    internal_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_steps: Mapped[str | None] = mapped_column(Text, nullable=True)
    issued_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    audit_reference: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    application: Mapped["Application"] = relationship(back_populates="admission_decision")


class TextAnalysisRun(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "text_analysis_runs"
    __table_args__ = (
        Index("ix_text_analysis_runs_application", "application_id"),
        Index("ix_text_analysis_runs_block", "application_id", "block_key"),
    )

    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False
    )
    block_key: Mapped[str] = mapped_column(String(64), nullable=False)
    source_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    source_document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    dimensions: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    explanations: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    flags: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    application: Mapped["Application"] = relationship(back_populates="text_analysis_runs")


class AnalysisJob(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "analysis_jobs"
    __table_args__ = (Index("ix_analysis_jobs_app_status", "application_id", "status"),)

    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False
    )
    job_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    application: Mapped["Application"] = relationship(back_populates="analysis_jobs")


class VerificationRecord(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "verification_records"
    __table_args__ = (Index("ix_verification_user", "user_id"),)

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    verification_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)


class Notification(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "notifications"
    __table_args__ = (Index("ix_notifications_status_created", "status", "created_at"),)

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    template_key: Mapped[str] = mapped_column(String(128), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)


class AuditLog(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_entity_time", "entity_type", "entity_id", "created_at"),)

    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    before_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    after_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AIReviewMetadata(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "ai_review_metadata"
    __table_args__ = (Index("ix_ai_review_application", "application_id"),)

    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False
    )
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(64), nullable=False)
    summary_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    explainability_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    authenticity_risk_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    flags: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    decision_authority: Mapped[str] = mapped_column(String(32), default="human_only", nullable=False)

    application: Mapped["Application"] = relationship(back_populates="ai_reviews")


class CommitteeReview(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "committee_reviews"
    __table_args__ = (Index("ix_committee_app", "application_id"),)

    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False
    )
    reviewer_notes_internal: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_summary_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_flags: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    explainability_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    authenticity_risk_flag: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    recommendation: Mapped[str | None] = mapped_column(String(32), nullable=True)
    manual_override: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    committee_decision: Mapped[str | None] = mapped_column(String(64), nullable=True)
    committee_review_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    recommendation_band: Mapped[str | None] = mapped_column(String(64), nullable=True)
    recommendation_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_metadata_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_review_metadata.id", ondelete="SET NULL"), nullable=True
    )

    application: Mapped["Application"] = relationship(back_populates="committee_reviews")

