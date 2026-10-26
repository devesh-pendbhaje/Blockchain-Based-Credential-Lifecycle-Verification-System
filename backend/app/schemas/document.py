from typing import Optional, Any
from pydantic import BaseModel, Field
from app.schemas.common import validate_bytes32_hex


class DocumentUploadResponse(BaseModel):
    storage_id: str = Field(..., description="UUID storage object identifier")
    document_digest: str = Field(..., description="SHA-256 digest of original certificate bytes in 0x hex format")
    content_type: str = Field(..., description="Detected MIME content type")
    byte_size: int = Field(..., description="Size of certificate in bytes")
    storage_adapter: str = Field(default="filesystem_encrypted", description="Storage adapter mechanism")
    created_at: str = Field(..., description="ISO 8601 creation timestamp")


class CanonicalMetadataRequest(BaseModel):
    metadata: Any = Field(..., description="Raw JSON metadata object or string")


class CanonicalMetadataResponse(BaseModel):
    metadata_digest: str = Field(..., description="Keccak-256 digest of RFC 8785 canonical UTF-8 bytes")
    canonical_bytes_length: int = Field(..., description="Length of canonicalized UTF-8 bytes")
    canonical_json: str = Field(..., description="RFC 8785 canonicalized JSON string")


class StorageMetadataResponse(BaseModel):
    storage_id: str
    document_digest: str
    content_type: str
    byte_size: int
    envelope_version: int
    created_at: Optional[str] = None
