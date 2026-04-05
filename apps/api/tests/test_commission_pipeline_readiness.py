"""Consistency across data-check readiness, kanban hints, and stage-advance guard."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from invision_api.commission.application import kanban_border_hints
from invision_api.commission.application.section_score_service import SECTION_SCORE_CONFIGS
from invision_api.commission.application.stage_transition_guard import (
    StageAdvanceBlockCode,
    resolve_kanban_advance,
)
from invision_api.models.commission import SectionReviewScore
from invision_api.models.application import AIReviewMetadata
from invision_api.models.enums import ApplicationStage
from invision_api.repositories import data_check_repository
from invision_api.services.ai_interview.data_readiness import get_data_check_overall_status, is_data_processing_ready
from invision_api.services.data_check import submit_bootstrap_service


def test_kanban_latest_data_check_matches_get_data_check_overall_status(
    db: Session, factory, monkeypatch
) -> None:
    monkeypatch.setattr("invision_api.services.job_dispatcher_service.enqueue_job", lambda *_a, **_kwargs: None)

    user = factory.user(db)
    profile = factory.profile(db, user)
    app = factory.application(db, profile, state="under_screening")
    app.current_stage = ApplicationStage.initial_screening.value
    db.flush()

    submit_bootstrap_service.bootstrap_data_check_pipeline(
        db,
        application_id=app.id,
        candidate_id=profile.id,
        actor_user_id=user.id,
    )

    direct = get_data_check_overall_status(db, app.id)
    via_kanban_fn = kanban_border_hints.latest_data_check_run_status(db, app.id)
    assert direct == via_kanban_fn


def test_stage_one_data_ready_implies_aggregate_ready_and_ai_summary(
    db: Session, factory, monkeypatch
) -> None:
    """stage_one_data_ready matches product rule: AI summary + data-check ready."""
    monkeypatch.setattr("invision_api.services.job_dispatcher_service.enqueue_job", lambda *_a, **_kwargs: None)

    user = factory.user(db)
    profile = factory.profile(db, user)
    app = factory.application(db, profile, state="under_screening")
    app.current_stage = ApplicationStage.application_review.value
    db.flush()

    run_id = submit_bootstrap_service.bootstrap_data_check_pipeline(
        db,
        application_id=app.id,
        candidate_id=profile.id,
        actor_user_id=user.id,
    )
    for c in data_check_repository.list_checks_for_run(db, run_id):
        c.status = "completed"
    db.flush()

    assert is_data_processing_ready(db, app.id) is True
    assert kanban_border_hints.stage_one_data_ready(db, app.id, has_ai_summary=False) is False

    db.add(
        AIReviewMetadata(
            application_id=app.id,
            model="test",
            prompt_version="v1",
            summary_text="summary",
            flags={},
        )
    )
    db.flush()

    assert kanban_border_hints.stage_one_data_ready(db, app.id, has_ai_summary=True) is True


def test_resolve_kanban_advance_blocks_manual_move_from_initial_screening(
    db: Session, factory, monkeypatch
) -> None:
    monkeypatch.setattr("invision_api.services.job_dispatcher_service.enqueue_job", lambda *_a, **_kwargs: None)

    user = factory.user(db)
    profile = factory.profile(db, user)
    app = factory.application(db, profile, state="under_screening")
    app.current_stage = ApplicationStage.initial_screening.value
    db.flush()

    submit_bootstrap_service.bootstrap_data_check_pipeline(
        db,
        application_id=app.id,
        candidate_id=profile.id,
        actor_user_id=user.id,
    )

    res = resolve_kanban_advance(db, app.id)
    assert res.allowed is False
    assert res.block_code == StageAdvanceBlockCode.MANUAL_FROM_DATA_CHECK_FORBIDDEN


def test_application_review_total_score_uses_complete_manual_trio(db: Session, factory) -> None:
    user = factory.user(db)
    profile = factory.profile(db, user)
    app = factory.application(db, profile, state="under_review")
    app.current_stage = ApplicationStage.application_review.value
    db.flush()

    reviewer = factory.user(db, email="reviewer-a@example.com")
    score_value = 2
    for section in ("motivation", "path", "achievements"):
        for cfg in SECTION_SCORE_CONFIGS[section]:
            db.add(
                SectionReviewScore(
                    application_id=app.id,
                    reviewer_user_id=reviewer.id,
                    section=section,
                    score_key=cfg["key"],
                    recommended_score=3,
                    manual_score=score_value,
                    updated_at=datetime.now(tz=UTC),
                )
            )
            score_value += 1
    db.flush()

    total = kanban_border_hints.application_review_total_score(db, app.id)
    assert total == sum(range(2, 11))
    assert kanban_border_hints.rubric_three_sections_complete(db, app.id) is True


def test_application_review_total_score_is_none_for_incomplete_trio(db: Session, factory) -> None:
    user = factory.user(db)
    profile = factory.profile(db, user)
    app = factory.application(db, profile, state="under_review")
    app.current_stage = ApplicationStage.application_review.value
    db.flush()

    reviewer = factory.user(db, email="reviewer-b@example.com")
    # Missing one required key in achievements.
    for section in ("motivation", "path"):
        for cfg in SECTION_SCORE_CONFIGS[section]:
            db.add(
                SectionReviewScore(
                    application_id=app.id,
                    reviewer_user_id=reviewer.id,
                    section=section,
                    score_key=cfg["key"],
                    recommended_score=3,
                    manual_score=4,
                    updated_at=datetime.now(tz=UTC),
                )
            )
    for cfg in SECTION_SCORE_CONFIGS["achievements"][:-1]:
        db.add(
            SectionReviewScore(
                application_id=app.id,
                reviewer_user_id=reviewer.id,
                section="achievements",
                score_key=cfg["key"],
                recommended_score=3,
                manual_score=4,
                updated_at=datetime.now(tz=UTC),
            )
        )
    db.flush()

    assert kanban_border_hints.application_review_total_score(db, app.id) is None
    assert kanban_border_hints.rubric_three_sections_complete(db, app.id) is False
