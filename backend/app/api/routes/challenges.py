from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.services.challenge_service import ChallengeService
from app.repositories.credential_repository import CredentialRepository
from app.schemas.challenge import (
    ChallengeCreateRequest,
    ChallengeCreateResponse,
)

from app.core.auth.models import AuthenticatedPrincipal
from app.core.auth.dependencies import require_verifier

router = APIRouter(prefix="/challenges", tags=["challenges"])


@router.post(
    "",
    response_model=ChallengeCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Issue Verifier Challenge Nonce",
)
def create_challenge(
    req: ChallengeCreateRequest,
    db: Session = Depends(get_db),
    principal: AuthenticatedPrincipal = Depends(require_verifier),
):
    """
    Issues an unpredictable 256-bit single-use random nonce challenge bound to an authenticated verifier principal.
    Persists only the SHA-256 hash in PostgreSQL to prevent database disclosure.
    Returns the challenge nonce to the caller for proof generation.
    """
    svc = ChallengeService(db)
    result = svc.create_challenge(
        verifier_session_id=req.verifier_session_id,
        credential_fingerprint=req.credential_fingerprint,
        expiry_seconds=req.expiry_seconds,
        verifier_principal=principal.subject,
    )

    # Log non-sensitive audit event (no raw nonce)
    cred_repo = CredentialRepository(db)
    cred_repo.record_audit(
        event_type="VERIFIER_CHALLENGE_ISSUED",
        entity_type="CHALLENGE",
        entity_id=result["challenge_id"],
        outcome="SUCCESS",
        correlation_id=result["challenge_id"],
        details_json=None,
    )
    db.commit()

    return ChallengeCreateResponse(
        challenge_id=result["challenge_id"],
        challenge_nonce=result["challenge_nonce"],
        verifier_session_id=result["verifier_session_id"],
        verifier_principal=result.get("verifier_principal", ""),
        credential_fingerprint=result["credential_fingerprint"],
        expires_at=result["expires_at"],
        status=result["status"],
    )
