"""Unit tests for text extraction (no database)."""

from io import BytesIO

from pypdf import PdfWriter

from invision_api.models.enums import ExtractionStatus
from invision_api.services.text_extraction_service import extract_bytes


def _minimal_pdf_bytes() -> bytes:
    w = PdfWriter()
    w.add_blank_page(width=72, height=72)
    buf = BytesIO()
    w.write(buf)
    return buf.getvalue()


def test_extract_pdf() -> None:
    data = _minimal_pdf_bytes()
    out = extract_bytes(mime_type="application/pdf", filename="x.pdf", data=data)
    assert out.status == ExtractionStatus.completed.value
    assert out.text is not None


def test_extract_plain_text() -> None:
    out = extract_bytes(mime_type="text/plain", filename="a.txt", data=b"hello \xd0\xbf\xd1\x80\xd0\xb8\xd0\xb2\xd0\xb5\xd1\x82")
    assert out.status == ExtractionStatus.completed.value
    assert "hello" in (out.text or "")


def test_extract_unsupported() -> None:
    out = extract_bytes(mime_type="application/zip", filename="x.zip", data=b"PK\x00")
    assert out.status == ExtractionStatus.skipped.value
