from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator
from app.schemas.common import validate_bytes32_hex


class IssuerCreateRequest(BaseModel):
    issuer_id: str = Field(..., description="0x-prefixed 32-byte hex issuer identifier (non-zero)")
    display_name: str = Field(..., min_length=1, max_length=255, description="Institution display name")
    metadata_uri: Optional[str] = Field(None, max_length=1024, description="Public IPFS or HTTPS metadata pointer")
    status: str = Field("ACTIVE", description="Initial database lifecycle status (ACTIVE, SUSPENDED, REVOKED)")

    @field_validator("issuer_id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        return validate_bytes32_hex(v, allow_zero=False)

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        v_upper = v.upper()
        if v_upper not in {"ACTIVE", "SUSPENDED", "REVOKED"}:
            raise ValueError("Status must be one of: ACTIVE, SUSPENDED, REVOKED")
        return v_upper


class IssuerResponse(BaseModel):
    issuer_id: str
    display_name: str
    metadata_uri: Optional[str]
    status: str
    created_at: datetime
    updated_at: datetime
    on_chain_registered: Optional[bool] = None
    on_chain_note: str = "Database record only. On-chain registration is executed separately via governance."


class IssuerStatusResponse(BaseModel):
    issuer_id: str
    db_status: str
    on_chain_status: Optional[str] = None
    is_on_chain_active: Optional[bool] = None
    checked_at: datetime


class IssuerOnChainRegisterRequest(BaseModel):
    signing_address: str = Field(..., description="EVM signing address authorized to issue credentials for this institution")
    metadata_uri: Optional[str] = Field(None, max_length=1024, description="Optional metadata URI override")

    @field_validator("signing_address")
    @classmethod
    def validate_signing_addr(cls, v: str) -> str:
        clean = v.strip()
        if not clean.startswith("0x") or len(clean) != 42:
            raise ValueError("signing_address must be a valid 20-byte 0x-prefixed Ethereum address")
        return clean


class IssuerOnChainRegisterResponse(BaseModel):
    success: bool
    status: str
    issuer_id: str
    tx_hash: Optional[str] = None
    block_number: Optional[int] = None
    already_registered: Optional[bool] = None
    error: Optional[str] = None
