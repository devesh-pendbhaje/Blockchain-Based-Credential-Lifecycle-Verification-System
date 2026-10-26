from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class CertificateStorageAdapter(ABC):
    """
    Abstract interface for off-chain certificate storage.
    Enables swapping local encrypted filesystem storage with cloud object storage (S3/GCS)
    or IPFS without altering core credential lifecycle business logic.
    """

    @abstractmethod
    def store(self, storage_id: str, data: bytes, metadata: Dict[str, Any]) -> str:
        """
        Stores data payload associated with a unique storage_id and metadata.
        Returns the persistent object key/URI.
        """
        pass

    @abstractmethod
    def retrieve(self, storage_id: str) -> bytes:
        """
        Retrieves stored raw payload bytes for storage_id.
        """
        pass

    @abstractmethod
    def exists(self, storage_id: str) -> bool:
        """
        Checks whether storage_id exists in storage.
        """
        pass

    @abstractmethod
    def delete(self, storage_id: str) -> bool:
        """
        Deletes stored object where permitted. Returns True if deleted, False if not found.
        """
        pass

    @abstractmethod
    def get_metadata(self, storage_id: str) -> Dict[str, Any]:
        """
        Retrieves non-sensitive storage metadata without returning ciphertext or plaintext.
        """
        pass
