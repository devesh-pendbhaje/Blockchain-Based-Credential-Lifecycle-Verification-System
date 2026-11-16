from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, field_validator, model_validator
from app.schemas.common import validate_bytes32_hex


class DisclosedClaim(BaseModel):
    key: str = Field(..., min_length=1, max_length=128, description="Attribute name")
    value: str = Field(..., max_length=2048, description="Attribute claim value")
    salt: str = Field(..., min_length=64, max_length=66, description="256-bit blinding salt (0x + 64 hex)")
    leaf_hash: Optional[str] = Field(None, max_length=66, description="Computed leaf hash")
    proof: List[str] = Field(default_factory=list, max_length=64, description="Merkle sibling proof path")

    @field_validator("salt", "leaf_hash")
    @classmethod
    def hashes(cls, v):
        return validate_bytes32_hex(v) if v is not None else None

    @field_validator("proof")
    @classmethod
    def siblings(cls, values):
        return [validate_bytes32_hex(v) for v in values]


class PresentationPayload(BaseModel):
    credential_fingerprint: str = Field(..., min_length=64, max_length=66, description="Composite fingerprint")
    credential_id: Optional[str] = Field(None, max_length=66, description="Credential ID")
    version: Optional[int] = Field(None, ge=1, le=4294967295, description="Version number")
    issuer_id: Optional[str] = Field(None, max_length=66, description="Issuer ID")
    merkle_root: str = Field(..., min_length=64, max_length=66, description="Salted Merkle root")
    document_digest: Optional[str] = Field(None, max_length=66, description="Document digest")
    metadata_digest: Optional[str] = Field(None, max_length=66, description="Metadata digest")
    disclosed_claims: List[DisclosedClaim] = Field(..., min_length=1, max_length=100, description="List of revealed claims with Merkle proofs")
    challenge_id: Optional[str] = Field(None, max_length=128, description="Verifier challenge ID")
    challenge_nonce: Optional[str] = Field(None, max_length=66, description="Verifier challenge nonce")

    @field_validator("credential_fingerprint", "credential_id", "issuer_id", "merkle_root", "document_digest", "metadata_digest", "challenge_nonce")
    @classmethod
    def hashes(cls, v):
        return validate_bytes32_hex(v) if v is not None else None

    @model_validator(mode="after")
    def complete_challenge(self):
        if bool(self.challenge_id) != bool(self.challenge_nonce):
            raise ValueError("Challenge ID and nonce must be provided together")
        if len({c.key for c in self.disclosed_claims}) != len(self.disclosed_claims):
            raise ValueError("Duplicate disclosed claim keys")
        return self


class PresentationGenerateRequest(BaseModel):
    credential_id: str = Field(..., description="Business credential identifier (0x + 64 hex)")
    version: int = Field(..., description="Monotonically increasing version counter", ge=1, le=4294967295)
    attributes: Dict[str, str] = Field(..., description="Full credential attributes", min_length=1, max_length=100)
    salts: Dict[str, str] = Field(..., description="Salts for each attribute", min_length=1, max_length=100)
    disclosed_keys: List[str] = Field(..., description="Subset of attribute keys to disclose", min_length=1)
    document_digest: str = Field(..., description="SHA-256 document digest")
    metadata_digest: str = Field(..., description="Keccak-256 metadata digest")
    issuer_id: str = Field(..., description="Issuer identifier (0x + 64 hex)")
    challenge_id: Optional[str] = Field(None, description="Optional verifier challenge ID")
    challenge_nonce: Optional[str] = Field(None, description="Optional verifier challenge nonce")

    @field_validator("credential_id", "issuer_id", "document_digest", "metadata_digest", "challenge_nonce")
    @classmethod
    def hashes(cls, v):
        return validate_bytes32_hex(v) if v is not None else None

    @model_validator(mode="after")
    def validate_attributes(self):
        if set(self.attributes) != set(self.salts):
            raise ValueError("Original salts are required for every attribute")
        for key, value in self.attributes.items():
            if not key or len(key) > 128 or len(value) > 2048:
                raise ValueError("Invalid attribute length")
            self.salts[key] = validate_bytes32_hex(self.salts[key])
        if len(self.disclosed_keys) != len(set(self.disclosed_keys)) or not set(self.disclosed_keys) <= set(self.attributes):
            raise ValueError("Disclosed keys must be unique existing attributes")
        return self


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
    presentation: PresentationPayload = Field(..., description="Typed and bounded selective disclosure presentation payload")
    verifier_session_id: str = Field(..., min_length=1, max_length=128, description="Verifier session identifier")
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
