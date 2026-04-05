from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from invision_api.models.candidate_activity_event import CandidateActivityEvent


CANDIDATE_ACTIVITY_EVENT_TYPES: set[str] = {
    "platform_interaction_ping",
    "interview_info_opened",
    "interview_instruction_opened",
    "interview_link_copied",
    "interview_link_opened",
    "stage_action_started",
    "section_saved",
    "document_uploaded",
    "internal_test_saved",
    "internal_test_submitted",
    "application_submitted",
    "application_reopened",
    "interview_preferences_submitted",
    "ai_interview_completed",
    "reminder_requested",
}


def is_supported_event_type(event_type: str) -> bool:
    return event_type in CANDIDATE_ACTIVITY_EVENT_TYPES


def record_candidate_activity_event(
    db: Session,
    *,
    application_id: UUID,
    candidate_user_id: UUID,
    event_type: str,
    occurred_at: datetime | None = None,
    stage: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> CandidateActivityEvent:
    event_type = (event_type or "").strip()
    if not is_supported_event_type(event_type):
        raise ValueError(f"unsupported event_type={event_type!r}")

    ts = occurred_at or datetime.now(tz=UTC)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)

    row = CandidateActivityEvent(
        application_id=application_id,
        candidate_user_id=candidate_user_id,
        event_type=event_type,
        occurred_at=ts,
        stage=(stage or None),
        metadata_json=metadata or None,
    )
    db.add(row)
    db.flush()
    return row
