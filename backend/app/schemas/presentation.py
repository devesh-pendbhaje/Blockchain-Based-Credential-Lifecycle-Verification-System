from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class DisclosedClaim(BaseModel):
    key: str = Field(..., description="Attribute name")
    value: str = Field(..., description="Attribute claim value")
    salt: str = Field(..., description="256-bit blinding salt (0x + 64 hex)")
    leaf_hash: str = Field(..., description="Computed leaf hash")
    proof: List[str] = Field(..., description="Merkle sibling proof path")


class PresentationGenerateRequest(BaseModel):
    credential_id: str = Field(..., description="Business credential identifier (0x + 64 hex)")
    version: int = Field(..., description="Monotonically increasing version counter", ge=1)
    attributes: Dict[str, str] = Field(..., description="Full credential attributes")
    salts: Dict[str, str] = Field(..., description="Salts for each attribute")
    disclosed_keys: List[str] = Field(..., description="Subset of attribute keys to disclose", min_length=1)
    document_digest: str = Field(..., description="SHA-256 document digest")
    metadata_digest: str = Field(..., description="Keccak-256 metadata digest")
    issuer_id: str = Field(..., description="Issuer identifier (0x + 64 hex)")
    challenge_id: Optional[str] = Field(None, description="Optional verifier challenge ID")
    challenge_nonce: Optional[str] = Field(None, description="Optional verifier challenge nonce")


class PresentationResponse(BaseModel):
    credential_fingerprint: str
    credential_id: str
    version: int
    issuer_id: str
    merkle_root: str
    document_digest: str
    metadata_digest: str
    disclosed_claims: List[DisclosedClaim]
    challenge_id: Optional[str] = None
    challenge_nonce: Optional[str] = None


class PresentationVerifyRequest(BaseModel):
    presentation: Dict[str, Any] = Field(..., description="Selective disclosure presentation payload")
    verifier_session_id: str = Field(..., description="Verifier session identifier")
    require_current_version: bool = Field(False, description="Whether to reject superseded historical versions")


class PresentationVerifyResponse(BaseModel):
    overall_valid: bool = Field(..., description="Whether the entire presentation and credential verification succeeded")
    selective_disclosure_valid: bool = Field(..., description="Whether all revealed Merkle proofs are cryptographically valid")
    disclosed_attributes: Dict[str, Any] = Field(..., description="Map of verified disclosed attributes")
    challenge_verified: bool = Field(..., description="Whether the verifier challenge was authenticated and consumed")
    fingerprint_verified: bool = Field(..., description="Whether the 6-component composite fingerprint was verified")
    database_status: str = Field(..., description="Database lifecycle status of credential")
    is_current_version: bool = Field(..., description="Whether the credential matches the latest known version")
    blockchain_verification: Dict[str, Any] = Field(..., description="On-chain verification outcome and connection status")
    privacy_notice: str = Field(..., description="Notice regarding attribute disclosure and verifier linkability")
