"""Committee deliberation; no autonomous final decision."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from invision_api.models.application import Application, CommitteeReview
from invision_api.models.enums import ApplicationStage
from invision_api.services.stage_transition_policy import TransitionContext, TransitionName, apply_transition


def get_or_create_committee_review(db: Session, application_id: UUID) -> CommitteeReview:
    row = db.scalars(select(CommitteeReview).where(CommitteeReview.application_id == application_id)).first()
    if row:
        return row
    row = CommitteeReview(
        application_id=application_id,
        authenticity_risk_flag=False,
        manual_override=False,
    )
    db.add(row)
    db.flush()
    return row


def update_committee_review(
    db: Session,
    application_id: UUID,
    *,
    committee_review_status: str | None = None,
    recommendation_band: str | None = None,
    recommendation_reasoning: str | None = None,
    reviewer_notes_internal: str | None = None,
) -> CommitteeReview:
    row = get_or_create_committee_review(db, application_id)
    if committee_review_status is not None:
        row.committee_review_status = committee_review_status
    if recommendation_band is not None:
        row.recommendation_band = recommendation_band
    if recommendation_reasoning is not None:
        row.recommendation_reasoning = recommendation_reasoning
    if reviewer_notes_internal is not None:
        row.reviewer_notes_internal = reviewer_notes_internal
    return row


def advance_to_decision_stage(
    db: Session,
    app: Application,
    *,
    actor_user_id: UUID | None,
) -> Application:
    if app.current_stage != ApplicationStage.committee_review.value:
        raise ValueError("application must be in committee_review stage")
    ctx = TransitionContext(
        application_id=app.id,
        transition=TransitionName.human_advances_to_decision,
        actor_user_id=actor_user_id,
        actor_type="committee",
    )
    return apply_transition(db, app, ctx)
