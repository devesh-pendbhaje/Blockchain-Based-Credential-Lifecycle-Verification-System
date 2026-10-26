import io
import hashlib
import pytest
from app.crypto.document import compute_document_digest, detect_content_type
from app.core.exceptions import AppException


def test_document_digest_determinism():
    """
    Validates that the exact same file bytes always yield the identical SHA-256 digest.
    """
    pdf_bytes = b"%PDF-1.4\n%test deterministic document content\n%%EOF"
    digest1, mime1, size1, _ = compute_document_digest(pdf_bytes)
    digest2, mime2, size2, _ = compute_document_digest(io.BytesIO(pdf_bytes))

    assert digest1 == digest2
    assert mime1 == "application/pdf"
    assert size1 == len(pdf_bytes)
    assert digest1 == "0x" + hashlib.sha256(pdf_bytes).hexdigest()


def test_document_digest_sensitivity():
    """
    Validates that mutating even a single bit in the file bytes produces a distinct digest.
    """
    pdf_bytes_1 = b"%PDF-1.4\n%Certificate for Alice\n%%EOF"
    pdf_bytes_2 = b"%PDF-1.4\n%Certificate for Bob\n%%EOF"

    digest1, _, _, _ = compute_document_digest(pdf_bytes_1)
    digest2, _, _, _ = compute_document_digest(pdf_bytes_2)

    assert digest1 != digest2


def test_document_rejects_empty_payload():
    """
    Rejects empty (0-byte) uploads immediately.
    """
    with pytest.raises(AppException) as exc_info:
        compute_document_digest(b"")
    assert exc_info.value.error_code == "EMPTY_DOCUMENT_NOT_ALLOWED"

    with pytest.raises(AppException) as exc_info:
        compute_document_digest(io.BytesIO(b""))
    assert exc_info.value.error_code == "EMPTY_DOCUMENT_NOT_ALLOWED"


def test_document_enforces_upload_size_limit():
    """
    Rejects uploads exceeding configurable maximum byte limits.
    """
    small_limit = 100
    oversized = b"%PDF-1.4" + b"X" * 200

    with pytest.raises(AppException) as exc_info:
        compute_document_digest(oversized, max_size_bytes=small_limit)
    assert exc_info.value.error_code == "DOCUMENT_SIZE_EXCEEDED"


def test_document_content_type_detection_magic_bytes():
    """
    Validates magic byte content type detection for PDF, PNG, and JPEG,
    and rejects unsupported formats (e.g. text/plain, exe).
    """
    pdf_header = b"%PDF-1.7\n..."
    png_header = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
    jpeg_header = b"\xff\xd8\xff\xe0\x00\x10JFIF"

    assert detect_content_type(pdf_header) == "application/pdf"
    assert detect_content_type(png_header) == "image/png"
    assert detect_content_type(jpeg_header) == "image/jpeg"

    # Reject plain text or executables
    with pytest.raises(AppException) as exc_info:
        detect_content_type(b"Plain text file")
    assert exc_info.value.error_code == "UNSUPPORTED_CONTENT_TYPE"

    with pytest.raises(AppException) as exc_info:
        detect_content_type(b"MZ\x90\x00\x03\x00\x00\x00")
    assert exc_info.value.error_code == "UNSUPPORTED_CONTENT_TYPE"
