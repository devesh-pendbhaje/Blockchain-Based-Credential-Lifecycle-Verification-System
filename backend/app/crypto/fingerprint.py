import re
from eth_abi import encode
from eth_utils import keccak


def _to_bytes32(hex_str: str) -> bytes:
    clean = hex_str.strip().lower()
    if clean.startswith("0x"):
        clean = clean[2:]
    if len(clean) != 64:
        raise ValueError(f"Expected 64 hex characters (32 bytes), got {len(clean)}")
    return bytes.fromhex(clean)


def compute_composite_fingerprint(
    document_digest: str,
    metadata_digest: str,
    merkle_root: str,
    issuer_id: str,
    credential_id: str,
    version: int,
) -> str:
    """
    Computes the authoritative 6-input composite credential fingerprint:
    keccak256(abi.encode(documentDigest, metadataDigest, merkleRoot, issuerId, credentialId, version))

    Parameter order and Solidity types:
    1. documentDigest: bytes32
    2. metadataDigest: bytes32
    3. merkleRoot: bytes32
    4. issuerId: bytes32
    5. credentialId: bytes32
    6. version: uint32
    """
    if version < 1 or version > 0xFFFFFFFF:
        raise ValueError(f"Version must fit in uint32 (1 to 4294967295), got {version}")

    doc_b = _to_bytes32(document_digest)
    meta_b = _to_bytes32(metadata_digest)
    root_b = _to_bytes32(merkle_root)
    issuer_b = _to_bytes32(issuer_id)
    cred_b = _to_bytes32(credential_id)

    encoded = encode(
        ["bytes32", "bytes32", "bytes32", "bytes32", "bytes32", "uint32"],
        [doc_b, meta_b, root_b, issuer_b, cred_b, int(version)],
    )

    h = keccak(encoded)
    return "0x" + h.hex()
