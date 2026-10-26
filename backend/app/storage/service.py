import uuid
import json
from datetime import datetime, timezone
from typing import Dict, Any, Tuple, Optional
from app.core.config import settings
from app.core.exceptions import AppException
from app.storage.encryption import EnvelopeEncryption
from app.storage.filesystem import EncryptedFilesystemStorage


class CertificateStorageService:
    """
    High-level certificate storage service decoupling encryption, storage adapters,
    and business logic. Manages key loading, AAD binding, and off-chain storage.
    """

    def __init__(
        self,
        encryption_key_hex: Optional[str] = None,
        storage_root_dir: Optional[str] = None,
    ):
        key_hex = encryption_key_hex or settings.STORAGE_ENCRYPTION_KEY
        key_bytes = bytes.fromhex(key_hex)
        self.encryptor = EnvelopeEncryption(key_bytes)

        root_dir = storage_root_dir or settings.STORAGE_ROOT_DIR
        self.adapter = EncryptedFilesystemStorage(root_dir)

    def _build_aad(self, storage_id: str, document_digest: str, content_type: str) -> bytes:
        return f"{storage_id}:{document_digest.lower()}:{content_type.lower()}".encode("utf-8")

    def store_certificate(
        self,
        raw_bytes: bytes,
        content_type: str,
        document_digest: str,
        credential_id: Optional[str] = None,
        version: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Encrypts certificate bytes with unique AES-GCM nonce and AAD binding,
        then persists to off-chain storage.
        """
        storage_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()
        aad = self._build_aad(storage_id, document_digest, content_type)

        # 1. Encrypt with AES-256-GCM
        envelope = self.encryptor.encrypt(raw_bytes, aad=aad)

        # 2. Build non-sensitive storage metadata
        metadata = {
            "storage_id": storage_id,
            "document_digest": document_digest.lower(),
            "content_type": content_type,
            "byte_size": len(raw_bytes),
            "credential_id": credential_id,
            "version": version,
            "storage_adapter": "filesystem_encrypted",
            "created_at": created_at,
        }

        # 3. Persist via storage adapter
        envelope_json = json.dumps(envelope).encode("utf-8")
        self.adapter.store(storage_id, envelope_json, metadata)

        return metadata

    def retrieve_certificate(self, storage_id: str) -> Tuple[bytes, Dict[str, Any]]:
        """
        Retrieves and decrypts certificate for authorized operations.
        Zero plaintext exposure on tag or AAD mismatch.
        """
        raw_bundle_bytes = self.adapter.retrieve(storage_id)
        try:
            bundle = json.loads(raw_bundle_bytes.decode("utf-8"))
            metadata = bundle.get("metadata", {})
            envelope = bundle.get("envelope", {})
        except Exception as exc:
            raise AppException(
                message="Failed to deserialize stored certificate package.",
                error_code="STORAGE_DESERIALIZE_FAILED",
                status_code=500,
            ) from exc

        doc_digest = metadata.get("document_digest", "")
        content_type = metadata.get("content_type", "")
        expected_aad = self._build_aad(storage_id, doc_digest, content_type)

        plaintext = self.encryptor.decrypt(envelope, expected_aad=expected_aad)
        return plaintext, metadata

    def get_metadata(self, storage_id: str) -> Dict[str, Any]:
        """
        Retrieves non-sensitive storage metadata without decrypting contents.
        """
        return self.adapter.get_metadata(storage_id)

    def exists(self, storage_id: str) -> bool:
        return self.adapter.exists(storage_id)

    def delete_certificate(self, storage_id: str) -> bool:
        return self.adapter.delete(storage_id)
