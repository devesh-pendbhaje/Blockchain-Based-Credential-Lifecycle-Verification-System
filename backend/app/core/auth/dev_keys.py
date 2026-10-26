import os
import threading
import time
from typing import List, Optional, Tuple, Dict, Any
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

from app.core.config import settings
from app.core.logging import logger
from app.core.exceptions import AppException

_key_lock = threading.Lock()
_cached_private_pem: Optional[str] = None
_cached_public_pem: Optional[str] = None


def get_or_create_dev_keypair() -> Tuple[str, str]:
    """
    Retrieves or generates an RSA-2048 keypair strictly for local development and testing.
    In production environments, this method fails closed.
    Ensures that settings.AUTH_DEV_PUBLIC_KEY is initialized for OIDCValidator.
    """
    global _cached_private_pem, _cached_public_pem

    # If explicit settings keys provided, synchronize and return immediately
    if settings.AUTH_DEV_PRIVATE_KEY and settings.AUTH_DEV_PUBLIC_KEY:
        if _cached_private_pem == settings.AUTH_DEV_PRIVATE_KEY and _cached_public_pem == settings.AUTH_DEV_PUBLIC_KEY:
            return _cached_private_pem, _cached_public_pem
        with _key_lock:
            _cached_private_pem = settings.AUTH_DEV_PRIVATE_KEY
            _cached_public_pem = settings.AUTH_DEV_PUBLIC_KEY
            return _cached_private_pem, _cached_public_pem

    if _cached_private_pem and _cached_public_pem:
        return _cached_private_pem, _cached_public_pem

    with _key_lock:
        if _cached_private_pem and _cached_public_pem:
            return _cached_private_pem, _cached_public_pem

        if settings.is_production:
            raise AppException(
                message="Local development cryptographic keys are strictly prohibited in production mode.",
                error_code="DEV_KEYS_PROHIBITED",
                status_code=500,
            )

        # 1. If explicit environment keys provided, prioritize them
        if settings.AUTH_DEV_PRIVATE_KEY and settings.AUTH_DEV_PUBLIC_KEY:
            _cached_private_pem = settings.AUTH_DEV_PRIVATE_KEY
            _cached_public_pem = settings.AUTH_DEV_PUBLIC_KEY
            return _cached_private_pem, _cached_public_pem

        if settings.AUTH_DEV_PRIVATE_KEY:
            try:
                priv_key = serialization.load_pem_private_key(
                    settings.AUTH_DEV_PRIVATE_KEY.encode("utf-8"),
                    password=None,
                )
                pub_bytes = priv_key.public_key().public_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PublicFormat.SubjectPublicKeyInfo,
                )
                _cached_private_pem = settings.AUTH_DEV_PRIVATE_KEY
                _cached_public_pem = pub_bytes.decode("utf-8")
                settings.AUTH_DEV_PUBLIC_KEY = _cached_public_pem
                return _cached_private_pem, _cached_public_pem
            except Exception as exc:
                logger.warning(f"Failed to parse AUTH_DEV_PRIVATE_KEY: {exc}")

        # 2. Check for persistent dev key file on local disk
        os.makedirs(settings.STORAGE_ROOT_DIR, exist_ok=True)
        key_path = os.path.join(settings.STORAGE_ROOT_DIR, ".dev_jwt_rsa.pem")

        if os.path.exists(key_path):
            try:
                with open(key_path, "r", encoding="utf-8") as f:
                    file_priv_pem = f.read().strip()
                priv_key = serialization.load_pem_private_key(
                    file_priv_pem.encode("utf-8"),
                    password=None,
                )
                pub_bytes = priv_key.public_key().public_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PublicFormat.SubjectPublicKeyInfo,
                )
                _cached_private_pem = file_priv_pem
                _cached_public_pem = pub_bytes.decode("utf-8")
                settings.AUTH_DEV_PUBLIC_KEY = _cached_public_pem
                logger.info("Loaded persistent RSA dev keypair for local authentication.")
                return _cached_private_pem, _cached_public_pem
            except Exception as exc:
                logger.warning(f"Failed to read existing dev key file: {exc}. Generating a new one.")

        # 3. Generate a fresh 2048-bit RSA keypair for local evaluation
        logger.info("Generating new 2048-bit RSA keypair for local dev authentication...")
        new_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        new_priv_pem = new_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode("utf-8")
        new_pub_pem = new_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("utf-8")

        try:
            with open(key_path, "w", encoding="utf-8") as f:
                f.write(new_priv_pem)
            try:
                os.chmod(key_path, 0o600)
            except OSError:
                pass
        except Exception as exc:
            logger.warning(f"Could not persist dev key to disk ({exc}); holding in memory.")

        _cached_private_pem = new_priv_pem
        _cached_public_pem = new_pub_pem
        settings.AUTH_DEV_PUBLIC_KEY = new_pub_pem
        return _cached_private_pem, _cached_public_pem


def init_dev_auth_if_needed() -> None:
    """
    Initializes dev authentication settings if running in development mode.
    Does nothing in production.
    """
    if not settings.is_production and not settings.AUTH_DEV_PUBLIC_KEY:
        try:
            get_or_create_dev_keypair()
        except Exception as exc:
            logger.warning(f"Could not initialize local dev keypair: {exc}")


def sign_dev_jwt(
    sub: str,
    roles: List[str],
    issuer_id: Optional[str] = None,
    verifier_id: Optional[str] = None,
    exp_seconds: int = 7200,
    email: Optional[str] = None,
    extra_claims: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Signs a valid, cryptographically verifiable RS256 JWT using the local dev keypair.
    Strictly forbidden in production mode.
    """
    if settings.is_production:
        raise AppException(
            message="Development token issuance is strictly prohibited in production mode.",
            error_code="DEV_AUTH_FORBIDDEN",
            status_code=403,
        )

    priv_pem, _ = get_or_create_dev_keypair()
    now = int(time.time())

    issuer_url = settings.OIDC_ISSUER_URL.rstrip("/") if settings.OIDC_ISSUER_URL else "https://auth.institutional-consortium.org/realms/credentials"

    payload: Dict[str, Any] = {
        "iss": issuer_url,
        "aud": settings.OIDC_AUDIENCE,
        "sub": sub,
        "iat": now,
        "nbf": now - 5,
        "exp": now + exp_seconds,
        "roles": [r.lower() for r in roles],
    }

    if email:
        payload["email"] = email
    if issuer_id:
        payload["issuer_id"] = issuer_id.lower()
    if verifier_id:
        payload["verifier_id"] = verifier_id
    if extra_claims:
        payload.update(extra_claims)

    headers = {"kid": "local-dev-rsa-1", "alg": "RS256", "typ": "JWT"}
    return jwt.encode(payload, priv_pem, algorithm="RS256", headers=headers)
