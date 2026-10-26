import os
from typing import List, Union
from pydantic import AnyHttpUrl, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    ENVIRONMENT: str = "development"
    PROJECT_NAME: str = "Blockchain Credential Lifecycle Verification API"
    API_V1_STR: str = "/api/v1"

    # Security & CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]

    # Database
    DATABASE_URL: str = "postgresql+psycopg://postgres:postgres@127.0.0.1:5433/credential_verification"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30

    # Authentication & Authorization (Phase 6)
    AUTH_MODE: str = "oidc"  # "oidc" | "local_dev" | "disabled"
    OIDC_ISSUER_URL: str = "https://auth.institutional-consortium.org/realms/credentials"
    OIDC_AUDIENCE: str = "blockchain-credential-api"
    OIDC_JWKS_URL: Union[str, None] = None
    OIDC_ALLOWED_ALGORITHMS: List[str] = ["RS256", "ES256"]
    OIDC_CLOCK_SKEW_SECONDS: int = 60
    AUTH_DEV_PUBLIC_KEY: Union[str, None] = None
    AUTH_DEV_PRIVATE_KEY: Union[str, None] = None

    # Blockchain
    BLOCKCHAIN_RPC_URL: str = "http://127.0.0.1:8545"
    BLOCKCHAIN_CHAIN_ID: int = 11155111  # Sepolia testnet default
    CHAIN_ID: Union[int, None] = None  # Backward-compatible alias
    ISSUER_REGISTRY_ADDRESS: str = ""
    CREDENTIAL_REGISTRY_ADDRESS: str = ""
    BLOCKCHAIN_SIGNER_PRIVATE_KEY: Union[str, None] = None
    BLOCKCHAIN_TIMEOUT_SECONDS: float = 10.0
    CONFIRMATION_BLOCKS: int = 1

    # Storage & Encryption (Phase 3)
    STORAGE_ROOT_DIR: str = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "storage")
    STORAGE_ENCRYPTION_KEY: str = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    MAX_UPLOAD_SIZE_BYTES: int = 10 * 1024 * 1024  # 10 MB
    CHALLENGE_EXPIRY_SECONDS: int = 300  # 5 minutes

    @field_validator("BLOCKCHAIN_SIGNER_PRIVATE_KEY")
    @classmethod
    def validate_signer_private_key(cls, v: Union[str, None]) -> Union[str, None]:
        if not v or not v.strip():
            return None
        clean = v.strip().lower()
        if clean.startswith("0x"):
            clean = clean[2:]
        if len(clean) != 64:
            raise ValueError(f"BLOCKCHAIN_SIGNER_PRIVATE_KEY must be exactly 32 bytes (64 hex characters), got {len(clean)}")
        try:
            bytes.fromhex(clean)
        except ValueError as err:
            raise ValueError("BLOCKCHAIN_SIGNER_PRIVATE_KEY must be a valid hex string") from err
        return "0x" + clean

    @field_validator("STORAGE_ENCRYPTION_KEY")
    @classmethod
    def validate_encryption_key(cls, v: str) -> str:
        clean = v.strip().lower()
        if clean.startswith("0x"):
            clean = clean[2:]
        if len(clean) != 64:
            raise ValueError(f"STORAGE_ENCRYPTION_KEY must be exactly 32 bytes (64 hex characters), got {len(clean)}")
        try:
            bytes.fromhex(clean)
        except ValueError as err:
            raise ValueError("STORAGE_ENCRYPTION_KEY must be a valid hex string") from err
        return clean

    @model_validator(mode="after")
    def validate_production_configuration(self) -> "Settings":
        # Harmonize CHAIN_ID and BLOCKCHAIN_CHAIN_ID
        if self.CHAIN_ID is not None:
            self.BLOCKCHAIN_CHAIN_ID = self.CHAIN_ID
        else:
            self.CHAIN_ID = self.BLOCKCHAIN_CHAIN_ID

        if self.is_production:
            if self.AUTH_MODE.lower() not in {"oidc", "mtls"}:
                raise ValueError("In production mode, AUTH_MODE must be 'oidc' or 'mtls'")
            if self.AUTH_MODE.lower() == "oidc":
                if not self.OIDC_ISSUER_URL or "localhost" in self.OIDC_ISSUER_URL or "127.0.0.1" in self.OIDC_ISSUER_URL:
                    raise ValueError("Production requires a valid external HTTPS institutional OIDC_ISSUER_URL")
                if not self.OIDC_AUDIENCE:
                    raise ValueError("Production requires OIDC_AUDIENCE to be configured")
            if not self.BLOCKCHAIN_RPC_URL:
                raise ValueError("Production requires BLOCKCHAIN_RPC_URL to be configured")
        return self

    # Documentation toggle
    DOCS_ENABLED: bool = True

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"

    @property
    def openapi_url(self) -> Union[str, None]:
        if self.is_production and not self.DOCS_ENABLED:
            return None
        return f"{self.API_V1_STR}/openapi.json"

    @property
    def docs_url(self) -> Union[str, None]:
        if self.is_production and not self.DOCS_ENABLED:
            return None
        return f"{self.API_V1_STR}/docs"

    @property
    def redoc_url(self) -> Union[str, None]:
        if self.is_production and not self.DOCS_ENABLED:
            return None
        return f"{self.API_V1_STR}/redoc"


settings = Settings()
