"""Validation sidebar: «Документы» block with ЕНТ / IELTS from certificate_validation payload."""

from types import SimpleNamespace
from uuid import uuid4

from invision_api.commission.application.sidebar_service import _build_documents_scores_items


def test_documents_scores_ent_threshold_and_ielts() -> None:
    english_id = uuid4()
    certificate_id = uuid4()
    unit = SimpleNamespace(
        result_payload={
            "results": [
                {
                    "documentType": "ent",
                    "examDocument": {
                        "documentId": str(certificate_id),
                        "detectedScore": 79,
                    },
                },
                {
                    "documentType": "ielts",
                    "examDocument": {
                        "documentId": str(english_id),
                        "detectedScore": 6.7,
                    },
                },
            ]
        }
    )
    items = _build_documents_scores_items(
        unit,
        english_document_id=english_id,
        certificate_document_id=certificate_id,
    )
    assert items[0] == {"text": "ЕНТ: 79", "tone": "danger"}
    assert items[1] == {"text": "IELTS: 6.7", "tone": "success"}


def test_documents_scores_ielts_below_threshold_red() -> None:
    english_id = uuid4()
    certificate_id = uuid4()
    unit = SimpleNamespace(
        result_payload={
            "results": [
                {
                    "examDocument": {
                        "documentId": str(certificate_id),
                        "detectedScore": 100,
                    },
                },
                {
                    "examDocument": {
                        "documentId": str(english_id),
                        "detectedScore": 5.5,
                    },
                },
            ]
        }
    )
    items = _build_documents_scores_items(
        unit,
        english_document_id=english_id,
        certificate_document_id=certificate_id,
    )
    assert items[1] == {"text": "IELTS: 5.5", "tone": "danger"}


def test_documents_scores_ent_pass_green() -> None:
    english_id = uuid4()
    certificate_id = uuid4()
    unit = SimpleNamespace(
        result_payload={
            "results": [
                {
                    "examDocument": {
                        "documentId": str(certificate_id),
                        "detectedScore": 80,
                    },
                },
            ]
        }
    )
    items = _build_documents_scores_items(
        unit,
        english_document_id=english_id,
        certificate_document_id=certificate_id,
    )
    assert items[0] == {"text": "ЕНТ: 80", "tone": "success"}
