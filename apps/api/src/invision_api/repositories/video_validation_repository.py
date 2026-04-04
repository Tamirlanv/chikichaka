from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from invision_api.models.video_validation import VideoValidationResultRow


def get_latest_for_application(db: Session, application_id: UUID) -> VideoValidationResultRow | None:
    return db.scalars(
        select(VideoValidationResultRow)
        .where(VideoValidationResultRow.application_id == application_id)
        .order_by(VideoValidationResultRow.created_at.desc())
        .limit(1)
    ).first()
