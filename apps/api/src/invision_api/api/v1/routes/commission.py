"""Commission API (viewer/reviewer/admin)."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from invision_api.api.deps import require_commission_role
from invision_api.commission.application import service as commission_service
from invision_api.commission.application import personal_info_service as commission_personal_info_service
from invision_api.commission.domain.types import (
    CommissionRole,
    FinalDecision,
    InternalRecommendation,
    ReviewerRubric,
    RubricScore,
    StageStatus,
)
from invision_api.db.session import get_db
from invision_api.models.user import User
from invision_api.models.application import Document
from invision_api.repositories import admissions_repository, document_repository
from invision_api.services import candidate_stage_email_service
from invision_api.services.storage import get_storage

router = APIRouter()


@router.get("/me")
def commission_me(
    user: User = Depends(require_commission_role(CommissionRole.viewer)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    from invision_api.models.commission import CommissionUser

    row = db.get(CommissionUser, user.id)
    return {"userId": str(user.id), "role": row.role if row else None}


@router.get("/applications")
def list_applications(
    stage: str | None = None,
    stageStatus: str | None = None,
    attentionOnly: bool = False,
    program: str | None = None,
    search: str | None = None,
    scope: str | None = None,
    interviewKanbanOnly: bool = False,
    limit: int = 50,
    offset: int = 0,
    user: User = Depends(require_commission_role(CommissionRole.viewer)),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    from invision_api.models.enums import ApplicationStage

    mine_uid = user.id if stage == ApplicationStage.interview.value and scope == "mine" else None
    ik = bool(interviewKanbanOnly) and stage == ApplicationStage.interview.value
    rows = commission_service.list_applications(
        db,
        stage=stage,
        stage_status=stageStatus,
        attention_only=attentionOnly,
        program=program,
        search=search,
        limit=min(max(limit, 1), 200),
        offset=max(offset, 0),
        scope=scope,
        current_user_id=mine_uid,
        interview_kanban_only=ik,
    )
    return [r.__dict__ for r in rows]


@router.get("/metrics")
def board_metrics(
    range: str = "week",
    search: str | None = None,
    program: str | None = None,
    _: User = Depends(require_commission_role(CommissionRole.viewer)),
    db: Session = Depends(get_db),
) -> dict[str, int]:
    return commission_service.board_metrics(db, range_value=range, search=search, program=program)


@router.get("/applications/{application_id}")
def get_application(
    application_id: UUID,
    _: User = Depends(require_commission_role(CommissionRole.viewer)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return commission_service.get_application_details(db, application_id)


@router.get("/applications/{application_id}/personal-info")
def get_application_personal_info(
    application_id: UUID,
    user: User = Depends(require_commission_role(CommissionRole.viewer)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return commission_personal_info_service.get_commission_application_personal_info(
        db, application_id=application_id, actor=user
    )


@router.get("/applications/{application_id}/documents/{document_id}/file")
def get_application_document_file(
    application_id: UUID,
    document_id: UUID,
    _: User = Depends(require_commission_role(CommissionRole.viewer)),
    db: Session = Depends(get_db),
) -> Response:
    """Отдать файл заявки для просмотра в браузере (inline, без принудительного скачивания)."""
    if not document_repository.document_belongs_to_application(db, document_id, application_id):
        raise HTTPException(status_code=404, detail="Документ не найден")
    doc = db.get(Document, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Документ не найден")
    try:
        data = get_storage().read_bytes(doc.storage_key)
    except (FileNotFoundError, OSError):
        raise HTTPException(status_code=404, detail="Файл не найден в хранилище")
    media = doc.mime_type or "application/octet-stream"
    fname = doc.original_filename or "document"
    cd = f"inline; filename*=UTF-8''{quote(fname, safe='')}"
    return Response(content=data, media_type=media, headers={"Content-Disposition": cd})


@router.get("/applications/{application_id}/test-info")
def get_application_test_info(
    application_id: UUID,
    _: User = Depends(require_commission_role(CommissionRole.viewer)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return commission_personal_info_service.get_commission_application_test_info(
        db, application_id=application_id
    )


@router.get("/applications/{application_id}/sidebar")
def get_application_sidebar(
    application_id: UUID,
    tab: str = "personal",
    _: User = Depends(require_commission_role(CommissionRole.viewer)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    from invision_api.commission.application import sidebar_service

    return sidebar_service.get_sidebar_panel(db, application_id=application_id, tab=tab)


@router.get("/applications/{application_id}/section-scores")
def get_section_scores(
    application_id: UUID,
    tab: str = "personal",
    user: User = Depends(require_commission_role(CommissionRole.viewer)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    from invision_api.commission.application import section_score_service

    return section_score_service.get_section_scores(
        db,
        application_id=application_id,
        section=tab,
        reviewer_user_id=user.id,
    )


class SectionScoreItem(BaseModel):
    key: str
    score: int = Field(ge=1, le=5)


class SaveSectionScoresBody(BaseModel):
    section: str
    scores: list[SectionScoreItem]


@router.put("/applications/{application_id}/section-scores")
def save_section_scores(
    application_id: UUID,
    body: SaveSectionScoresBody,
    user: User = Depends(require_commission_role(CommissionRole.reviewer)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    from invision_api.commission.application import section_score_service

    result = section_score_service.save_section_scores(
        db,
        application_id=application_id,
        section=body.section,
        reviewer_user_id=user.id,
        scores=[{"key": s.key, "score": s.score} for s in body.scores],
    )
    db.commit()
    return result


class StageAdvanceBody(BaseModel):
    reason_comment: str | None = None


@router.post("/applications/{application_id}/stage/advance")
def stage_advance(
    application_id: UUID,
    body: StageAdvanceBody,
    user: User = Depends(require_commission_role(CommissionRole.reviewer)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    app_before = admissions_repository.get_application_by_id(db, application_id)
    if not app_before:
        raise HTTPException(status_code=404, detail="Заявление не найдено")
    prev_stage = app_before.current_stage
    out = commission_personal_info_service.move_application_to_next_stage(
        db,
        application_id=application_id,
        actor_user_id=user.id,
        reason_comment=body.reason_comment,
    )
    db.commit()
    app_after = admissions_repository.get_application_by_id(db, application_id)
    if app_after and app_after.current_stage != prev_stage:
        candidate_stage_email_service.send_stage_transition_notification(
            application_id, prev_stage, app_after.current_stage
        )
    return out


class StageStatusBody(BaseModel):
    status: StageStatus
    reason_comment: str | None = None


@router.patch("/applications/{application_id}/stage-status")
def patch_stage_status(
    application_id: UUID,
    body: StageStatusBody,
    user: User = Depends(require_commission_role(CommissionRole.reviewer)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    out = commission_service.set_stage_status(
        db,
        application_id=application_id,
        status_value=body.status,
        actor_user_id=user.id,
        reason_comment=body.reason_comment,
    )
    db.commit()
    return out


class AttentionBody(BaseModel):
    value: bool
    reason_comment: str | None = None


@router.patch("/applications/{application_id}/attention")
def patch_attention(
    application_id: UUID,
    body: AttentionBody,
    user: User = Depends(require_commission_role(CommissionRole.reviewer)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    out = commission_service.set_attention(
        db,
        application_id=application_id,
        value=body.value,
        actor_user_id=user.id,
        reason_comment=body.reason_comment,
    )
    db.commit()
    return out


class CommentBody(BaseModel):
    body: str = Field(min_length=1, max_length=5000)


@router.post("/applications/{application_id}/comments")
def create_comment(
    application_id: UUID,
    body: CommentBody,
    user: User = Depends(require_commission_role(CommissionRole.reviewer)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    out = commission_personal_info_service.create_commission_comment(
        db,
        application_id=application_id,
        actor_user_id=user.id,
        text=body.body,
    )
    db.commit()
    return out


@router.get("/applications/{application_id}/comments")
def get_comments(
    application_id: UUID,
    _: User = Depends(require_commission_role(CommissionRole.viewer)),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    return commission_service.list_comments(db, application_id=application_id)


class TagsBody(BaseModel):
    tags: list[str]


@router.put("/applications/{application_id}/tags")
def put_tags(
    application_id: UUID,
    body: TagsBody,
    user: User = Depends(require_commission_role(CommissionRole.reviewer)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    out = commission_service.set_tags(
        db,
        application_id=application_id,
        actor_user_id=user.id,
        tag_keys=body.tags,
    )
    db.commit()
    return out


class RubricItem(BaseModel):
    rubric: ReviewerRubric
    score: RubricScore


class RubricBody(BaseModel):
    items: list[RubricItem]
    comment: str | None = None


@router.put("/applications/{application_id}/rubric")
def put_rubric(
    application_id: UUID,
    body: RubricBody,
    user: User = Depends(require_commission_role(CommissionRole.reviewer)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    scores = {item.rubric: item.score for item in body.items}
    out = commission_service.set_rubric_scores(
        db,
        application_id=application_id,
        reviewer_user_id=user.id,
        scores=scores,
        comment=body.comment,
    )
    db.commit()
    return out


class RecommendationBody(BaseModel):
    recommendation: InternalRecommendation
    reason_comment: str | None = None


@router.put("/applications/{application_id}/internal-recommendation")
def put_internal_recommendation(
    application_id: UUID,
    body: RecommendationBody,
    user: User = Depends(require_commission_role(CommissionRole.reviewer)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    out = commission_service.set_internal_recommendation(
        db,
        application_id=application_id,
        reviewer_user_id=user.id,
        recommendation=body.recommendation,
        reason_comment=body.reason_comment,
    )
    db.commit()
    return out


class FinalDecisionBody(BaseModel):
    final_decision: FinalDecision
    reason_comment: str | None = None


@router.post("/applications/{application_id}/final-decision")
def post_final_decision(
    application_id: UUID,
    body: FinalDecisionBody,
    user: User = Depends(require_commission_role(CommissionRole.reviewer)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    out = commission_service.set_final_decision(
        db,
        application_id=application_id,
        actor_user_id=user.id,
        final_decision=body.final_decision,
        reason_comment=body.reason_comment,
    )
    db.commit()
    candidate_stage_email_service.send_final_decision_notification(application_id, body.final_decision.value)
    return out


@router.get("/applications/{application_id}/audit")
def list_audit(
    application_id: UUID,
    _: User = Depends(require_commission_role(CommissionRole.viewer)),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    return commission_service.list_audit(db, application_id=application_id)


@router.get("/ai-summary/{application_id}")
def get_ai_summary(
    application_id: UUID,
    _: User = Depends(require_commission_role(CommissionRole.viewer)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    row = commission_service.get_ai_summary(db, application_id=application_id)
    return row.__dict__


class AISummaryRunBody(BaseModel):
    force: bool = False


@router.post("/applications/{application_id}/ai-summary/run")
def post_ai_summary_run(
    application_id: UUID,
    body: AISummaryRunBody | None = None,
    user: User = Depends(require_commission_role(CommissionRole.reviewer)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    out = commission_service.run_ai_summary_for_application(
        db,
        application_id=application_id,
        actor_user_id=user.id,
        force=bool(body.force) if body else False,
    )
    db.commit()
    return {"status": out.status, "detail": out.detail, "inputHash": out.input_hash}


class AiInterviewGenerateBody(BaseModel):
    force: bool = False


@router.post("/applications/{application_id}/ai-interview/generate")
def post_ai_interview_generate(
    application_id: UUID,
    body: AiInterviewGenerateBody | None = None,
    user: User = Depends(require_commission_role(CommissionRole.reviewer)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    from invision_api.services.ai_interview import service as ai_interview_service

    force = bool(body.force) if body else False
    out = ai_interview_service.generate_ai_interview_draft(
        db, application_id, force=force, actor_user_id=user.id
    )
    db.commit()
    return out


@router.get("/applications/{application_id}/ai-interview/draft")
def get_ai_interview_draft(
    application_id: UUID,
    _: User = Depends(require_commission_role(CommissionRole.viewer)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    from invision_api.services.ai_interview import service as ai_interview_service

    return ai_interview_service.get_draft_for_commission(db, application_id)


class AiInterviewDraftPatchBody(BaseModel):
    revision: int
    questions: list[dict[str, Any]]


@router.patch("/applications/{application_id}/ai-interview/draft")
def patch_ai_interview_draft(
    application_id: UUID,
    body: AiInterviewDraftPatchBody,
    user: User = Depends(require_commission_role(CommissionRole.reviewer)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    from invision_api.services.ai_interview import service as ai_interview_service

    out = ai_interview_service.patch_draft_questions(
        db,
        application_id,
        revision=body.revision,
        questions=body.questions,
        actor_user_id=user.id,
    )
    db.commit()
    return out


@router.post("/applications/{application_id}/ai-interview/approve")
def post_ai_interview_approve(
    application_id: UUID,
    user: User = Depends(require_commission_role(CommissionRole.reviewer)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    from invision_api.repositories import admissions_repository
    from invision_api.services.ai_interview import service as ai_interview_service

    app_before = admissions_repository.get_application_by_id(db, application_id)
    if not app_before:
        raise HTTPException(status_code=404, detail="Заявление не найдено")
    prev_stage = app_before.current_stage
    out = ai_interview_service.approve_ai_interview(db, application_id, actor_user_id=user.id)
    db.commit()
    if out.get("alreadyApproved"):
        return out
    app_after = admissions_repository.get_application_by_id(db, application_id)
    if app_after and app_after.current_stage != prev_stage:
        candidate_stage_email_service.send_stage_transition_notification(
            application_id, prev_stage, app_after.current_stage
        )
    return out


@router.get("/applications/{application_id}/ai-interview/candidate-session")
def get_ai_interview_candidate_session(
    application_id: UUID,
    _: User = Depends(require_commission_role(CommissionRole.viewer)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    from invision_api.services.ai_interview import service as ai_interview_service

    return ai_interview_service.build_commission_ai_interview_session_view(db, application_id)


@router.delete("/applications/{application_id}")
def delete_application(
    application_id: UUID,
    _: User = Depends(require_commission_role(CommissionRole.admin)),
    db: Session = Depends(get_db),
) -> Response:
    """Hard-delete an application (admin / testing only). All related rows cascade."""
    from invision_api.models.application import Application
    from fastapi import HTTPException

    app = db.get(Application, application_id)
    if app is None:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    db.delete(app)
    db.commit()
    return Response(status_code=204)


@router.get("/updates")
def get_updates(
    cursor: str | None = None,
    _: User = Depends(require_commission_role(CommissionRole.viewer)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return commission_service.list_updates(db, cursor=cursor)


class ExportBody(BaseModel):
    format: str = "csv"
    filter_payload: dict[str, Any] | None = None


@router.post("/exports")
def create_export(
    body: ExportBody,
    user: User = Depends(require_commission_role(CommissionRole.admin)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    if body.format != "csv":
        return {"error": "MVP поддерживает только csv", "status": "not_implemented"}
    job = commission_service.create_export_csv_job(
        db,
        actor_user_id=user.id,
        filter_payload=body.filter_payload,
    )
    db.commit()
    return {"jobId": str(job.id), "status": job.status}


@router.get("/exports/{job_id}")
def get_export_result(
    job_id: UUID,
    user: User = Depends(require_commission_role(CommissionRole.admin)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    from invision_api.models.commission import ExportJob

    job = db.get(ExportJob, job_id)
    if not job:
        return {"error": "not_found"}
    return {
        "jobId": str(job.id),
        "status": job.status,
        "format": job.format,
        "resultStorageKey": job.result_storage_key,
        "completedAt": job.completed_at.isoformat() if job.completed_at else None,
    }

