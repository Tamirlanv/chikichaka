"""Enqueue background jobs (Redis list) and persist AnalysisJob rows."""

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from invision_api.core.redis_client import enqueue_job
from invision_api.models.enums import JobStatus, JobType
from invision_api.repositories import admissions_repository

QUEUE_NAME = "invision:admission_jobs"


def enqueue_extract_text(db: Session, application_id: UUID, document_id: UUID) -> None:
    admissions_repository.create_analysis_job(
        db,
        application_id,
        job_type=JobType.extract_text.value,
        payload={"document_id": str(document_id)},
        status=JobStatus.queued.value,
    )
    enqueue_job(
        QUEUE_NAME,
        {
            "job_type": JobType.extract_text.value,
            "application_id": str(application_id),
            "document_id": str(document_id),
        },
    )


def enqueue_run_block_analysis(
    db: Session,
    application_id: UUID,
    *,
    block_key: str,
    source_document_id: UUID | None = None,
) -> None:
    payload: dict[str, Any] = {"block_key": block_key}
    if source_document_id:
        payload["source_document_id"] = str(source_document_id)
    admissions_repository.create_analysis_job(
        db,
        application_id,
        job_type=JobType.run_block_analysis.value,
        payload=payload,
        status=JobStatus.queued.value,
    )
    enqueue_job(
        QUEUE_NAME,
        {
            "job_type": JobType.run_block_analysis.value,
            "application_id": str(application_id),
            **payload,
        },
    )


def enqueue_initial_screening_job(db: Session, application_id: UUID) -> None:
    admissions_repository.create_analysis_job(
        db,
        application_id,
        job_type=JobType.initial_screening.value,
        payload={},
        status=JobStatus.queued.value,
    )
    enqueue_job(
        QUEUE_NAME,
        {"job_type": JobType.initial_screening.value, "application_id": str(application_id)},
    )
