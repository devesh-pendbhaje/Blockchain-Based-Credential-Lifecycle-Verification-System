import hashlib
from typing import BinaryIO, Tuple
from app.core.config import settings
from app.core.exceptions import AppException

# Permitted MIME types and their leading magic byte signatures
SUPPORTED_MAGIC_SIGNATURES = {
    b"%PDF-": "application/pdf",
    b"\x89PNG\r\n\x1a\n": "image/png",
    b"\xff\xd8\xff": "image/jpeg",
}

DEFAULT_CHUNK_SIZE = 65536  # 64 KB streaming chunks


def detect_content_type(header_bytes: bytes) -> str:
    """
    Detects supported content type from leading magic bytes.
    Does not trust client-supplied MIME types or filenames.
    """
    for magic, mime in SUPPORTED_MAGIC_SIGNATURES.items():
        if header_bytes.startswith(magic):
            return mime
    raise AppException(
        message="Unsupported file content type. Only PDF (application/pdf), PNG (image/png), and JPEG (image/jpeg) are supported.",
        error_code="UNSUPPORTED_CONTENT_TYPE",
        status_code=415,
    )


def compute_document_digest(
    stream_or_bytes: BinaryIO | bytes,
    max_size_bytes: int = settings.MAX_UPLOAD_SIZE_BYTES,
) -> Tuple[str, str, int, bytes]:
    """
    Computes deterministic SHA-256 digest over the raw certificate bytes.
    Streams input in bounded chunks to avoid excessive memory usage.

    Returns:
        Tuple of (digest_hex, detected_mime_type, total_byte_count, complete_bytes)
    """
    hasher = hashlib.sha256()
    total_bytes = 0
    all_chunks = []
    first_chunk = True
    detected_mime = ""

    if isinstance(stream_or_bytes, bytes):
        raw_bytes = stream_or_bytes
        total_bytes = len(raw_bytes)
        if total_bytes == 0:
            raise AppException(
                message="Empty certificate file is not allowed.",
                error_code="EMPTY_DOCUMENT_NOT_ALLOWED",
                status_code=400,
            )
        if total_bytes > max_size_bytes:
            raise AppException(
                message=f"Uploaded document ({total_bytes} bytes) exceeds maximum limit ({max_size_bytes} bytes).",
                error_code="DOCUMENT_SIZE_EXCEEDED",
                status_code=413,
            )
        detected_mime = detect_content_type(raw_bytes[:16])
        hasher.update(raw_bytes)
        digest = "0x" + hasher.hexdigest().lower()
        return digest, detected_mime, total_bytes, raw_bytes

    # If file-like stream
    while True:
        chunk = stream_or_bytes.read(DEFAULT_CHUNK_SIZE)
        if not chunk:
            break
        if first_chunk:
            detected_mime = detect_content_type(chunk[:16])
            first_chunk = False
        total_bytes += len(chunk)
        if total_bytes > max_size_bytes:
            raise AppException(
                message=f"Uploaded document exceeds maximum allowed limit of {max_size_bytes} bytes.",
                error_code="DOCUMENT_SIZE_EXCEEDED",
                status_code=413,
            )
        hasher.update(chunk)
        all_chunks.append(chunk)

    if total_bytes == 0:
        raise AppException(
            message="Empty certificate file is not allowed.",
            error_code="EMPTY_DOCUMENT_NOT_ALLOWED",
            status_code=400,
        )

    digest = "0x" + hasher.hexdigest().lower()
    return digest, detected_mime, total_bytes, b"".join(all_chunks)
