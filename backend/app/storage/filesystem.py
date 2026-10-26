import os
import re
import json
from pathlib import Path
from typing import Dict, Any, Optional
from app.core.exceptions import AppException
from app.storage.base import CertificateStorageAdapter

# Strict UUID / safe alphanumeric regex to eliminate path injection
SAFE_ID_REGEX = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")


class EncryptedFilesystemStorage(CertificateStorageAdapter):
    """
    Encrypted local filesystem storage adapter.
    Enforces strict path isolation, non-overwriting atomic writes,
    and restrictive permissions to prevent unauthorized host traversal.
    """

    def __init__(self, root_dir: str):
        self.root_path = Path(root_dir).resolve()
        # Create directory with parent directories
        self.root_path.mkdir(parents=True, exist_ok=True)

    def _resolve_safe_path(self, storage_id: str, suffix: str = ".enc") -> Path:
        """
        Validates storage_id and ensures resolved target path resides strictly
        within the configured root directory without directory traversal.
        """
        if not storage_id or not SAFE_ID_REGEX.match(storage_id):
            raise AppException(
                message="Invalid storage object identifier format. Must be a valid UUID.",
                error_code="INVALID_STORAGE_ID",
                status_code=400,
            )

        target_file = (self.root_path / f"{storage_id}{suffix}").resolve()
        try:
            # Check containment inside root_path
            common = Path(os.path.commonpath([str(target_file), str(self.root_path)])).resolve()
            if common != self.root_path:
                raise ValueError("Traversal detected")
        except Exception as exc:
            raise AppException(
                message="Path traversal attempt detected and blocked.",
                error_code="PATH_TRAVERSAL_DETECTED",
                status_code=400,
            ) from exc

        return target_file

    def store(self, storage_id: str, data: bytes, metadata: Dict[str, Any]) -> str:
        """
        Atomically writes encrypted payload to disk.
        Prevents partial-write corruption and accidental overwrite.
        """
        target_path = self._resolve_safe_path(storage_id)

        if target_path.exists():
            raise AppException(
                message=f"Storage object '{storage_id}' already exists and cannot be overwritten.",
                error_code="OBJECT_ALREADY_EXISTS",
                status_code=409,
            )

        # Build bundle containing envelope and safe non-secret metadata
        bundle = {
            "metadata": metadata,
            "envelope": json.loads(data.decode("utf-8")),
        }
        bundle_bytes = json.dumps(bundle, indent=2).encode("utf-8")

        # Atomic write pattern: write to temporary file, fsync, then replace
        temp_path = self.root_path / f".{storage_id}.tmp"
        try:
            with open(temp_path, "wb") as f:
                f.write(bundle_bytes)
                f.flush()
                os.fsync(f.fileno())

            # Set restrictive permissions (0o600 = owner rw only) if platform supports chmod
            try:
                os.chmod(temp_path, 0o600)
            except (OSError, NotImplementedError):
                pass

            os.replace(temp_path, target_path)
            return str(target_path)
        except Exception as exc:
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except OSError:
                    pass
            if isinstance(exc, AppException):
                raise
            raise AppException(
                message=f"Filesystem write failed: {str(exc)}",
                error_code="STORAGE_WRITE_FAILED",
                status_code=500,
            ) from exc

    def retrieve(self, storage_id: str) -> bytes:
        """
        Retrieves stored raw payload bytes for storage_id.
        """
        target_path = self._resolve_safe_path(storage_id)
        if not target_path.exists():
            raise AppException(
                message=f"Storage object '{storage_id}' not found.",
                error_code="STORAGE_OBJECT_NOT_FOUND",
                status_code=404,
            )

        try:
            with open(target_path, "rb") as f:
                content = f.read()
            return content
        except Exception as exc:
            raise AppException(
                message=f"Failed to read storage object: {str(exc)}",
                error_code="STORAGE_READ_FAILED",
                status_code=500,
            ) from exc

    def exists(self, storage_id: str) -> bool:
        try:
            target_path = self._resolve_safe_path(storage_id)
            return target_path.exists()
        except AppException:
            return False

    def delete(self, storage_id: str) -> bool:
        target_path = self._resolve_safe_path(storage_id)
        if not target_path.exists():
            return False
        try:
            target_path.unlink()
            return True
        except Exception as exc:
            raise AppException(
                message=f"Failed to delete storage object: {str(exc)}",
                error_code="STORAGE_DELETE_FAILED",
                status_code=500,
            ) from exc

    def get_metadata(self, storage_id: str) -> Dict[str, Any]:
        """
        Retrieves non-sensitive metadata without leaking ciphertext or plaintext.
        """
        raw_bytes = self.retrieve(storage_id)
        try:
            bundle = json.loads(raw_bytes.decode("utf-8"))
            meta = bundle.get("metadata", {})
            return {
                "storage_id": storage_id,
                "content_type": meta.get("content_type"),
                "byte_size": meta.get("byte_size"),
                "document_digest": meta.get("document_digest"),
                "envelope_version": bundle.get("envelope", {}).get("envelope_version"),
                "created_at": meta.get("created_at"),
            }
        except Exception as exc:
            raise AppException(
                message="Failed to parse storage object metadata.",
                error_code="METADATA_PARSE_FAILED",
                status_code=500,
            ) from exc
