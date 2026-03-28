"""Central rules for (stage, state) transitions and stage history writes."""

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from invision_api.models.application import Application, ApplicationStageHistory
from invision_api.models.enums import ApplicationStage, ApplicationState
from invision_api.services import audit_log_service


class TransitionName(str, Enum):
    submit_application = "submit_application"
    screening_passed = "screening_passed"
    revision_required = "revision_required"
    screening_blocked = "screening_blocked"
    review_complete = "review_complete"
    interview_complete = "interview_complete"
    human_advances_to_decision = "human_advances_to_decision"
    decision_recorded = "decision_recorded"


@dataclass(frozen=True)
class TransitionContext:
    application_id: UUID
    transition: TransitionName
    actor_user_id: UUID | None
    actor_type: str
    candidate_visible_note: str | None = None
    internal_note: str | None = None


def _close_open_history(db: Session, application_id: UUID, now: datetime) -> None:
    last_open = db.scalars(
        select(ApplicationStageHistory)
        .where(ApplicationStageHistory.application_id == application_id, ApplicationStageHistory.exited_at.is_(None))
        .order_by(ApplicationStageHistory.entered_at.desc())
    ).first()
    if last_open:
        last_open.exited_at = now


def _append_history(
    db: Session,
    application_id: UUID,
    *,
    from_stage: str | None,
    to_stage: str,
    now: datetime,
    actor_type: str,
    candidate_visible_note: str | None,
    internal_note: str | None,
) -> ApplicationStageHistory:
    row = ApplicationStageHistory(
        application_id=application_id,
        from_stage=from_stage,
        to_stage=to_stage,
        entered_at=now,
        actor_type=actor_type,
        candidate_visible_note=candidate_visible_note,
        internal_note=internal_note,
    )
    db.add(row)
    return row


def apply_transition(db: Session, app: Application, ctx: TransitionContext) -> Application:
    """Apply a validated transition; caller must commit."""
    now = datetime.now(tz=UTC)
    before = {"state": app.state, "current_stage": app.current_stage, "locked": app.locked_after_submit}

    match ctx.transition:
        case TransitionName.screening_passed:
            if app.current_stage != ApplicationStage.initial_screening.value:
                raise ValueError("screening_passed only from initial_screening")
            prev_stage = app.current_stage
            _close_open_history(db, app.id, now)
            app.current_stage = ApplicationStage.application_review.value
            app.state = ApplicationState.under_review.value
            _append_history(
                db,
                app.id,
                from_stage=prev_stage,
                to_stage=ApplicationStage.application_review.value,
                now=now,
                actor_type=ctx.actor_type,
                candidate_visible_note=ctx.candidate_visible_note or "Первичная проверка пройдена.",
                internal_note=ctx.internal_note,
            )
        case TransitionName.revision_required:
            prev_stage = app.current_stage
            _close_open_history(db, app.id, now)
            app.current_stage = ApplicationStage.application.value
            app.state = ApplicationState.revision_required.value
            app.locked_after_submit = False
            _append_history(
                db,
                app.id,
                from_stage=prev_stage,
                to_stage=ApplicationStage.application.value,
                now=now,
                actor_type=ctx.actor_type,
                candidate_visible_note=ctx.candidate_visible_note
                or "Требуется доработка материалов. Заявление снова доступно для редактирования.",
                internal_note=ctx.internal_note,
            )
        case TransitionName.screening_blocked:
            if app.current_stage != ApplicationStage.initial_screening.value:
                raise ValueError("screening_blocked only from initial_screening")
            app.state = ApplicationState.screening_blocked.value
            _append_history(
                db,
                app.id,
                from_stage=ApplicationStage.initial_screening.value,
                to_stage=ApplicationStage.initial_screening.value,
                now=now,
                actor_type=ctx.actor_type,
                candidate_visible_note=ctx.candidate_visible_note,
                internal_note=ctx.internal_note,
            )
        case TransitionName.review_complete:
            if app.current_stage != ApplicationStage.application_review.value:
                raise ValueError("review_complete only from application_review")
            prev_stage = app.current_stage
            _close_open_history(db, app.id, now)
            app.current_stage = ApplicationStage.interview.value
            app.state = ApplicationState.interview_pending.value
            _append_history(
                db,
                app.id,
                from_stage=prev_stage,
                to_stage=ApplicationStage.interview.value,
                now=now,
                actor_type=ctx.actor_type,
                candidate_visible_note=ctx.candidate_visible_note or "Материалы приняты к рассмотрению на следующем этапе.",
                internal_note=ctx.internal_note,
            )
        case TransitionName.interview_complete:
            if app.current_stage != ApplicationStage.interview.value:
                raise ValueError("interview_complete only from interview")
            prev_stage = app.current_stage
            _close_open_history(db, app.id, now)
            app.current_stage = ApplicationStage.committee_review.value
            app.state = ApplicationState.committee_review.value
            _append_history(
                db,
                app.id,
                from_stage=prev_stage,
                to_stage=ApplicationStage.committee_review.value,
                now=now,
                actor_type=ctx.actor_type,
                candidate_visible_note=ctx.candidate_visible_note or "Собеседование зафиксировано; дело передано в комиссию.",
                internal_note=ctx.internal_note,
            )
        case TransitionName.human_advances_to_decision:
            if app.current_stage != ApplicationStage.committee_review.value:
                raise ValueError("human_advances_to_decision only from committee_review")
            prev_stage = app.current_stage
            _close_open_history(db, app.id, now)
            app.current_stage = ApplicationStage.decision.value
            app.state = ApplicationState.pending_decision.value
            _append_history(
                db,
                app.id,
                from_stage=prev_stage,
                to_stage=ApplicationStage.decision.value,
                now=now,
                actor_type=ctx.actor_type,
                candidate_visible_note=ctx.candidate_visible_note or "Принято решение по зачислению.",
                internal_note=ctx.internal_note,
            )
        case _:
            raise ValueError(f"Unsupported transition {ctx.transition}")

    after = {"state": app.state, "current_stage": app.current_stage, "locked": app.locked_after_submit}
    audit_log_service.write_audit(
        db,
        entity_type="application",
        entity_id=app.id,
        action=f"transition:{ctx.transition.value}",
        actor_user_id=ctx.actor_user_id,
        before_data=before,
        after_data=after,
    )
    db.flush()
    return app
