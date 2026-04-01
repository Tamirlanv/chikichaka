"""Pipeline test: validation orchestration trigger and report assembly."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from invision_api.repositories.commission_repository import get_latest_validation_report


def test_validation_report_assembly_from_db(db: Session, factory):
    """When validation data exists in DB, report assembles correctly."""
    from invision_api.models.candidate_validation_orchestration import (
        CandidateValidationRun,
        CandidateValidationCheck,
    )

    user = factory.user(db)
    profile = factory.profile(db, user)
    app = factory.application(db, profile)
    db.flush()

    run = CandidateValidationRun(
        id=uuid4(),
        candidate_id=profile.id,
        application_id=app.id,
        overall_status="completed",
        warnings=["Low confidence on link check"],
        errors=[],
        explainability=["All checks ran successfully"],
    )
    db.add(run)
    db.flush()

    db.add(CandidateValidationCheck(
        id=uuid4(),
        run_id=run.id,
        check_type="links",
        status="passed",
        result_payload={"valid": True},
    ))
    db.add(CandidateValidationCheck(
        id=uuid4(),
        run_id=run.id,
        check_type="videoPresentation",
        status="manual_review_required",
        result_payload={"face_detected": False},
    ))
    db.add(CandidateValidationCheck(
        id=uuid4(),
        run_id=run.id,
        check_type="certificates",
        status="passed",
        result_payload={"score": 85},
    ))
    db.flush()

    report = get_latest_validation_report(db, app.id)
    assert report is not None
    assert report["overallStatus"] == "completed"
    assert report["checks"]["links"]["status"] == "passed"
    assert report["checks"]["videoPresentation"]["status"] == "manual_review_required"
    assert report["checks"]["certificates"]["status"] == "passed"
    assert len(report["warnings"]) == 1


def test_validation_report_none_when_no_runs(db: Session, factory):
    """No validation runs returns None."""
    user = factory.user(db)
    profile = factory.profile(db, user)
    app = factory.application(db, profile)
    db.flush()

    report = get_latest_validation_report(db, app.id)
    assert report is None


def test_validation_trigger_service_handles_offline_orchestrator():
    """Trigger service doesn't raise when orchestrator is unreachable."""
    from invision_api.services.validation_trigger_service import trigger_validation_run
    from uuid import uuid4

    # This should not raise — it logs a warning instead
    trigger_validation_run(application_id=uuid4(), candidate_id=uuid4())
