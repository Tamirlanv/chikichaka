"""Persistence for admissions stage artifacts, extractions, analysis, decisions."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from invision_api.models.application import (
    AdmissionDecision,
    AnalysisJob,
    Application,
    ApplicationReviewSnapshot,
    DocumentExtraction,
    InitialScreeningResult,
    InterviewSession,
    TextAnalysisRun,
)


def get_initial_screening(db: Session, application_id: UUID) -> InitialScreeningResult | None:
    return db.get(InitialScreeningResult, application_id)


def upsert_initial_screening(
    db: Session,
    application_id: UUID,
    *,
    screening_status: str,
    missing_items: dict[str, Any] | None = None,
    issues_found: dict[str, Any] | None = None,
    screening_notes: str | None = None,
    screening_result: str | None = None,
    screening_completed_at: datetime | None = None,
) -> InitialScreeningResult:
    row = db.get(InitialScreeningResult, application_id)
    if row:
        row.screening_status = screening_status
        row.missing_items = missing_items
        row.issues_found = issues_found
        row.screening_notes = screening_notes
        row.screening_result = screening_result
        row.screening_completed_at = screening_completed_at
        return row
    row = InitialScreeningResult(
        application_id=application_id,
        screening_status=screening_status,
        missing_items=missing_items,
        issues_found=issues_found,
        screening_notes=screening_notes,
        screening_result=screening_result,
        screening_completed_at=screening_completed_at,
    )
    db.add(row)
    return row


def get_review_snapshot(db: Session, application_id: UUID) -> ApplicationReviewSnapshot | None:
    return db.scalars(
        select(ApplicationReviewSnapshot).where(ApplicationReviewSnapshot.application_id == application_id)
    ).first()


def upsert_review_snapshot(
    db: Session,
    application_id: UUID,
    *,
    review_status: str,
    review_packet: dict[str, Any] | None = None,
    summary_by_block: dict[str, Any] | None = None,
    authenticity_risk_flag: bool = False,
    consistency_flags: dict[str, Any] | None = None,
    reviewer_notes_internal: str | None = None,
    ai_summary_draft: str | None = None,
    explainability_snapshot: dict[str, Any] | None = None,
) -> ApplicationReviewSnapshot:
    row = get_review_snapshot(db, application_id)
    if row:
        row.review_status = review_status
        row.review_packet = review_packet
        row.summary_by_block = summary_by_block
        row.authenticity_risk_flag = authenticity_risk_flag
        row.consistency_flags = consistency_flags
        row.reviewer_notes_internal = reviewer_notes_internal
        row.ai_summary_draft = ai_summary_draft
        row.explainability_snapshot = explainability_snapshot
        return row
    row = ApplicationReviewSnapshot(
        application_id=application_id,
        review_status=review_status,
        review_packet=review_packet,
        summary_by_block=summary_by_block,
        authenticity_risk_flag=authenticity_risk_flag,
        consistency_flags=consistency_flags,
        reviewer_notes_internal=reviewer_notes_internal,
        ai_summary_draft=ai_summary_draft,
        explainability_snapshot=explainability_snapshot,
    )
    db.add(row)
    return row


def list_interview_sessions(db: Session, application_id: UUID) -> list[InterviewSession]:
    return list(
        db.scalars(
            select(InterviewSession)
            .where(InterviewSession.application_id == application_id)
            .order_by(InterviewSession.session_index, InterviewSession.created_at)
        ).all()
    )


def create_interview_session(
    db: Session,
    application_id: UUID,
    *,
    session_index: int,
    interview_status: str,
    scheduled_at: datetime | None = None,
    scheduled_by_user_id: UUID | None = None,
    interview_mode: str | None = None,
    location_or_link: str | None = None,
    notes: str | None = None,
    transcript: str | None = None,
    follow_up_questions: dict[str, Any] | None = None,
    interview_summary_draft: str | None = None,
) -> InterviewSession:
    row = InterviewSession(
        application_id=application_id,
        session_index=session_index,
        interview_status=interview_status,
        scheduled_at=scheduled_at,
        scheduled_by_user_id=scheduled_by_user_id,
        interview_mode=interview_mode,
        location_or_link=location_or_link,
        notes=notes,
        transcript=transcript,
        follow_up_questions=follow_up_questions,
        interview_summary_draft=interview_summary_draft,
    )
    db.add(row)
    return row


def get_admission_decision(db: Session, application_id: UUID) -> AdmissionDecision | None:
    return db.scalars(select(AdmissionDecision).where(AdmissionDecision.application_id == application_id)).first()


def create_admission_decision(
    db: Session,
    application_id: UUID,
    *,
    final_decision_status: str,
    decision_at: datetime | None,
    candidate_message: str | None,
    internal_note: str | None,
    next_steps: str | None,
    issued_by_user_id: UUID | None,
    audit_reference: UUID | None,
) -> AdmissionDecision:
    row = AdmissionDecision(
        application_id=application_id,
        final_decision_status=final_decision_status,
        decision_at=decision_at,
        candidate_message=candidate_message,
        internal_note=internal_note,
        next_steps=next_steps,
        issued_by_user_id=issued_by_user_id,
        audit_reference=audit_reference,
    )
    db.add(row)
    return row


def create_document_extraction(
    db: Session,
    document_id: UUID,
    *,
    sha256_hex: str,
    extracted_text: str | None,
    extraction_status: str,
    extractor_version: str,
    error_message: str | None = None,
) -> DocumentExtraction:
    row = DocumentExtraction(
        document_id=document_id,
        sha256_hex=sha256_hex,
        extracted_text=extracted_text,
        extraction_status=extraction_status,
        extractor_version=extractor_version,
        error_message=error_message,
    )
    db.add(row)
    db.flush()
    return row


def set_document_primary_extraction(db: Session, document_id: UUID, extraction_id: UUID) -> None:
    from invision_api.models.application import Document

    doc = db.get(Document, document_id)
    if doc:
        doc.primary_extraction_id = extraction_id


def latest_extraction_for_document(db: Session, document_id: UUID) -> DocumentExtraction | None:
    return db.scalars(
        select(DocumentExtraction)
        .where(DocumentExtraction.document_id == document_id)
        .order_by(DocumentExtraction.created_at.desc())
        .limit(1)
    ).first()


def create_text_analysis_run(
    db: Session,
    application_id: UUID,
    *,
    block_key: str,
    source_kind: str,
    source_document_id: UUID | None,
    model: str | None,
    status: str,
    dimensions: dict[str, Any] | None = None,
    explanations: dict[str, Any] | None = None,
    flags: dict[str, Any] | None = None,
) -> TextAnalysisRun:
    row = TextAnalysisRun(
        application_id=application_id,
        block_key=block_key,
        source_kind=source_kind,
        source_document_id=source_document_id,
        model=model,
        status=status,
        dimensions=dimensions,
        explanations=explanations,
        flags=flags,
    )
    db.add(row)
    return row


def create_analysis_job(
    db: Session,
    application_id: UUID,
    *,
    job_type: str,
    payload: dict[str, Any] | None,
    status: str,
) -> AnalysisJob:
    row = AnalysisJob(
        application_id=application_id,
        job_type=job_type,
        payload=payload,
        status=status,
        attempts=0,
        last_error=None,
    )
    db.add(row)
    return row


def get_analysis_job(db: Session, job_id: UUID) -> AnalysisJob | None:
    return db.get(AnalysisJob, job_id)


def update_analysis_job(
    db: Session,
    job: AnalysisJob,
    *,
    status: str | None = None,
    attempts: int | None = None,
    last_error: str | None = None,
) -> AnalysisJob:
    if status is not None:
        job.status = status
    if attempts is not None:
        job.attempts = attempts
    if last_error is not None:
        job.last_error = last_error
    return job


def get_application_by_id(db: Session, application_id: UUID) -> Application | None:
    return db.get(Application, application_id)
