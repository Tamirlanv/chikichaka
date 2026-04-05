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
        additional_document_id=None,
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
        additional_document_id=None,
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
        additional_document_id=None,
    )
    assert items[0] == {"text": "ЕНТ: 80", "tone": "success"}
    assert items[1] == {"text": "IELTS/TOEFL: —", "tone": "neutral"}


def test_documents_scores_resolves_english_via_additional_slot_and_ocr() -> None:
    """IELTS in additional attachment: UUID matches additional_document_id; score maps to English line."""
    english_id = uuid4()
    certificate_id = uuid4()
    additional_id = uuid4()
    unit = SimpleNamespace(
        result_payload={
            "results": [
                {
                    "documentType": "unknown",
                    "examDocument": {
                        "documentId": str(additional_id),
                        "ocrDocumentType": "ielts",
                        "detectedScore": 6.0,
                    },
                },
            ]
        }
    )
    items = _build_documents_scores_items(
        unit,
        english_document_id=english_id,
        certificate_document_id=certificate_id,
        additional_document_id=additional_id,
    )
    assert items[1] == {"text": "IELTS: 6.0", "tone": "success"}


def test_documents_scores_unknown_resolved_type_uses_ocr_document_type() -> None:
    """When resolved documentType is unknown but ocrDocumentType is ielts, fallback still maps to English."""
    english_id = uuid4()
    cert_id = uuid4()
    unit = SimpleNamespace(
        result_payload={
            "results": [
                {
                    "documentType": "unknown",
                    "examDocument": {
                        "documentId": str(english_id),
                        "documentType": "unknown",
                        "ocrDocumentType": "ielts",
                        "detectedScore": 6.5,
                    },
                },
            ]
        }
    )
    items = _build_documents_scores_items(
        unit,
        english_document_id=english_id,
        certificate_document_id=cert_id,
        additional_document_id=None,
    )
    assert items[1] == {"text": "IELTS: 6.5", "tone": "success"}


def test_documents_scores_nis_certificate_line() -> None:
    certificate_id = uuid4()
    english_id = uuid4()
    unit = SimpleNamespace(
        result_payload={
            "results": [
                {
                    "documentType": "nis_12",
                    "examDocument": {
                        "documentId": str(certificate_id),
                        "detectedScore": 110,
                    },
                },
            ]
        }
    )
    items = _build_documents_scores_items(
        unit,
        english_document_id=english_id,
        certificate_document_id=certificate_id,
        additional_document_id=None,
    )
    assert items[0] == {"text": "NIS: 110", "tone": "success"}


def test_documents_scores_toefl_line() -> None:
    english_id = uuid4()
    certificate_id = uuid4()
    unit = SimpleNamespace(
        result_payload={
            "results": [
                {
                    "documentType": "toefl",
                    "examDocument": {
                        "documentId": str(english_id),
                        "detectedScore": 95,
                    },
                },
            ]
        }
    )
    items = _build_documents_scores_items(
        unit,
        english_document_id=english_id,
        certificate_document_id=certificate_id,
        additional_document_id=None,
    )
    assert items[1] == {"text": "TOEFL: 95", "tone": "success"}
