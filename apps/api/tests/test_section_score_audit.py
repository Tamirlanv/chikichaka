from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from invision_api.commission.application import section_score_service
from invision_api.models.application import AuditLog
from invision_api.models.enums import ApplicationState


def test_save_section_scores_writes_audit_event(db: Session, factory) -> None:
    reviewer = factory.user(db)
    candidate = factory.user(db)
    profile = factory.profile(db, candidate)
    app = factory.application(db, profile, state=ApplicationState.submitted.value)
    app.locked_after_submit = True
    app.submitted_at = datetime.now(tz=UTC)
    db.flush()

    section_score_service.save_section_scores(
        db,
        application_id=app.id,
        section="motivation",
        reviewer_user_id=reviewer.id,
        scores=[
            {"key": "motivation_level", "score": 4},
            {"key": "choice_awareness", "score": 4},
            {"key": "specificity", "score": 4},
        ],
    )
    db.flush()

    row = db.scalars(
        select(AuditLog)
        .where(AuditLog.entity_type == "application", AuditLog.entity_id == app.id, AuditLog.action == "section_scores_updated")
        .order_by(AuditLog.created_at.desc())
    ).first()
    assert row is not None
    after = row.after_data if isinstance(row.after_data, dict) else {}
    assert after.get("section") == "motivation"
