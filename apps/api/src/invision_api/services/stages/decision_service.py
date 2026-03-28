"""Final admission decision — committee/admin only; audited."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from invision_api.models.application import Application
from invision_api.models.enums import ApplicationStage, ApplicationState
from invision_api.repositories import admissions_repository
from invision_api.services import audit_log_service


def record_final_decision(
    db: Session,
    app: Application,
    *,
    actor_user_id: UUID,
    final_decision_status: str,
    candidate_message: str | None,
    internal_note: str | None,
    next_steps: str | None,
) -> Any:
    """Persist admission decision. Caller must enforce committee/admin role."""
    if app.current_stage != ApplicationStage.decision.value:
        raise ValueError("application must be in decision stage")
    if admissions_repository.get_admission_decision(db, app.id):
        raise ValueError("decision already recorded")

    audit_row = audit_log_service.write_audit(
        db,
        entity_type="application",
        entity_id=app.id,
        action="admission_decision_draft",
        actor_user_id=actor_user_id,
        after_data={"final_decision_status": final_decision_status},
    )

    decision = admissions_repository.create_admission_decision(
        db,
        app.id,
        final_decision_status=final_decision_status,
        decision_at=datetime.now(tz=UTC),
        candidate_message=candidate_message,
        internal_note=internal_note,
        next_steps=next_steps,
        issued_by_user_id=actor_user_id,
        audit_reference=audit_row.id,
    )
    app.state = ApplicationState.decision_made.value
    db.flush()
    return decision
