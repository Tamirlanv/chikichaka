from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from invision_api.models.ai_interview import AIInterviewAnswer, AIInterviewQuestionSet


def get_question_set_for_application(db: Session, application_id: UUID) -> AIInterviewQuestionSet | None:
    return db.scalars(select(AIInterviewQuestionSet).where(AIInterviewQuestionSet.application_id == application_id)).first()


def get_question_set_for_application_for_update(db: Session, application_id: UUID) -> AIInterviewQuestionSet | None:
    """Row lock for approve / concurrent edit safety."""
    return db.scalars(
        select(AIInterviewQuestionSet)
        .where(AIInterviewQuestionSet.application_id == application_id)
        .with_for_update()
    ).first()


def upsert_draft(
    db: Session,
    *,
    application_id: UUID,
    questions: list[dict[str, Any]],
    generated_from_signals: dict[str, Any] | None,
) -> AIInterviewQuestionSet:
    row = get_question_set_for_application(db, application_id)
    now = datetime.now(tz=UTC)
    if row is None:
        row = AIInterviewQuestionSet(
            application_id=application_id,
            status="draft",
            revision=1,
            questions=questions,
            generated_from_signals=generated_from_signals,
            generated_at=now,
        )
        db.add(row)
    else:
        if row.status == "approved":
            row.revision = (row.revision or 1) + 1
        row.status = "draft"
        row.questions = questions
        row.generated_from_signals = generated_from_signals
        row.generated_at = now
        # New draft must not carry previous approval metadata (e.g. after force regenerate).
        row.approved_at = None
        row.approved_by_user_id = None
    db.flush()
    db.refresh(row)
    return row


def save_questions_draft(db: Session, row: AIInterviewQuestionSet, questions: list[dict[str, Any]]) -> None:
    row.questions = questions
    row.revision = (row.revision or 1) + 1
    db.flush()


def mark_approved(db: Session, row: AIInterviewQuestionSet, *, approved_by_user_id: UUID) -> None:
    from datetime import UTC, datetime

    row.status = "approved"
    row.approved_at = datetime.now(tz=UTC)
    row.approved_by_user_id = approved_by_user_id
    db.flush()


def upsert_answer(
    db: Session, *, application_id: UUID, question_id: str, answer_text: str
) -> AIInterviewAnswer:
    existing = db.scalars(
        select(AIInterviewAnswer).where(
            AIInterviewAnswer.application_id == application_id,
            AIInterviewAnswer.question_id == question_id,
        )
    ).first()
    if existing:
        existing.answer_text = answer_text
        db.flush()
        db.refresh(existing)
        return existing
    row = AIInterviewAnswer(application_id=application_id, question_id=question_id, answer_text=answer_text)
    db.add(row)
    db.flush()
    db.refresh(row)
    return row


def list_answers(db: Session, application_id: UUID) -> list[AIInterviewAnswer]:
    return list(
        db.scalars(
            select(AIInterviewAnswer).where(AIInterviewAnswer.application_id == application_id).order_by(
                AIInterviewAnswer.created_at
            )
        ).all()
    )
