from typing import Dict, List, Optional
from pydantic import BaseModel, Field, field_validator
from app.schemas.common import validate_bytes32_hex


class MerkleBuildTreeRequest(BaseModel):
    attributes: Dict[str, str] = Field(..., description="Key-value mapping of credential attribute claims")
    salts: Optional[Dict[str, str]] = Field(None, description="Optional pre-generated 256-bit blinding salts")


class MerkleBuildTreeResponse(BaseModel):
    merkle_root: str = Field(..., description="Root hash of domain-separated salted attribute Merkle tree")
    ordered_keys: List[str] = Field(..., description="Deterministically sorted attribute keys")
    leaves: Dict[str, str] = Field(..., description="Leaf hashes mapped by attribute key")
    salts: Dict[str, str] = Field(..., description="256-bit blinding salts mapped by attribute key")
    proofs: Dict[str, List[str]] = Field(..., description="Merkle sibling proofs mapped by attribute key")


class MerkleVerifyProofRequest(BaseModel):
    root: str = Field(..., description="Expected Merkle root (bytes32 hex)")
    leaf: str = Field(..., description="Target leaf hash (bytes32 hex)")
    proof: List[str] = Field(..., description="Sibling proof hashes ascending to root")

    @field_validator("root", "leaf")
    @classmethod
    def validate_hashes(cls, v: str) -> str:
        return validate_bytes32_hex(v, allow_zero=False)


class MerkleVerifyProofResponse(BaseModel):
    is_valid: bool = Field(..., description="Whether the proof verifies against the root")
