"""AI clarification interview: draft questions, commission approval, candidate answers."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from invision_api.db.base import Base
from invision_api.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class AIInterviewQuestionSet(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "ai_interview_question_sets"
    __table_args__ = (
        UniqueConstraint("application_id", name="uq_ai_interview_question_sets_app"),
        Index("ix_ai_interview_qs_app", "application_id"),
        Index("ix_ai_interview_qs_status", "status"),
    )

    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)  # draft | approved
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    questions: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    generated_from_signals: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"), nullable=False)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    candidate_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution_summary: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    resolution_summary_error: Mapped[str | None] = mapped_column(Text, nullable=True)


class AIInterviewAnswer(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "ai_interview_answers"
    __table_args__ = (
        UniqueConstraint("application_id", "question_id", name="uq_ai_interview_answer_app_q"),
        Index("ix_ai_interview_answers_app", "application_id"),
    )

    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False
    )
    question_id: Mapped[str] = mapped_column(String(64), nullable=False)
    answer_text: Mapped[str] = mapped_column(Text, nullable=False)
