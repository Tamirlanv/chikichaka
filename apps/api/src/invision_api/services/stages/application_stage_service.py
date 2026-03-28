"""Application-stage assembly: completion and pre-submit validation."""

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from invision_api.models.application import Application
from invision_api.models.enums import ApplicationStage, SectionKey
from invision_api.repositories import document_repository
from invision_api.services import application_service, section_payloads


def get_stage_snapshot(db: Session, app: Application) -> dict[str, Any]:
    """Candidate-facing summary of current stage and section completeness."""
    pct, missing = application_service.completion_percentage(db, app)
    docs = document_repository.list_documents_for_application(db, app.id)
    return {
        "current_stage": app.current_stage,
        "state": app.state,
        "completion_percentage": pct,
        "missing_sections": [m.value for m in missing],
        "locked_after_submit": app.locked_after_submit,
        "document_count": len(docs),
        "editable": app.current_stage == ApplicationStage.application.value and not app.locked_after_submit,
    }


def validate_ready_to_submit(db: Session, app: Application) -> tuple[bool, list[str]]:
    _, missing = application_service.completion_percentage(db, app)
    if not missing:
        return True, []
    return False, [m.value for m in missing]


def load_section_payload(db: Session, app: Application, section_key: str) -> dict[str, Any] | None:
    from invision_api.models.application import ApplicationSectionState
    from sqlalchemy import select

    row = db.scalars(
        select(ApplicationSectionState).where(
            ApplicationSectionState.application_id == app.id,
            ApplicationSectionState.section_key == section_key,
        )
    ).first()
    return row.payload if row else None


def get_motivation_narrative(db: Session, app: Application) -> str | None:
    raw = load_section_payload(db, app, SectionKey.motivation_goals.value)
    if not raw:
        return None
    try:
        p = section_payloads.MotivationGoalsSectionPayload.model_validate(raw)
        return p.narrative
    except Exception:
        return None
