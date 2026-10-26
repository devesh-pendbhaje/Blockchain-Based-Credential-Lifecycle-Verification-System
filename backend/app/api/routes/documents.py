from fastapi import APIRouter, UploadFile, File, Depends, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.crypto.document import compute_document_digest
from app.crypto.metadata import canonicalize_and_hash_metadata
from app.storage.service import CertificateStorageService
from app.repositories.storage_repository import StorageRepository
from app.repositories.credential_repository import CredentialRepository
from app.schemas.document import (
    DocumentUploadResponse,
    CanonicalMetadataRequest,
    CanonicalMetadataResponse,
    StorageMetadataResponse,
)

from app.core.auth.models import AuthenticatedPrincipal
from app.core.auth.dependencies import get_current_principal
from app.core.exceptions import AppException

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and Encrypt Certificate Document",
)
async def upload_certificate(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
):
    """
    Accepts bounded certificate upload from authorized issuer or administrator, computes
    deterministic SHA-256 over raw file bytes, encrypts the file at rest with AES-256-GCM
    using unique nonce and AAD binding, persists off-chain under an isolated server-generated UUID.
    """
    if not principal.has_role("issuer") and not principal.is_admin():
        raise AppException(
            message="Forbidden: Document upload requires issuer or administrator privileges.",
            error_code="INSUFFICIENT_PERMISSIONS",
            status_code=403,
        )
    # 1. Compute digest and detect content type using streaming/bounded read
    digest, mime_type, total_size, raw_bytes = compute_document_digest(file.file)

    # 2. Encrypt and store off-chain
    storage_svc = CertificateStorageService()
    meta = storage_svc.store_certificate(
        raw_bytes=raw_bytes,
        content_type=mime_type,
        document_digest=digest,
    )

    # 3. Persist non-sensitive metadata in PostgreSQL
    storage_repo = StorageRepository(db)
    cred_repo = CredentialRepository(db)

    storage_repo.create(
        storage_id=meta["storage_id"],
        document_digest=digest,
        content_type=mime_type,
        byte_size=total_size,
        storage_adapter=meta["storage_adapter"],
        envelope_version=1,
    )

    # Record operational audit event without sensitive payloads
    cred_repo.record_audit(
        event_type="CERTIFICATE_ENCRYPTED_AND_STORED",
        entity_type="STORAGE_OBJECT",
        entity_id=meta["storage_id"],
        outcome="SUCCESS",
        correlation_id=meta["storage_id"],
        details_json=None,
    )
    db.commit()

    return DocumentUploadResponse(
        storage_id=meta["storage_id"],
        document_digest=digest,
        content_type=mime_type,
        byte_size=total_size,
        storage_adapter=meta["storage_adapter"],
        created_at=meta["created_at"],
    )


@router.post(
    "/canonical-metadata",
    response_model=CanonicalMetadataResponse,
    summary="Compute RFC 8785 Canonical Metadata Digest",
)
def canonicalize_metadata(
    req: CanonicalMetadataRequest,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
):
    """
    Parses and canonicalizes JSON metadata according to RFC 8785 (JCS),
    rejects duplicate keys, and computes the authoritative Keccak-256 metadataDigest.
    Requires an authenticated principal.
    """
    digest, canonical_bytes = canonicalize_and_hash_metadata(req.metadata)
    return CanonicalMetadataResponse(
        metadata_digest=digest,
        canonical_bytes_length=len(canonical_bytes),
        canonical_json=canonical_bytes.decode("utf-8"),
    )


@router.get(
    "/{storage_id}/metadata",
    response_model=StorageMetadataResponse,
    summary="Inspect Non-Sensitive Certificate Storage Metadata",
)
def get_certificate_metadata(
    storage_id: str,
    db: Session = Depends(get_db),
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
):
    """
    Retrieves non-sensitive off-chain storage metadata.
    Does NOT return decrypted certificate contents, ciphertext, or encryption keys.
    Requires an authenticated principal.
    """
    storage_repo = StorageRepository(db)
    record = storage_repo.get_by_storage_id(storage_id)
    if not record:
        # Check storage service adapter directly
        storage_svc = CertificateStorageService()
        meta = storage_svc.get_metadata(storage_id)
        return StorageMetadataResponse(
            storage_id=storage_id,
            document_digest=meta["document_digest"],
            content_type=meta["content_type"],
            byte_size=meta["byte_size"],
            envelope_version=meta.get("envelope_version", 1),
            created_at=meta.get("created_at"),
        )

    return StorageMetadataResponse(
        storage_id=record.storage_id,
        document_digest=record.document_digest,
        content_type=record.content_type,
        byte_size=record.byte_size,
        envelope_version=record.envelope_version,
        created_at=record.created_at.isoformat() if record.created_at else None,
    )
