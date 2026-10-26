from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.services.selective_disclosure_service import SelectiveDisclosureService
from app.repositories.credential_repository import CredentialRepository
from app.schemas.presentation import (
    PresentationGenerateRequest,
    PresentationResponse,
    PresentationVerifyRequest,
    PresentationVerifyResponse,
)

from app.core.auth.models import AuthenticatedPrincipal
from app.core.auth.dependencies import get_current_principal, require_verifier

router = APIRouter(prefix="/presentations", tags=["presentations"])


@router.post(
    "/generate",
    response_model=PresentationResponse,
    summary="Generate Selective Disclosure Presentation",
)
def generate_presentation(
    req: PresentationGenerateRequest,
    db: Session = Depends(get_db),
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
):
    """
    Generates a selective disclosure presentation revealing only requested attributes,
    opening salts, and Merkle proofs bound to the composite fingerprint and challenge.
    Requires an authenticated principal.
    """
    svc = SelectiveDisclosureService(db)
    result = svc.generate_presentation(
        credential_id=req.credential_id,
        version=req.version,
        attributes=req.attributes,
        salts=req.salts,
        disclosed_keys=req.disclosed_keys,
        document_digest=req.document_digest,
        metadata_digest=req.metadata_digest,
        issuer_id=req.issuer_id,
        challenge_id=req.challenge_id,
        challenge_nonce=req.challenge_nonce,
    )
    return PresentationResponse(**result)


@router.post(
    "/verify",
    response_model=PresentationVerifyResponse,
    summary="Verify Selective Disclosure Presentation & Challenge",
)
def verify_presentation(
    req: PresentationVerifyRequest,
    db: Session = Depends(get_db),
    principal: AuthenticatedPrincipal = Depends(require_verifier),
):
    """
    Verifies selective disclosure presentation:
    - Recomputes leaf hashes and validates Merkle proofs against root.
    - Atomically consumes verifier challenge (single-use replay prevention and verifier principal binding).
    - Verifies composite fingerprint binding.
    - Resolves database lifecycle status and checks version recency.
    - Resolves on-chain status and issuer standing if blockchain node is available.
    Does not leak certificate contents or secret payloads.
    Requires an authenticated verifier principal.
    """
    svc = SelectiveDisclosureService(db)
    outcome = svc.verify_presentation(
        presentation=req.presentation,
        verifier_session_id=req.verifier_session_id,
        require_current_version=req.require_current_version,
        verifier_principal=principal.subject,
    )

    # Record operational audit event without sensitive claim values
    fp = req.presentation.get("credential_fingerprint", "unknown")
    cred_repo = CredentialRepository(db)
    cred_repo.record_audit(
        event_type="PRESENTATION_VERIFIED",
        entity_type="CREDENTIAL_PRESENTATION",
        entity_id=fp,
        outcome="SUCCESS" if outcome["overall_valid"] else "FAILURE",
        correlation_id=req.verifier_session_id,
        details_json=None,
    )
    db.commit()

    return PresentationVerifyResponse(**outcome)
