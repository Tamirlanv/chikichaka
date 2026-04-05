from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from invision_api.commission.application import history_service
from invision_api.models.enums import ApplicationState
from invision_api.repositories import commission_repository, data_check_repository
from invision_api.services import audit_log_service


def test_commission_history_events_human_readable(db: Session, factory) -> None:
    reviewer = factory.user(db, email="reviewer@example.com")
    candidate_user = factory.user(db, email="candidate@example.com")
    profile = factory.profile(db, candidate_user, first_name="Алихан", last_name="С.")

    app = factory.application(db, profile, state=ApplicationState.submitted.value)
    app.locked_after_submit = True
    app.submitted_at = datetime.now(tz=UTC)
    app.current_stage = "application_review"
    db.flush()
    commission_repository.upsert_projection_for_application(db, app)

    audit_log_service.write_audit(
        db,
        entity_type="application",
        entity_id=app.id,
        action="stage_advanced",
        actor_user_id=reviewer.id,
        after_data={"current_stage": "interview"},
    )
    audit_log_service.write_audit(
        db,
        entity_type="application",
        entity_id=app.id,
        action="final_decision_set",
        actor_user_id=reviewer.id,
        after_data={"final_decision": "reject"},
    )
    run = data_check_repository.create_run(
        db,
        candidate_id=candidate_user.id,
        application_id=app.id,
        status="ready",
    )
    run.updated_at = datetime.now(tz=UTC)
    db.flush()

    payload = history_service.list_commission_history_events(
        db,
        search="Алихан",
        program=None,
        event_type="all",
        sort="newest",
        limit=50,
        offset=0,
    )

    assert payload["total"] >= 3
    descriptions = [str(item["description"]).lower() for item in payload["items"]]
    assert any("переведен на этап" in line for line in descriptions)
    assert any("итоговое решение" in line for line in descriptions)
    assert all("stage_advanced" not in line for line in descriptions)
    assert all("final_decision_set" not in line for line in descriptions)


def test_application_history_events_filter_stage(db: Session, factory) -> None:
    reviewer = factory.user(db, email="reviewer2@example.com")
    candidate_user = factory.user(db, email="candidate2@example.com")
    profile = factory.profile(db, candidate_user, first_name="Аружан", last_name="М.")
    app = factory.application(db, profile, state=ApplicationState.submitted.value)
    app.locked_after_submit = True
    app.submitted_at = datetime.now(tz=UTC)
    app.current_stage = "initial_screening"
    db.flush()
    commission_repository.upsert_projection_for_application(db, app)

    audit_log_service.write_audit(
        db,
        entity_type="application",
        entity_id=app.id,
        action="stage_advanced",
        actor_user_id=reviewer.id,
        after_data={"current_stage": "application_review"},
    )
    audit_log_service.write_audit(
        db,
        entity_type="application",
        entity_id=app.id,
        action="comment_added",
        actor_user_id=reviewer.id,
        after_data={"comment_id": "x"},
    )
    db.flush()

    payload = history_service.list_application_history_events(
        db,
        application_id=app.id,
        event_type="stage",
        sort="newest",
        limit=50,
        offset=0,
    )

    assert payload["applicationId"] == str(app.id)
    assert payload["total"] >= 1
    assert all("Перемещение по этапам" == item["eventType"] for item in payload["items"])
