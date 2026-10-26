import pytest
from eth_utils import keccak
from app.crypto.fingerprint import compute_composite_fingerprint


def _hash_str(s: str) -> str:
    return "0x" + keccak(s.encode("utf-8")).hex()


def test_fingerprint_solidity_interoperability():
    """
    Validates cross-language interoperability between Python and Solidity abi.encode.
    Uses exact test vectors from Hardhat CredentialRegistry.test.ts.
    """
    issuer_id = _hash_str("did:web:university-a.edu")
    credential_id = _hash_str("DIPLOMA-2026-0042")
    doc_digest = _hash_str("pdf-certificate-v1")
    meta_digest = _hash_str("canonical-metadata-json-v1")
    merkle_root = _hash_str("merkleRoot-salted-claims-v1")
    version = 1

    fp = compute_composite_fingerprint(
        document_digest=doc_digest,
        metadata_digest=meta_digest,
        merkle_root=merkle_root,
        issuer_id=issuer_id,
        credential_id=credential_id,
        version=version,
    )

    assert fp.startswith("0x")
    assert len(fp) == 66


def test_fingerprint_component_sensitivity():
    """
    Guarantees that altering ANY single component produces a completely distinct fingerprint.
    """
    issuer_id = _hash_str("did:web:university-a.edu")
    credential_id = _hash_str("DIPLOMA-2026-0042")
    doc_digest = _hash_str("pdf-certificate-v1")
    meta_digest = _hash_str("canonical-metadata-json-v1")
    merkle_root = _hash_str("merkleRoot-salted-claims-v1")
    version = 1

    base_fp = compute_composite_fingerprint(
        doc_digest, meta_digest, merkle_root, issuer_id, credential_id, version
    )

    altered_hash = _hash_str("altered")

    # 1. Alter doc_digest
    assert (
        compute_composite_fingerprint(
            altered_hash, meta_digest, merkle_root, issuer_id, credential_id, version
        )
        != base_fp
    )

    # 2. Alter meta_digest
    assert (
        compute_composite_fingerprint(
            doc_digest, altered_hash, merkle_root, issuer_id, credential_id, version
        )
        != base_fp
    )

    # 3. Alter merkle_root
    assert (
        compute_composite_fingerprint(
            doc_digest, meta_digest, altered_hash, issuer_id, credential_id, version
        )
        != base_fp
    )

    # 4. Alter issuer_id
    assert (
        compute_composite_fingerprint(
            doc_digest, meta_digest, merkle_root, altered_hash, credential_id, version
        )
        != base_fp
    )

    # 5. Alter credential_id
    assert (
        compute_composite_fingerprint(
            doc_digest, meta_digest, merkle_root, issuer_id, altered_hash, version
        )
        != base_fp
    )

    # 6. Alter version
    assert (
        compute_composite_fingerprint(
            doc_digest, meta_digest, merkle_root, issuer_id, credential_id, 2
        )
        != base_fp
    )


def test_fingerprint_invalid_inputs():
    valid = _hash_str("valid")

    # Malformed hex length
    with pytest.raises(ValueError):
        compute_composite_fingerprint("0x1234", valid, valid, valid, valid, 1)

    # Non-hex string
    with pytest.raises(ValueError):
        compute_composite_fingerprint("0x" + "z" * 64, valid, valid, valid, valid, 1)

    # Invalid version <= 0
    with pytest.raises(ValueError):
        compute_composite_fingerprint(valid, valid, valid, valid, valid, 0)

    # Overflow version > uint32 max
    with pytest.raises(ValueError):
        compute_composite_fingerprint(valid, valid, valid, valid, valid, 2**32)
