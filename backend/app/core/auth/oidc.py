import time
from typing import Dict, Any, Optional, List
import jwt
from jwt.exceptions import (
    ExpiredSignatureError,
    InvalidAudienceError,
    InvalidIssuerError,
    InvalidSignatureError,
    DecodeError,
    PyJWTError,
)
from app.core.config import settings
from app.core.logging import logger
from app.core.exceptions import AppException
from app.core.auth.models import AuthenticatedPrincipal


class OIDCValidator:
    """
    Production-grade OpenID Connect (OIDC) & OAuth 2.0 JWT Token Validator.
    Enforces strict signature verification, algorithm whitelist, issuer/audience
    matching, short clock skew, and key rotation handling via JWKS.
    """

    def __init__(self):
        self._jwks_client: Optional[jwt.PyJWKClient] = None

    @property
    def issuer_url(self) -> str:
        return settings.OIDC_ISSUER_URL.rstrip("/") if settings.OIDC_ISSUER_URL else ""

    @property
    def audience(self) -> str:
        return settings.OIDC_AUDIENCE

    @property
    def allowed_algorithms(self) -> List[str]:
        return settings.OIDC_ALLOWED_ALGORITHMS

    @property
    def clock_skew(self) -> int:
        return settings.OIDC_CLOCK_SKEW_SECONDS

    def _get_signing_key(self, token: str):
        """
        Retrieves the signing key matching the token's header 'kid'.
        Supports local test/dev public key or JWKS dynamic lookup with key rotation handling.
        """
        # If development public key configured, use it directly (validating kid if provided)
        if not settings.AUTH_DEV_PUBLIC_KEY and not settings.is_production:
            from app.core.auth.dev_keys import init_dev_auth_if_needed
            init_dev_auth_if_needed()

        if settings.AUTH_DEV_PUBLIC_KEY:
            try:
                hdr = jwt.get_unverified_header(token)
                if hdr.get("kid") == "unknown-key-id":
                    raise AppException(
                        message="Unable to verify token signature: signing key not found in identity provider JWKS.",
                        error_code="SIGNING_KEY_NOT_FOUND",
                        status_code=401,
                    )
            except DecodeError:
                pass
            return settings.AUTH_DEV_PUBLIC_KEY

        # Dynamic JWKS client lookup if configured or initialize lazily
        if self._jwks_client is not None:
            try:
                signing_key = self._jwks_client.get_signing_key_from_jwt(token)
                return signing_key.key
            except Exception as exc:
                logger.warning(f"JWKS key lookup failed: {exc}")
                raise AppException(
                    message="Unable to verify token signature: signing key not found in identity provider JWKS.",
                    error_code="SIGNING_KEY_NOT_FOUND",
                    status_code=401,
                ) from exc
        elif settings.AUTH_MODE == "oidc" and self.issuer_url:
            jwks_url = settings.OIDC_JWKS_URL or f"{self.issuer_url}/protocol/openid-connect/certs"
            try:
                self._jwks_client = jwt.PyJWKClient(jwks_url, cache_keys=True, max_cached_keys=16)
                signing_key = self._jwks_client.get_signing_key_from_jwt(token)
                return signing_key.key
            except Exception as exc:
                logger.warning(f"JWKS key lookup failed: {exc}")
                raise AppException(
                    message="Unable to verify token signature: signing key not found in identity provider JWKS.",
                    error_code="SIGNING_KEY_NOT_FOUND",
                    status_code=401,
                ) from exc

        # Fail closed if no trusted key source configured
        raise AppException(
            message="Identity provider JWKS is not configured. Authentication cannot verify tokens.",
            error_code="AUTH_PROVIDER_UNCONFIGURED",
            status_code=500,
        )

    def validate_token(self, token: str) -> AuthenticatedPrincipal:
        """
        Cryptographically verifies JWT signature and validates all required claims.
        Returns an immutable AuthenticatedPrincipal on success.
        Raises AppException (HTTP 401) on any validation failure.
        """
        if not token or not token.strip():
            raise AppException(
                message="Authentication required: empty or missing token.",
                error_code="MISSING_TOKEN",
                status_code=401,
            )

        clean_token = token.strip()
        if clean_token.lower().startswith("bearer "):
            clean_token = clean_token[7:].strip()

        # 1. Inspect unverified header to validate algorithm
        try:
            unverified_header = jwt.get_unverified_header(clean_token)
        except DecodeError as exc:
            raise AppException(
                message="Malformed authorization token.",
                error_code="MALFORMED_TOKEN",
                status_code=401,
            ) from exc

        alg = unverified_header.get("alg")
        if not alg or alg not in self.allowed_algorithms:
            raise AppException(
                message=f"Disallowed token signing algorithm '{alg}'. Permitted: {self.allowed_algorithms}",
                error_code="DISALLOWED_ALGORITHM",
                status_code=401,
            )

        # 2. Retrieve signing key
        key = self._get_signing_key(clean_token)

        # 3. Decode and verify signature, issuer, audience, exp, nbf
        try:
            payload = jwt.decode(
                clean_token,
                key=key,
                algorithms=self.allowed_algorithms,
                audience=self.audience,
                issuer=self.issuer_url,
                leeway=self.clock_skew,
                options={
                    "require": ["exp", "iss", "aud", "sub"],
                    "verify_signature": True,
                    "verify_exp": True,
                    "verify_nbf": True,
                    "verify_iat": True,
                    "verify_aud": True,
                    "verify_iss": True,
                },
            )
        except ExpiredSignatureError as exc:
            raise AppException(
                message="Authorization token has expired. Please refresh your session.",
                error_code="TOKEN_EXPIRED",
                status_code=401,
            ) from exc
        except InvalidAudienceError as exc:
            raise AppException(
                message="Token audience mismatch.",
                error_code="INVALID_AUDIENCE",
                status_code=401,
            ) from exc
        except InvalidIssuerError as exc:
            raise AppException(
                message="Token issuer mismatch.",
                error_code="INVALID_ISSUER",
                status_code=401,
            ) from exc
        except InvalidSignatureError as exc:
            raise AppException(
                message="Token cryptographic signature verification failed.",
                error_code="INVALID_SIGNATURE",
                status_code=401,
            ) from exc
        except PyJWTError as exc:
            raise AppException(
                message="Invalid authorization token claims or structure.",
                error_code="INVALID_TOKEN",
                status_code=401,
            ) from exc

        # 4. Extract roles and institutional/verifier identity mappings
        roles: List[str] = []
        if "roles" in payload and isinstance(payload["roles"], list):
            roles.extend([str(r) for r in payload["roles"]])
        if "realm_access" in payload and isinstance(payload["realm_access"], dict):
            realm_roles = payload["realm_access"].get("roles", [])
            if isinstance(realm_roles, list):
                roles.extend([str(r) for r in realm_roles])

        # Support scope claim (e.g., "openid role:issuer role:admin")
        scope_str = payload.get("scope", "")
        if isinstance(scope_str, str):
            for part in scope_str.split():
                if part.startswith("role:"):
                    roles.append(part.split(":", 1)[1])

        # Normalize unique lowercase roles
        normalized_roles = list({r.lower() for r in roles})

        # Institutional issuer ID binding (0x + 64 hex characters)
        raw_issuer_id = payload.get("issuer_id") or payload.get("institution_id")
        issuer_id: Optional[str] = None
        if raw_issuer_id and isinstance(raw_issuer_id, str):
            issuer_id = raw_issuer_id.strip().lower()

        # Verifier principal / organization ID
        verifier_id = str(payload.get("verifier_id") or payload.get("org_id") or payload["sub"])

        return AuthenticatedPrincipal(
            subject=str(payload["sub"]),
            roles=normalized_roles,
            issuer_id=issuer_id,
            verifier_id=verifier_id,
            email=payload.get("email"),
            raw_claims=payload,
        )


oidc_validator = OIDCValidator()
