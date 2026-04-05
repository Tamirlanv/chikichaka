from uuid import uuid4

from sqlalchemy.orm import Session

from invision_api.api.v1.routes import commission as commission_routes
from invision_api.models.application import Document
from invision_api.models.enums import DocumentType


def test_commission_document_file_uses_storage_fallback_reader(
    db: Session,
    factory,
    monkeypatch,
) -> None:
    user = factory.user(db)
    profile = factory.profile(db, user)
    app = factory.application(db, profile)
    doc = Document(
        id=uuid4(),
        application_id=app.id,
        original_filename="result.pdf",
        mime_type="application/pdf",
        byte_size=128,
        storage_key="documents/result.pdf",
        document_type=DocumentType.supporting_documents.value,
    )
    db.add(doc)
    db.flush()

    called: dict[str, str] = {}

    def _fake_read_document_bytes_with_fallback(*, document_id, storage_key):
        called["document_id"] = str(document_id)
        called["storage_key"] = storage_key
        return b"%PDF-1.7"

    monkeypatch.setattr(
        "invision_api.api.v1.routes.commission.read_document_bytes_with_fallback",
        _fake_read_document_bytes_with_fallback,
    )

    response = commission_routes.get_application_document_file(
        application_id=app.id,
        document_id=doc.id,
        _=None,
        db=db,
    )

    assert called["document_id"] == str(doc.id)
    assert called["storage_key"] == doc.storage_key
    assert response.media_type == "application/pdf"
    assert response.body.startswith(b"%PDF")
