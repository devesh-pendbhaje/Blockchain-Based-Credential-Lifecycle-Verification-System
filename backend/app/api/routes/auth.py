from fastapi import APIRouter, Depends, status
from app.core.config import settings
from app.core.exceptions import AppException
from app.core.auth.models import AuthenticatedPrincipal
from app.core.auth.dependencies import get_current_principal
from app.core.auth.dev_keys import sign_dev_jwt
from app.schemas.auth import (
    DevTokenRequest,
    TokenResponse,
    AuthConfigResponse,
    UserProfileResponse,
)

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.get("/config", response_model=AuthConfigResponse, summary="Get Authentication Configuration")
def get_auth_config():
    """
    Returns public authentication configuration and mode.
    Does not expose private keys, secrets, or internal certificates.
    """
    return AuthConfigResponse(
        auth_mode=settings.AUTH_MODE,
        environment=settings.ENVIRONMENT,
        dev_mode_available=not settings.is_production,
        issuer_url=settings.OIDC_ISSUER_URL,
        audience=settings.OIDC_AUDIENCE,
        allowed_algorithms=settings.OIDC_ALLOWED_ALGORITHMS,
    )


@router.post("/dev-token", response_model=TokenResponse, summary="Generate Local Dev JWT")
def generate_dev_token(req: DevTokenRequest):
    """
    Issues a cryptographically signed RS256 JWT for local evaluation and regression testing.
    Strictly forbidden in production environments (returns HTTP 403).
    """
    if settings.is_production:
        raise AppException(
            message="Development token issuance is strictly prohibited in production mode.",
            error_code="DEV_AUTH_FORBIDDEN",
            status_code=403,
        )

    # Resolve persona defaults
    if req.persona == "admin":
        sub = req.sub or "admin-sec-ops"
        roles = ["admin", "issuer", "verifier"]
        issuer_id = req.issuer_id
        verifier_id = req.verifier_id or "admin-session-ops"
        email = req.email or "admin@institution.example.edu"
    elif req.persona == "issuer":
        sub = req.sub or "issuer-registrar-authority"
        roles = ["issuer"]
        issuer_id = req.issuer_id or "0x0000000000000000000000000000000000000000000000000000000000000001"
        verifier_id = None
        email = req.email or "issuer@institution.example.edu"
    elif req.persona == "verifier":
        sub = req.sub or "verifier-session-principal-99"
        roles = ["verifier"]
        issuer_id = None
        verifier_id = req.verifier_id or "verifier-portal-auditor"
        email = req.email or "verifier@auditor.example.org"
    else:  # custom
        sub = req.sub or "custom-user-01"
        roles = req.roles or ["user"]
        issuer_id = req.issuer_id
        verifier_id = req.verifier_id
        email = req.email

    token = sign_dev_jwt(
        sub=sub,
        roles=roles,
        issuer_id=issuer_id,
        verifier_id=verifier_id,
        exp_seconds=req.exp_seconds,
        email=email,
    )

    return TokenResponse(
        access_token=token,
        token_type="Bearer",
        expires_in=req.exp_seconds,
        roles=roles,
        sub=sub,
        issuer_id=issuer_id,
        verifier_id=verifier_id,
    )


@router.get("/me", response_model=UserProfileResponse, summary="Get Current Authenticated Principal")
def get_current_user_profile(
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
):
    """
    Returns the validated identity and roles of the caller extracted from their Bearer token.
    Requires a valid Bearer token.
    """
    return UserProfileResponse(
        subject=principal.subject,
        roles=principal.roles,
        issuer_id=principal.issuer_id,
        verifier_id=principal.verifier_id,
        email=principal.email,
        is_admin=principal.is_admin(),
    )
