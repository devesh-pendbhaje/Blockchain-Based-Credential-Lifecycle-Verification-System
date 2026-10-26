from typing import List, Optional, Literal
from pydantic import BaseModel, Field


class DevTokenRequest(BaseModel):
    persona: Literal["admin", "issuer", "verifier", "custom"] = Field(
        default="admin",
        description="Pre-configured persona or custom",
    )
    roles: Optional[List[str]] = Field(
        default=None,
        description="Explicit roles if persona is custom",
    )
    issuer_id: Optional[str] = Field(
        default=None,
        description="0x-prefixed 32-byte hex issuer ID for issuer persona",
    )
    verifier_id: Optional[str] = Field(
        default=None,
        description="Verifier ID or organization name for verifier persona",
    )
    sub: Optional[str] = Field(
        default=None,
        description="Subject identifier",
    )
    email: Optional[str] = Field(
        default=None,
        description="Institutional user email address",
    )
    exp_seconds: int = Field(
        default=7200,
        ge=60,
        le=86400,
        description="Token expiration duration in seconds (default: 2 hours)",
    )


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in: int
    roles: List[str]
    sub: str
    issuer_id: Optional[str] = None
    verifier_id: Optional[str] = None


class AuthConfigResponse(BaseModel):
    auth_mode: str
    environment: str
    dev_mode_available: bool
    issuer_url: str
    audience: str
    allowed_algorithms: List[str]


class UserProfileResponse(BaseModel):
    subject: str
    roles: List[str]
    issuer_id: Optional[str] = None
    verifier_id: Optional[str] = None
    email: Optional[str] = None
    is_admin: bool
