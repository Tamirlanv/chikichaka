"""Initial screening: document extraction, completeness checks, screening result rows."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from invision_api.models.application import Application
from invision_api.models.enums import ApplicationStage, ScreeningResult
from invision_api.repositories import admissions_repository, document_repository
from invision_api.services import application_service, job_dispatcher_service, text_extraction_service
from invision_api.services.stage_transition_policy import TransitionContext, TransitionName, apply_transition


def enqueue_post_submit_jobs(db: Session, application_id: UUID) -> None:
    """After submit: queue text extraction for each document and a screening job."""
    docs = document_repository.list_documents_for_application(db, application_id)
    for d in docs:
        job_dispatcher_service.enqueue_extract_text(db, application_id, d.id)
    job_dispatcher_service.enqueue_initial_screening_job(db, application_id)


def run_extractions_for_application(db: Session, application_id: UUID) -> list[UUID]:
    """Run extraction for every document; returns document ids processed."""
    docs = document_repository.list_documents_for_application(db, application_id)
    out: list[UUID] = []
    for d in docs:
        text_extraction_service.extract_and_persist_for_document(db, d.id)
        out.append(d.id)
    return out


def _collect_missing_items(db: Session, app: Application) -> dict[str, Any]:
    _, missing = application_service.completion_percentage(db, app)
    return {
        "missing_sections": [m.value for m in missing],
    }


def run_screening_checks_and_record(
    db: Session,
    app: Application,
    *,
    actor_user_id: UUID | None,
) -> Any:
    """Run extraction, evaluate completeness, persist InitialScreeningResult (no automatic transition)."""
    run_extractions_for_application(db, app.id)
    missing = _collect_missing_items(db, app)
    issues: dict[str, Any] = {}
    if missing["missing_sections"]:
        issues["incomplete_sections"] = missing["missing_sections"]

    screening_result = (
        ScreeningResult.passed.value if not issues else ScreeningResult.revision_required.value
    )
    row = admissions_repository.upsert_initial_screening(
        db,
        app.id,
        screening_status="completed",
        missing_items=missing,
        issues_found=issues or None,
        screening_notes=None,
        screening_result=screening_result,
        screening_completed_at=datetime.now(tz=UTC),
    )
    db.flush()
    return row


def apply_screening_transition(
    db: Session,
    app: Application,
    *,
    transition: TransitionName,
    actor_user_id: UUID | None,
    internal_note: str | None = None,
) -> Application:
    if transition not in (TransitionName.screening_passed, TransitionName.revision_required, TransitionName.screening_blocked):
        raise ValueError("invalid screening transition")
    ctx = TransitionContext(
        application_id=app.id,
        transition=transition,
        actor_user_id=actor_user_id,
        actor_type="committee",
        internal_note=internal_note,
    )
    return apply_transition(db, app, ctx)


def ensure_stage(db: Session, app: Application) -> None:
    if app.current_stage != ApplicationStage.initial_screening.value:
        raise ValueError("application must be in initial_screening stage")
