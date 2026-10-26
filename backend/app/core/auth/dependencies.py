from typing import Callable, Optional
from fastapi import Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.exceptions import AppException
from app.core.auth.models import AuthenticatedPrincipal
from app.core.auth.oidc import oidc_validator

# HTTP Bearer scheme with custom auto_error=False to provide clean RFC-compliant error envelopes
bearer_scheme = HTTPBearer(auto_error=False)


def get_current_principal(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> AuthenticatedPrincipal:
    """
    FastAPI dependency extracting Bearer token and verifying it against identity provider.
    Returns AuthenticatedPrincipal on success; raises HTTP 401 on missing or invalid token.
    """
    if credentials is None:
        raise AppException(
            message="Authorization required. Provide 'Authorization: Bearer <token>' header.",
            error_code="UNAUTHORIZED",
            status_code=401,
        )

    return oidc_validator.validate_token(credentials.credentials)


def require_role(role_name: str) -> Callable[[AuthenticatedPrincipal], AuthenticatedPrincipal]:
    """
    Factory creating a FastAPI dependency requiring a specific validated authorization role.
    Admin principal inherently satisfies all role requirements.
    """
    def _role_checker(
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
    ) -> AuthenticatedPrincipal:
        if not principal.has_role(role_name):
            raise AppException(
                message=f"Access forbidden. This operation requires the '{role_name}' role.",
                error_code="INSUFFICIENT_PERMISSIONS",
                status_code=403,
            )
        return principal

    return _role_checker


# Common role dependencies
require_admin = require_role("admin")
require_issuer = require_role("issuer")
require_verifier = require_role("verifier")


def verify_issuer_tenant_ownership(
    principal: AuthenticatedPrincipal,
    target_issuer_id: str,
) -> None:
    """
    Enforces institutional tenant isolation (cross-tenant IDOR protection).
    Ensures that an authenticated issuer principal can only issue, modify,
    or supersede credentials for their own accredited institutional issuer ID.
    Admin principal can manage all institutions.
    """
    if principal.is_admin():
        return

    clean_target = target_issuer_id.strip().lower()
    if not principal.issuer_id:
        raise AppException(
            message="Forbidden: Authenticated token is not bound to any institutional issuer authority.",
            error_code="UNBOUND_ISSUER_IDENTITY",
            status_code=403,
        )

    if principal.issuer_id.lower() != clean_target:
        raise AppException(
            message="Forbidden: Authenticated principal is not authorized to act on behalf of the specified issuer.",
            error_code="TENANT_MISMATCH",
            status_code=403,
        )
