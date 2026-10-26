from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class ChallengeCreateRequest(BaseModel):
    verifier_session_id: str = Field(..., description="Unique verifier session identifier", min_length=1, max_length=128)
    credential_fingerprint: Optional[str] = Field(None, description="Optional scoped credential fingerprint (0x + 64 hex)")
    expiry_seconds: Optional[int] = Field(None, description="Expiration window in seconds (default 300)", ge=10, le=3600)


class ChallengeCreateResponse(BaseModel):
    challenge_id: str = Field(..., description="UUID challenge identifier")
    challenge_nonce: str = Field(..., description="Unpredictable 256-bit random nonce (0x + 64 hex)")
    verifier_session_id: str = Field(..., description="Bound verifier session identifier")
    verifier_principal: str = Field("", description="Authenticated verifier principal bound to challenge")
    credential_fingerprint: Optional[str] = Field(None, description="Bound credential fingerprint if scoped")
    expires_at: datetime = Field(..., description="Challenge expiration timestamp")
    status: str = Field(..., description="Challenge status (ISSUED)")
