import os
import json
import pytest
import tempfile
import shutil
from app.storage.encryption import EnvelopeEncryption
from app.storage.filesystem import EncryptedFilesystemStorage
from app.storage.service import CertificateStorageService
from app.core.exceptions import AppException


@pytest.fixture
def temp_storage_dir():
    dir_path = tempfile.mkdtemp()
    yield dir_path
    shutil.rmtree(dir_path, ignore_errors=True)


def test_encryption_roundtrip_and_nonce_uniqueness():
    """
    Validates AES-256-GCM authenticated encryption roundtrip and guarantees
    that every encryption operation generates a unique 96-bit nonce.
    """
    key = os.urandom(32)
    encryptor = EnvelopeEncryption(key)

    plaintext = b"Top secret credential document contents"
    aad = b"storage-id-123:sha256-doc:application/pdf"

    envelope = encryptor.encrypt(plaintext, aad=aad)
    decrypted = encryptor.decrypt(envelope, expected_aad=aad)

    assert decrypted == plaintext

    # Nonce uniqueness test
    nonces = set()
    for _ in range(500):
        env = encryptor.encrypt(plaintext, aad=aad)
        assert env["nonce"] not in nonces
        nonces.add(env["nonce"])
    assert len(nonces) == 500


def test_encryption_tamper_detection():
    """
    Guarantees that tampering with ciphertext, authentication tag, nonce, or AAD
    causes authentication failure and prevents plaintext exposure.
    """
    key = os.urandom(32)
    encryptor = EnvelopeEncryption(key)
    plaintext = b"Important diploma bytes"
    aad = b"context-aad-1"

    envelope = encryptor.encrypt(plaintext, aad=aad)

    # 1. Mutate ciphertext
    tampered_ct = envelope.copy()
    ct_bytes = bytearray.fromhex(tampered_ct["ciphertext"])
    ct_bytes[0] ^= 0x01  # Flip one bit
    tampered_ct["ciphertext"] = ct_bytes.hex()
    with pytest.raises(AppException) as exc_info:
        encryptor.decrypt(tampered_ct, expected_aad=aad)
    assert exc_info.value.error_code == "CIPHERTEXT_AUTH_FAILED"

    # 2. Mutate auth tag
    tampered_tag = envelope.copy()
    tag_bytes = bytearray.fromhex(tampered_tag["auth_tag"])
    tag_bytes[0] ^= 0x01
    tampered_tag["auth_tag"] = tag_bytes.hex()
    with pytest.raises(AppException) as exc_info:
        encryptor.decrypt(tampered_tag, expected_aad=aad)
    assert exc_info.value.error_code == "CIPHERTEXT_AUTH_FAILED"

    # 3. Mutate nonce
    tampered_nonce = envelope.copy()
    nonce_bytes = bytearray.fromhex(tampered_nonce["nonce"])
    nonce_bytes[0] ^= 0x01
    tampered_nonce["nonce"] = nonce_bytes.hex()
    with pytest.raises(AppException) as exc_info:
        encryptor.decrypt(tampered_nonce, expected_aad=aad)
    assert exc_info.value.error_code == "CIPHERTEXT_AUTH_FAILED"

    # 4. AAD mismatch
    with pytest.raises(AppException) as exc_info:
        encryptor.decrypt(envelope, expected_aad=b"wrong-context-aad")
    assert exc_info.value.error_code == "AAD_MISMATCH"


def test_encryption_wrong_key_and_invalid_key_length():
    """
    Rejects invalid key lengths and verifies wrong key fails decryption.
    """
    # Key length validation
    with pytest.raises(AppException) as exc_info:
        EnvelopeEncryption(b"short-key")
    assert exc_info.value.error_code == "INVALID_KEY_LENGTH"

    key_a = os.urandom(32)
    key_b = os.urandom(32)

    enc_a = EnvelopeEncryption(key_a)
    enc_b = EnvelopeEncryption(key_b)

    envelope = enc_a.encrypt(b"hello", aad=b"test")
    with pytest.raises(AppException) as exc_info:
        enc_b.decrypt(envelope, expected_aad=b"test")
    assert exc_info.value.error_code == "CIPHERTEXT_AUTH_FAILED"


def test_storage_service_persistence_and_no_plaintext_leakage(temp_storage_dir):
    """
    Tests end-to-end CertificateStorageService:
    1. Stores encrypted certificate.
    2. Inspects saved file on disk to guarantee NO plaintext exists in stored envelope.
    3. Retrieves and decrypts certificate.
    4. Proves key persistence across simulated service restarts.
    """
    test_key_hex = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    secret_content = b"%PDF-1.4\nSuper Sensitive Student Identification Data: SSN-000-11-2222\n%%EOF"

    svc1 = CertificateStorageService(
        encryption_key_hex=test_key_hex,
        storage_root_dir=temp_storage_dir,
    )

    meta = svc1.store_certificate(
        raw_bytes=secret_content,
        content_type="application/pdf",
        document_digest="0x" + "a" * 64,
    )
    storage_id = meta["storage_id"]

    # Verify physical file on disk does NOT contain secret plaintext
    stored_file_path = os.path.join(temp_storage_dir, f"{storage_id}.enc")
    assert os.path.exists(stored_file_path)

    with open(stored_file_path, "rb") as f:
        disk_bytes = f.read()
    assert b"Super Sensitive Student Identification Data" not in disk_bytes

    # Simulate service restart with same key
    svc2 = CertificateStorageService(
        encryption_key_hex=test_key_hex,
        storage_root_dir=temp_storage_dir,
    )
    decrypted, retrieved_meta = svc2.retrieve_certificate(storage_id)
    assert decrypted == secret_content
    assert retrieved_meta["content_type"] == "application/pdf"


def test_storage_path_traversal_and_overwrite_protection(temp_storage_dir):
    """
    Ensures storage adapter blocks path traversal attempts and accidental overwrites.
    """
    storage = EncryptedFilesystemStorage(temp_storage_dir)

    # Path traversal rejection
    with pytest.raises(AppException) as exc_info:
        storage.retrieve("../../etc/passwd")
    assert exc_info.value.error_code == "INVALID_STORAGE_ID"

    with pytest.raises(AppException) as exc_info:
        storage.retrieve("..\\..\\boot.ini")
    assert exc_info.value.error_code == "INVALID_STORAGE_ID"

    # Accidental overwrite protection
    valid_uuid = "a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d"
    dummy_envelope = json.dumps({"envelope_version": 1, "nonce": "00" * 12, "ciphertext": "00", "auth_tag": "00" * 16}).encode()
    storage.store(valid_uuid, dummy_envelope, {"created_at": "now"})

    with pytest.raises(AppException) as exc_info:
        storage.store(valid_uuid, dummy_envelope, {"created_at": "again"})
    assert exc_info.value.error_code == "OBJECT_ALREADY_EXISTS"
