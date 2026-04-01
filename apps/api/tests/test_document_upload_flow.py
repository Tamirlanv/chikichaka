"""Integration tests for document upload and manifest recompute."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from invision_api.models.application import Document
from invision_api.models.enums import DocumentType


def test_document_created_with_correct_type(db: Session, factory):
    """Documents are stored with the declared type."""
    user = factory.user(db)
    profile = factory.profile(db, user)
    app = factory.application(db, profile)
    db.flush()

    doc = Document(
        id=uuid4(),
        application_id=app.id,
        original_filename="transcript.pdf",
        mime_type="application/pdf",
        byte_size=12345,
        storage_key="uploads/transcript.pdf",
        document_type=DocumentType.transcript.value,
    )
    db.add(doc)
    db.flush()

    assert doc.document_type == "transcript"
    assert doc.application_id == app.id


def test_multiple_documents_same_type(db: Session, factory):
    """Multiple documents of the same type can be uploaded."""
    user = factory.user(db)
    profile = factory.profile(db, user)
    app = factory.application(db, profile)
    db.flush()

    for i in range(3):
        db.add(Document(
            id=uuid4(),
            application_id=app.id,
            original_filename=f"cert_{i}.pdf",
            mime_type="application/pdf",
            byte_size=1000 + i,
            storage_key=f"uploads/cert_{i}.pdf",
            document_type=DocumentType.certificate_of_social_status.value,
        ))
    db.flush()

    docs = db.query(Document).filter(
        Document.application_id == app.id,
        Document.document_type == DocumentType.certificate_of_social_status.value,
    ).all()
    assert len(docs) == 3


def test_document_belongs_to_application(db: Session, factory):
    """Document lookup respects application_id boundary."""
    user = factory.user(db)
    profile = factory.profile(db, user)
    app1 = factory.application(db, profile)

    user2 = factory.user(db, email="other@example.com")
    profile2 = factory.profile(db, user2)
    app2 = factory.application(db, profile2)
    db.flush()

    doc = Document(
        id=uuid4(),
        application_id=app1.id,
        original_filename="file.pdf",
        mime_type="application/pdf",
        byte_size=100,
        storage_key="uploads/file.pdf",
        document_type=DocumentType.supporting_documents.value,
    )
    db.add(doc)
    db.flush()

    found = db.query(Document).filter(
        Document.id == doc.id,
        Document.application_id == app2.id,
    ).first()
    assert found is None
