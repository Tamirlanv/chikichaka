from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from invision_api.models.enums import ApplicationStage
from invision_api.models.link_validation import LinkValidationResultRow
from invision_api.repositories import data_check_repository
from invision_api.services.data_check import submit_bootstrap_service
from invision_api.services.data_check.external_ingestion_service import (
    ExternalIngestionConflictError,
    ExternalIngestionValidationError,
    ingest_external_unit_result,
)


def test_data_check_external_validation_ingestion_updates_local_storage(
    db: Session, factory, monkeypatch
):
    user = factory.user(db)
    profile = factory.profile(db, user)
    app = factory.application(db, profile, state="under_screening")
    app.current_stage = ApplicationStage.initial_screening.value
    db.flush()

    monkeypatch.setattr("invision_api.services.job_dispatcher_service.enqueue_job", lambda *_args, **_kwargs: None)
    run_id = submit_bootstrap_service.bootstrap_data_check_pipeline(
        db,
        application_id=app.id,
        candidate_id=profile.id,
        actor_user_id=user.id,
    )

    ingest_external_unit_result(
        db,
        application_id=app.id,
        run_id=run_id,
        check_type="links",
        status="completed",
        result_payload={
            "links": [
                {
                    "originalUrl": "https://example.com",
                    "normalizedUrl": "https://example.com",
                    "isValidFormat": True,
                    "isReachable": True,
                    "availabilityStatus": "reachable",
                    "provider": "generic",
                    "resourceType": "web_page",
                    "statusCode": 200,
                    "contentType": "text/html",
                    "contentLength": 1000,
                    "redirected": False,
                    "redirectCount": 0,
                    "responseTimeMs": 120,
                    "warnings": [],
                    "errors": [],
                    "confidence": 0.95,
                }
            ]
        },
        warnings=[],
        errors=[],
        explainability=["external link run completed"],
    )
    db.flush()

    check = data_check_repository.get_check(db, run_id, "link_validation")
    assert check is not None
    assert check.status == "completed"

    rows = list(
        db.scalars(select(LinkValidationResultRow).where(LinkValidationResultRow.application_id == app.id)).all()
    )
    assert len(rows) == 1
    assert rows[0].original_url == "https://example.com"


def test_external_ingestion_maps_processing_to_running(
    db: Session, factory, monkeypatch
) -> None:
    user = factory.user(db)
    profile = factory.profile(db, user)
    app = factory.application(db, profile, state="under_screening")
    app.current_stage = ApplicationStage.initial_screening.value
    db.flush()

    monkeypatch.setattr("invision_api.services.job_dispatcher_service.enqueue_job", lambda *_args, **_kwargs: None)
    run_id = submit_bootstrap_service.bootstrap_data_check_pipeline(
        db,
        application_id=app.id,
        candidate_id=profile.id,
        actor_user_id=user.id,
    )

    ingest_external_unit_result(
        db,
        application_id=app.id,
        run_id=run_id,
        check_type="videoPresentation",
        status="processing",
        result_payload={"videoUrl": "https://example.com/v.mp4"},
        warnings=[],
        errors=[],
        explainability=[],
    )
    db.flush()

    check = data_check_repository.get_check(db, run_id, "video_validation")
    assert check is not None
    assert check.status == "running"


def test_external_ingestion_rejects_unknown_status(
    db: Session, factory, monkeypatch
) -> None:
    user = factory.user(db)
    profile = factory.profile(db, user)
    app = factory.application(db, profile, state="under_screening")
    app.current_stage = ApplicationStage.initial_screening.value
    db.flush()

    monkeypatch.setattr("invision_api.services.job_dispatcher_service.enqueue_job", lambda *_args, **_kwargs: None)
    run_id = submit_bootstrap_service.bootstrap_data_check_pipeline(
        db,
        application_id=app.id,
        candidate_id=profile.id,
        actor_user_id=user.id,
    )

    try:
        ingest_external_unit_result(
            db,
            application_id=app.id,
            run_id=run_id,
            check_type="links",
            status="unexpected_state",
            result_payload={},
            warnings=[],
            errors=[],
            explainability=[],
        )
    except ExternalIngestionValidationError:
        return
    assert False, "Expected ExternalIngestionValidationError for unknown status"


def test_external_ingestion_rejects_noncanonical_run(
    db: Session, factory, monkeypatch
) -> None:
    user = factory.user(db)
    profile = factory.profile(db, user)
    app = factory.application(db, profile, state="under_screening")
    app.current_stage = ApplicationStage.initial_screening.value
    db.flush()

    monkeypatch.setattr("invision_api.services.job_dispatcher_service.enqueue_job", lambda *_args, **_kwargs: None)
    canonical_run_id = submit_bootstrap_service.bootstrap_data_check_pipeline(
        db,
        application_id=app.id,
        candidate_id=profile.id,
        actor_user_id=user.id,
    )

    legacy = data_check_repository.create_run(
        db,
        candidate_id=profile.id,
        application_id=app.id,
        status="running",
    )
    data_check_repository.create_check(
        db,
        run_id=legacy.id,
        check_type="links",
        status="running",
        result_payload=None,
    )
    db.flush()

    assert legacy.id != canonical_run_id
    try:
        ingest_external_unit_result(
            db,
            application_id=app.id,
            run_id=legacy.id,
            check_type="links",
            status="passed",
            result_payload={},
            warnings=[],
            errors=[],
            explainability=[],
        )
    except ExternalIngestionConflictError:
        return
    assert False, "Expected ExternalIngestionConflictError for non-canonical run ingestion"
