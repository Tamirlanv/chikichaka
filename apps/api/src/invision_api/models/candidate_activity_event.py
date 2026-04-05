from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from invision_api.db.base import Base
from invision_api.models.mixins import UUIDPrimaryKeyMixin


class CandidateActivityEvent(Base, UUIDPrimaryKeyMixin):
    """Low-level candidate interaction telemetry for explainable engagement scoring."""

    __tablename__ = "candidate_activity_events"
    __table_args__ = (
        Index("ix_candidate_activity_app_time", "application_id", "occurred_at"),
        Index("ix_candidate_activity_user_time", "candidate_user_id", "occurred_at"),
        Index("ix_candidate_activity_event_type", "event_type"),
    )

    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True
    )
    candidate_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    stage: Mapped[str | None] = mapped_column(String(64), nullable=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSONB, nullable=True)
