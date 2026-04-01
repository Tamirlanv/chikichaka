"""Integration tests for commission review workflow: comments, rubrics, recommendations."""

import pytest
from sqlalchemy.orm import Session

from invision_api.repositories.commission_repository import (
    create_comment,
    list_comments,
    upsert_rubric_score,
    list_rubric_scores,
    upsert_internal_recommendation,
    list_internal_recommendations,
)


def test_create_and_list_comments(db: Session, factory):
    user = factory.user(db)
    profile = factory.profile(db, user)
    app = factory.application(db, profile)
    db.flush()

    create_comment(db, application_id=app.id, author_user_id=user.id, body="Отличная заявка")
    create_comment(db, application_id=app.id, author_user_id=user.id, body="Нужна доп. информация")
    db.flush()

    comments = list_comments(db, application_id=app.id)
    assert len(comments) == 2
    bodies = {c.body for c in comments}
    assert "Отличная заявка" in bodies
    assert "Нужна доп. информация" in bodies


def test_upsert_rubric_score(db: Session, factory):
    user = factory.user(db)
    profile = factory.profile(db, user)
    app = factory.application(db, profile)
    db.flush()

    upsert_rubric_score(db, application_id=app.id, reviewer_user_id=user.id, rubric="motivation", score="strong", comment=None)
    db.flush()
    scores = list_rubric_scores(db, application_id=app.id)
    assert len(scores) == 1
    assert scores[0].rubric == "motivation"
    assert scores[0].score == "strong"

    upsert_rubric_score(db, application_id=app.id, reviewer_user_id=user.id, rubric="motivation", score="excellent", comment="Updated")
    db.flush()
    scores = list_rubric_scores(db, application_id=app.id)
    assert len(scores) == 1
    assert scores[0].score == "excellent"


def test_upsert_internal_recommendation(db: Session, factory):
    user = factory.user(db)
    profile = factory.profile(db, user)
    app = factory.application(db, profile)
    db.flush()

    upsert_internal_recommendation(
        db, application_id=app.id, reviewer_user_id=user.id,
        recommendation="recommend", reason_comment="Strong candidate"
    )
    db.flush()
    recs = list_internal_recommendations(db, application_id=app.id)
    assert len(recs) == 1
    assert recs[0].recommendation == "recommend"
