from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.services.issuer_service import IssuerService
from app.schemas.issuer import (
    IssuerCreateRequest,
    IssuerResponse,
    IssuerStatusResponse,
    IssuerOnChainRegisterRequest,
    IssuerOnChainRegisterResponse,
)
from app.schemas.common import validate_bytes32_hex

from app.core.exceptions import AppException
from app.core.auth.models import AuthenticatedPrincipal
from app.core.auth.dependencies import get_current_principal, require_admin

router = APIRouter(prefix="/issuers", tags=["issuers"])


@router.post("", response_model=IssuerResponse, status_code=status.HTTP_201_CREATED, summary="Create Issuer Record")
def create_issuer(
    req: IssuerCreateRequest,
    db: Session = Depends(get_db),
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
):
    """
    Creates an authorized issuer profile in the database.
    Requires administrator privileges or an accredited institutional token matching the issuer_id.
    Note: Database registration does not imply on-chain smart-contract registration.
    """
    if not principal.is_admin():
        if not principal.has_role("issuer") or not principal.issuer_id or principal.issuer_id.lower() != req.issuer_id.lower():
            raise AppException(
                message="Forbidden: Creating an issuer profile requires administrator privileges or matching accredited issuer authority.",
                error_code="INSUFFICIENT_PERMISSIONS",
                status_code=403,
            )

    service = IssuerService(db)
    return service.create_issuer(req)


@router.get("/{issuer_id}", response_model=IssuerResponse, summary="Get Issuer Details")
def get_issuer(
    issuer_id: str,
    db: Session = Depends(get_db),
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
):
    """
    Retrieves issuer information by 32-byte hex ID, including on-chain registration status if available.
    Requires an authenticated principal.
    """
    valid_id = validate_bytes32_hex(issuer_id, allow_zero=False)
    service = IssuerService(db)
    return service.get_issuer(valid_id)


@router.get("/{issuer_id}/status", response_model=IssuerStatusResponse, summary="Get Issuer Status")
def get_issuer_status(
    issuer_id: str,
    db: Session = Depends(get_db),
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
):
    """
    Retrieves the latest known lifecycle status of the issuer across database and smart-contract layers.
    Requires an authenticated principal.
    """
    valid_id = validate_bytes32_hex(issuer_id, allow_zero=False)
    service = IssuerService(db)
    return service.get_issuer_status(valid_id)


@router.post("/{issuer_id}/register-on-chain", response_model=IssuerOnChainRegisterResponse, summary="Register Issuer in On-Chain Contract")
def register_issuer_on_chain(
    issuer_id: str,
    req: IssuerOnChainRegisterRequest,
    db: Session = Depends(get_db),
    principal: AuthenticatedPrincipal = Depends(require_admin),
):
    """
    Submits on-chain issuer registration to IssuerRegistry contract.
    Restricted to system administrators possessing governance credentials.
    """
    valid_id = validate_bytes32_hex(issuer_id, allow_zero=False)
    service = IssuerService(db)
    res = service.register_issuer_on_chain(
        issuer_id=valid_id,
        signing_address=req.signing_address,
        metadata_uri=req.metadata_uri or "",
    )
    return res
