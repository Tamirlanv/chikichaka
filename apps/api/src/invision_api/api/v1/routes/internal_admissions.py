"""Internal admissions / committee routes (no candidate UI; real authorization)."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from invision_api.api.deps import require_roles
from invision_api.db.session import get_db
from invision_api.models.enums import RoleName
from invision_api.models.user import User
from invision_api.repositories import admissions_repository
from invision_api.services import candidate_stage_email_service, committee_service
from invision_api.services.stage_transition_policy import TransitionName
from invision_api.services.stages import (
    application_review_service,
    application_stage_service,
    committee_review_service,
    decision_service,
    initial_screening_service,
    interview_stage_service,
)

router = APIRouter()


@router.get("/applications")
def list_applications(
    stage: str | None = None,
    state: str | None = None,
    limit: int = 50,
    offset: int = 0,
    _: User = Depends(require_roles(RoleName.committee, RoleName.admin)),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    return committee_service.query_applications_for_review(db, stage=stage, state=state, limit=limit, offset=offset)


@router.get("/applications/{application_id}/stage")
def get_application_stage_internal(
    application_id: UUID,
    _: User = Depends(require_roles(RoleName.committee, RoleName.admin)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    app = admissions_repository.get_application_by_id(db, application_id)
    if not app:
        raise HTTPException(status_code=404, detail="Заявление не найдено")
    return application_stage_service.get_stage_snapshot(db, app)


class ScreeningTransitionBody(BaseModel):
    transition: str = Field(description="screening_passed | revision_required | screening_blocked")


@router.post("/applications/{application_id}/screening/run")
def run_screening(
    application_id: UUID,
    user: User = Depends(require_roles(RoleName.committee, RoleName.admin)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    app = admissions_repository.get_application_by_id(db, application_id)
    if not app:
        raise HTTPException(status_code=404, detail="Заявление не найдено")
    initial_screening_service.ensure_stage(db, app)
    row = initial_screening_service.run_screening_checks_and_record(db, app, actor_user_id=user.id)
    db.commit()
    db.refresh(row)
    return {
        "screening_status": row.screening_status,
        "screening_result": row.screening_result,
        "missing_items": row.missing_items,
        "issues_found": row.issues_found,
    }


@router.post("/applications/{application_id}/screening/transition")
def screening_transition(
    application_id: UUID,
    body: ScreeningTransitionBody,
    user: User = Depends(require_roles(RoleName.committee, RoleName.admin)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    app = admissions_repository.get_application_by_id(db, application_id)
    if not app:
        raise HTTPException(status_code=404, detail="Заявление не найдено")
    initial_screening_service.ensure_stage(db, app)
    try:
        tn = TransitionName(body.transition)
    except ValueError:
        raise HTTPException(status_code=400, detail="Неизвестный переход") from None
    if tn not in (
        TransitionName.screening_passed,
        TransitionName.revision_required,
        TransitionName.screening_blocked,
    ):
        raise HTTPException(status_code=400, detail="Недопустимый переход для скрининга")
    prev_stage = app.current_stage
    initial_screening_service.apply_screening_transition(db, app, transition=tn, actor_user_id=user.id)
    db.commit()
    db.refresh(app)
    if tn == TransitionName.revision_required:
        candidate_stage_email_service.send_revision_required_notification(application_id)
    elif tn != TransitionName.screening_blocked:
        candidate_stage_email_service.send_stage_transition_notification(
            application_id, prev_stage, app.current_stage
        )
    return {"state": app.state, "current_stage": app.current_stage}


@router.post("/applications/{application_id}/review/snapshot")
def build_review_snapshot(
    application_id: UUID,
    _: User = Depends(require_roles(RoleName.committee, RoleName.admin)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    snap = application_review_service.upsert_snapshot_from_packet(db, application_id)
    db.commit()
    db.refresh(snap)
    return {"review_status": snap.review_status, "id": str(snap.id)}


@router.post("/applications/{application_id}/review/transition-to-interview")
def review_to_interview(
    application_id: UUID,
    user: User = Depends(require_roles(RoleName.admin)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Ops-only: same transition as AI interview approve, but admin-only. Prefer POST .../ai-interview/approve."""
    app = admissions_repository.get_application_by_id(db, application_id)
    if not app:
        raise HTTPException(status_code=404, detail="Заявление не найдено")
    prev_stage = app.current_stage
    try:
        application_review_service.transition_to_interview(db, app, actor_user_id=user.id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    db.commit()
    db.refresh(app)
    candidate_stage_email_service.send_stage_transition_notification(application_id, prev_stage, app.current_stage)
    return {"state": app.state, "current_stage": app.current_stage}


@router.post("/applications/{application_id}/interview/complete")
def interview_complete(
    application_id: UUID,
    user: User = Depends(require_roles(RoleName.committee, RoleName.admin)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    app = admissions_repository.get_application_by_id(db, application_id)
    if not app:
        raise HTTPException(status_code=404, detail="Заявление не найдено")
    prev_stage = app.current_stage
    try:
        interview_stage_service.complete_interview_stage(db, app, actor_user_id=user.id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    db.commit()
    db.refresh(app)
    candidate_stage_email_service.send_stage_transition_notification(application_id, prev_stage, app.current_stage)
    return {"state": app.state, "current_stage": app.current_stage}


@router.post("/applications/{application_id}/committee/advance")
def committee_advance(
    application_id: UUID,
    user: User = Depends(require_roles(RoleName.committee, RoleName.admin)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    app = admissions_repository.get_application_by_id(db, application_id)
    if not app:
        raise HTTPException(status_code=404, detail="Заявление не найдено")
    prev_stage = app.current_stage
    try:
        committee_review_service.advance_to_decision_stage(db, app, actor_user_id=user.id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    db.commit()
    db.refresh(app)
    candidate_stage_email_service.send_stage_transition_notification(application_id, prev_stage, app.current_stage)
    return {"state": app.state, "current_stage": app.current_stage}


class DecisionBody(BaseModel):
    final_decision_status: str = Field(min_length=1, max_length=64)
    candidate_message: str | None = None
    internal_note: str | None = None
    next_steps: str | None = None


@router.post("/applications/{application_id}/decision")
def post_decision(
    application_id: UUID,
    body: DecisionBody,
    user: User = Depends(require_roles(RoleName.committee, RoleName.admin)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    app = admissions_repository.get_application_by_id(db, application_id)
    if not app:
        raise HTTPException(status_code=404, detail="Заявление не найдено")
    try:
        decision = decision_service.record_final_decision(
            db,
            app,
            actor_user_id=user.id,
            final_decision_status=body.final_decision_status,
            candidate_message=body.candidate_message,
            internal_note=body.internal_note,
            next_steps=body.next_steps,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    db.commit()
    db.refresh(decision)
    candidate_stage_email_service.send_final_decision_notification(application_id, body.final_decision_status)
    return {"id": str(decision.id), "final_decision_status": decision.final_decision_status}
