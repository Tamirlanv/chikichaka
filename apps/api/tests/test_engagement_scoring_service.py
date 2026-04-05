from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from invision_api.models.application import ApplicationStageHistory
from invision_api.models.enums import ApplicationStage, ApplicationState
from invision_api.repositories import commission_repository
from invision_api.services import candidate_activity_service, engagement_scoring_service


def test_time_to_submit_bucket_boundaries() -> None:
    reg = datetime(2026, 4, 1, 10, 0, tzinfo=UTC)

    assert engagement_scoring_service._time_to_submit_bucket(reg + timedelta(minutes=1), reg) == "poor"
    assert engagement_scoring_service._time_to_submit_bucket(reg + timedelta(minutes=30), reg) == "poor"
    assert engagement_scoring_service._time_to_submit_bucket(reg + timedelta(minutes=31), reg) == "medium"
    assert engagement_scoring_service._time_to_submit_bucket(reg + timedelta(hours=2, minutes=59), reg) == "medium"
    assert engagement_scoring_service._time_to_submit_bucket(reg + timedelta(hours=3), reg) == "good"
    assert engagement_scoring_service._time_to_submit_bucket(reg + timedelta(hours=24), reg) == "good"
    assert engagement_scoring_service._time_to_submit_bucket(reg + timedelta(hours=25), reg) == "medium"


def test_last_online_bucket_boundaries() -> None:
    now = datetime(2026, 4, 5, 12, 0, tzinfo=UTC)

    assert engagement_scoring_service._last_online_bucket(now - timedelta(hours=5), now=now) == "good"
    assert engagement_scoring_service._last_online_bucket(now - timedelta(days=1), now=now) == "good"
    assert engagement_scoring_service._last_online_bucket(now - timedelta(days=2), now=now) == "medium"
    assert engagement_scoring_service._last_online_bucket(now - timedelta(days=5), now=now) == "poor"


def test_list_commission_engagement_only_active_stages(db: Session, factory) -> None:
    user = factory.user(db, email="engagement-candidate@example.com")
    profile = factory.profile(db, user, first_name="Алия", last_name="Тестова")

    active_app = factory.application(db, profile, state=ApplicationState.under_screening.value)
    active_app.locked_after_submit = True
    active_app.submitted_at = datetime.now(tz=UTC) - timedelta(hours=6)
    active_app.current_stage = ApplicationStage.initial_screening.value
    for row in active_app.stage_history:
        if row.exited_at is None:
            row.exited_at = datetime.now(tz=UTC) - timedelta(days=2)
    db.add(
        ApplicationStageHistory(
            application_id=active_app.id,
            from_stage=ApplicationStage.application.value,
            to_stage=ApplicationStage.initial_screening.value,
            entered_at=datetime.now(tz=UTC) - timedelta(days=2),
            actor_type="system",
        )
    )

    excluded_user = factory.user(db, email="engagement-excluded@example.com")
    excluded_profile = factory.profile(db, excluded_user, first_name="Исключен", last_name="Кандидат")
    excluded_result_app = factory.application(db, excluded_profile, state=ApplicationState.in_progress.value)
    excluded_result_app.locked_after_submit = True
    excluded_result_app.current_stage = ApplicationStage.application.value

    db.flush()
    commission_repository.upsert_projection_for_application(db, active_app)
    commission_repository.upsert_projection_for_application(db, excluded_result_app)

    candidate_activity_service.record_candidate_activity_event(
        db,
        application_id=active_app.id,
        candidate_user_id=user.id,
        event_type="platform_interaction_ping",
        occurred_at=datetime.now(tz=UTC) - timedelta(hours=2),
        stage=active_app.current_stage,
    )
    db.commit()

    payload = engagement_scoring_service.list_commission_engagement(
        db,
        search="Алия Тестова",
        program=None,
        sort="risk",
        limit=200,
        offset=0,
    )

    assert payload["totals"]["total"] == 1
    columns = payload["columns"]
    cards = [card for column in columns for card in column["cards"]]
    assert len(cards) == 1
    card = cards[0]
    assert card["applicationId"] == str(active_app.id)
    assert card["candidateFullName"] == "Алия Тестова"
    assert isinstance(card["lastActivityHumanized"], str) and card["lastActivityHumanized"]
    assert card["engagementLevel"] in {"High", "Medium", "Low"}
    assert card["riskLevel"] in {"High", "Medium", "Low"}


def test_record_candidate_activity_event_rejects_unknown_type(db: Session, factory) -> None:
    user = factory.user(db)
    profile = factory.profile(db, user)
    app = factory.application(db, profile)

    with pytest.raises(ValueError):
        candidate_activity_service.record_candidate_activity_event(
            db,
            application_id=app.id,
            candidate_user_id=user.id,
            event_type="unknown_event_type",
        )
