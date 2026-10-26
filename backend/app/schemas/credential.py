from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator
from app.schemas.common import validate_bytes32_hex


class CredentialCreateRequest(BaseModel):
    credential_id: str = Field(..., description="0x-prefixed 32-byte hex business credential identifier (non-zero)")
    issuer_id: str = Field(..., description="0x-prefixed 32-byte hex issuer identifier (non-zero)")
    document_digest: str = Field(..., description="0x-prefixed 32-byte hex digest of visual certificate")
    metadata_digest: str = Field(..., description="0x-prefixed 32-byte hex digest of canonical JSON metadata")
    merkle_root: str = Field(..., description="0x-prefixed 32-byte hex root of salted attribute Merkle tree")
    version: int = Field(1, ge=1, le=4294967295, description="uint32 version number (defaults to 1)")
    expires_at: Optional[int] = Field(0, ge=0, description="uint64 Unix expiration timestamp (0 = never expires)")
    idempotency_key: Optional[str] = Field(None, max_length=128, description="Optional client idempotency correlation key")

    @field_validator("credential_id", "issuer_id", "document_digest", "metadata_digest", "merkle_root")
    @classmethod
    def validate_hashes(cls, v: str) -> str:
        return validate_bytes32_hex(v, allow_zero=False)


class CredentialResponse(BaseModel):
    credential_id: str
    issuer_id: str
    current_version: int
    current_fingerprint: str
    current_status: str
    issuance_status: str
    issuance_tx_hash: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class CredentialVersionResponse(BaseModel):
    credential_id: str
    version: int
    fingerprint: str
    document_digest: str
    metadata_digest: str
    merkle_root: str
    expires_at: Optional[int] = 0
    issuance_status: str
    issuance_tx_hash: Optional[str] = None
    block_number: Optional[int] = None
    chain_id: Optional[int] = None
    superseded_by_fingerprint: Optional[str] = None
    created_at: datetime


class VerificationResponse(BaseModel):
    fingerprint: str
    database_found: bool
    blockchain_available: bool
    is_valid: bool
    lifecycle_status: Optional[str] = None
    is_expired: Optional[bool] = None
    digest_match: Optional[bool] = None
    blockchain_code: Optional[str] = None
    details: str
    checked_at: datetime
