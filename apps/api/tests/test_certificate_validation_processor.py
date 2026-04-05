"""Unit tests for certificate validation payload and row mapping."""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

from invision_api.models.application import Document
from invision_api.services.data_check.processors.certificate_validation_processor import (
    _build_validation_payload,
    _row_from_response,
)


def test_build_validation_payload_includes_skip_persistence_and_role() -> None:
    doc = MagicMock(spec=Document)
    doc.mime_type = "image/jpeg"
    doc.original_filename = "cert.jpg"
    raw = b"\xff\xd8\xff\xe0fake jpeg"
    payload = _build_validation_payload(
        application_id=uuid4(),
        doc=doc,
        raw=raw,
        role="certificate",
        english_proof_kind=None,
        certificate_proof_kind="ent",
    )
    assert payload.get("skipPersistence") is True
    assert payload.get("documentRole") == "certificate"
    assert payload.get("certificateProofKind") == "ent"
    assert "imageBase64" in payload or "plainText" in payload


def test_row_from_response_maps_exam_document() -> None:
    app_id = uuid4()
    doc_id = uuid4()
    data = {
        "documentType": "ielts",
        "processingStatus": "processed",
        "extractedFields": {
            "totalScore": 6.5,
            "ocrDocumentType": "ielts",
            "targetFieldFound": True,
            "targetFieldType": "ielts_overall_band",
            "targetFieldEvidence": "overall band score 6.5",
        },
        "scoreLabel": "overall band score",
        "passedThreshold": True,
        "thresholdType": "ielts",
        "thresholdChecks": {"ieltsMinPassed": True},
        "authenticity": {
            "status": "likely_authentic",
            "templateMatchScore": 0.9,
            "ocrConfidence": 0.8,
            "fraudSignals": [],
        },
        "warnings": [],
        "errors": [],
        "explainability": [],
        "confidence": 0.85,
    }
    row = _row_from_response(app_id, doc_id, data, document_role="english")
    assert row.document_type == "ielts"
    assert row.extracted_fields["examDocument"]["detectedScore"] == 6.5
    assert row.extracted_fields["examDocument"]["passedThreshold"] is True
    assert row.extracted_fields["examDocument"]["targetFieldFound"] is True
    assert row.extracted_fields["examDocument"]["targetFieldType"] == "ielts_overall_band"
