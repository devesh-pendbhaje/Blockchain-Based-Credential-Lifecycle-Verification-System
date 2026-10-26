from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.services.credential_service import CredentialService
from app.schemas.credential import (
    CredentialCreateRequest,
    CredentialResponse,
    CredentialVersionResponse,
    VerificationResponse,
)
from app.schemas.common import validate_bytes32_hex

from app.core.auth.models import AuthenticatedPrincipal
from app.core.auth.dependencies import require_issuer, verify_issuer_tenant_ownership, get_current_principal

router = APIRouter(prefix="/credentials", tags=["credentials"])


@router.post("", response_model=CredentialResponse, status_code=status.HTTP_201_CREATED, summary="Create Credential Issuance")
def create_credential(
    req: CredentialCreateRequest,
    db: Session = Depends(get_db),
    principal: AuthenticatedPrincipal = Depends(require_issuer),
):
    """
    Accepts, validates, and persists an authorized credential issuance request.
    Enforces institutional tenant authorization (cross-tenant IDOR protection).
    Computes the authoritative 6-input composite fingerprint and prepares the lifecycle record.
    """
    verify_issuer_tenant_ownership(principal, req.issuer_id)
    service = CredentialService(db)
    return service.create_credential(req)


@router.get("", response_model=List[CredentialResponse], summary="List Issued Credentials")
def list_credentials(
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
):
    """
    Retrieves a paginated list of issued credentials.
    Requires an authenticated principal. Enforces tenant boundaries for issuers.
    """
    service = CredentialService(db)
    return service.list_credentials(limit=limit, offset=offset, principal=principal)


@router.get("/fingerprint/{fingerprint}", response_model=CredentialResponse, summary="Get Credential by Fingerprint")
def get_credential_by_fingerprint(
    fingerprint: str,
    db: Session = Depends(get_db),
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
):
    """
    Retrieves the credential record matching an exact composite fingerprint.
    Requires an authenticated principal. Enforces tenant boundaries for issuers.
    """
    valid_fp = validate_bytes32_hex(fingerprint, allow_zero=False)
    service = CredentialService(db)
    return service.get_by_fingerprint(valid_fp, principal=principal)


@router.get("/fingerprint/{fingerprint}/verify", response_model=VerificationResponse, summary="Verify Credential by Fingerprint")
def verify_credential_by_fingerprint(
    fingerprint: str,
    db: Session = Depends(get_db),
):
    """
    Performs comprehensive zero-trust public verification:
    1. Resolves database presence.
    2. Performs on-chain query if contract is connected.
    3. Verifies dynamic expiration and digest integrity.
    Does NOT report valid: true if blockchain verification is unavailable.
    Does NOT expose PII, document contents, salts, or tenant-isolated metadata.
    Publicly accessible without authentication.
    """
    valid_fp = validate_bytes32_hex(fingerprint, allow_zero=False)
    service = CredentialService(db)
    return service.verify_credential(valid_fp)


@router.get("/{credential_id}", response_model=CredentialResponse, summary="Get Credential by Credential ID")
def get_credential(
    credential_id: str,
    db: Session = Depends(get_db),
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
):
    """
    Retrieves current credential status and version for a given business credential ID.
    Requires an authenticated principal. Enforces tenant boundaries for issuers.
    """
    valid_id = validate_bytes32_hex(credential_id, allow_zero=False)
    service = CredentialService(db)
    return service.get_credential(valid_id, principal=principal)


@router.get("/{credential_id}/versions", response_model=List[CredentialVersionResponse], summary="Get Credential Version History")
def get_credential_versions(
    credential_id: str,
    db: Session = Depends(get_db),
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
):
    """
    Retrieves the historical chronological version sequence for a credential.
    Requires an authenticated principal. Enforces tenant boundaries for issuers.
    """
    valid_id = validate_bytes32_hex(credential_id, allow_zero=False)
    service = CredentialService(db)
    return service.get_credential_versions(valid_id, principal=principal)


@router.post("/{credential_id}/versions/{version}/anchor", response_model=CredentialResponse, summary="Reconcile or Retry Credential Anchoring")
def reconcile_or_anchor_credential(
    credential_id: str,
    version: int,
    db: Session = Depends(get_db),
    principal: AuthenticatedPrincipal = Depends(require_issuer),
):
    """
    Submits or reconciles on-chain anchoring for a credential version.
    Idempotently verifies whether the fingerprint is already anchored on-chain before submission.
    Requires an authorized issuer or admin principal.
    """
    valid_id = validate_bytes32_hex(credential_id, allow_zero=False)
    service = CredentialService(db)
    return service.reconcile_and_anchor_credential(valid_id, version, principal=principal)
