import os
from typing import Dict, Any, Optional
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag
from app.core.exceptions import AppException


class EnvelopeEncryption:
    """
    Authenticated encryption for certificates at rest using AES-256-GCM.
    Enforces 256-bit key requirement, unique 96-bit nonces, and AAD integrity.
    """

    ENVELOPE_VERSION = 1
    NONCE_BYTES_LENGTH = 12  # Standard 96-bit AES-GCM nonce

    def __init__(self, key: bytes):
        if len(key) != 32:
            raise AppException(
                message=f"Encryption key must be exactly 32 bytes (256 bits), got {len(key)} bytes.",
                error_code="INVALID_KEY_LENGTH",
                status_code=500,
            )
        self._key = key
        self._aesgcm = AESGCM(key)

    def encrypt(
        self,
        plaintext: bytes,
        aad: bytes = b"",
    ) -> Dict[str, Any]:
        """
        Encrypts plaintext using AES-256-GCM with a newly generated random 96-bit nonce.
        Never reuses nonces under any circumstance.
        """
        if not plaintext:
            raise AppException(
                message="Cannot encrypt empty payload.",
                error_code="EMPTY_PAYLOAD",
                status_code=400,
            )

        nonce = os.urandom(self.NONCE_BYTES_LENGTH)
        try:
            # AESGCM encrypt appends the 16-byte authentication tag to the ciphertext
            ciphertext_with_tag = self._aesgcm.encrypt(nonce, plaintext, aad)
        except Exception as exc:
            raise AppException(
                message="Encryption failed.",
                error_code="ENCRYPTION_FAILED",
                status_code=500,
            ) from exc

        # Split ciphertext and tag for explicit representation in envelope
        ciphertext = ciphertext_with_tag[:-16]
        tag = ciphertext_with_tag[-16:]

        return {
            "envelope_version": self.ENVELOPE_VERSION,
            "nonce": nonce.hex(),
            "ciphertext": ciphertext.hex(),
            "auth_tag": tag.hex(),
            "aad_hex": aad.hex() if aad else "",
        }

    def decrypt(
        self,
        envelope: Dict[str, Any],
        expected_aad: bytes = b"",
    ) -> bytes:
        """
        Decrypts envelope and verifies authentication tag and AAD.
        Rejects modified ciphertext, authentication tags, nonces, and incompatible versions.
        Zero plaintext exposure on failure.
        """
        version = envelope.get("envelope_version")
        if version != self.ENVELOPE_VERSION:
            raise AppException(
                message=f"Unsupported envelope version '{version}'. Expected {self.ENVELOPE_VERSION}.",
                error_code="UNSUPPORTED_ENVELOPE_VERSION",
                status_code=400,
            )

        nonce_hex = envelope.get("nonce")
        ciphertext_hex = envelope.get("ciphertext")
        tag_hex = envelope.get("auth_tag")
        aad_hex = envelope.get("aad_hex", "")

        if not nonce_hex or not ciphertext_hex or not tag_hex:
            raise AppException(
                message="Corrupted encryption envelope: missing nonce, ciphertext, or auth tag.",
                error_code="MALFORMED_ENVELOPE",
                status_code=400,
            )

        try:
            nonce = bytes.fromhex(nonce_hex)
            ciphertext = bytes.fromhex(ciphertext_hex)
            tag = bytes.fromhex(tag_hex)
        except ValueError as exc:
            raise AppException(
                message="Malformed hex representation in encryption envelope.",
                error_code="MALFORMED_ENVELOPE_HEX",
                status_code=400,
            ) from exc

        if len(nonce) != self.NONCE_BYTES_LENGTH:
            raise AppException(
                message=f"Invalid nonce length ({len(nonce)} bytes). Expected {self.NONCE_BYTES_LENGTH}.",
                error_code="INVALID_NONCE_LENGTH",
                status_code=400,
            )

        # Verify AAD matches expected AAD
        stored_aad = bytes.fromhex(aad_hex) if aad_hex else b""
        if expected_aad and stored_aad != expected_aad:
            raise AppException(
                message="Additional Authenticated Data (AAD) mismatch. Verification failed.",
                error_code="AAD_MISMATCH",
                status_code=400,
            )

        # Recombine ciphertext and tag for AESGCM verification
        combined = ciphertext + tag

        try:
            plaintext = self._aesgcm.decrypt(nonce, combined, stored_aad)
            return plaintext
        except InvalidTag as exc:
            # Rejects forged or altered ciphertext/tag without leaking details
            raise AppException(
                message="Authentication failed. The ciphertext, nonce, or authentication tag has been tampered with.",
                error_code="CIPHERTEXT_AUTH_FAILED",
                status_code=400,
            ) from exc
        except Exception as exc:
            raise AppException(
                message="Decryption failed.",
                error_code="DECRYPTION_FAILED",
                status_code=400,
            ) from exc
