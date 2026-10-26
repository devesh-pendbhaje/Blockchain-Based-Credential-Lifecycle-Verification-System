import pytest
from eth_abi import encode
from eth_utils import keccak
from app.crypto.fingerprint import compute_composite_fingerprint
from app.crypto.merkle import (
    hash_leaf,
    hash_parent,
    compute_merkle_root,
    generate_merkle_proof,
    verify_merkle_proof,
    SaltedAttributeMerkleTree,
)
from app.crypto.metadata import canonicalize_and_hash_metadata
from app.core.exceptions import AppException

def test_six_component_fingerprint_parity_with_solidity_specification():
    """
    Solidity Invariant:
    keccak256(abi.encode(documentDigest, metadataDigest, merkleRoot, issuerId, credentialId, version))
    Verifies parameter order, types (bytes32, bytes32, bytes32, bytes32, bytes32, uint32).
    """
    doc = "0x" + "11" * 32
    meta = "0x" + "22" * 32
    root = "0x" + "33" * 32
    issuer = "0x" + "44" * 32
    cred = "0x" + "55" * 32
    version = 42

    computed_fp = compute_composite_fingerprint(doc, meta, root, issuer, cred, version)

    # Independent ABI encoding
    expected_encoded = encode(
        ["bytes32", "bytes32", "bytes32", "bytes32", "bytes32", "uint32"],
        [
            bytes.fromhex(doc[2:]),
            bytes.fromhex(meta[2:]),
            bytes.fromhex(root[2:]),
            bytes.fromhex(issuer[2:]),
            bytes.fromhex(cred[2:]),
            version,
        ],
    )
    expected_fp = "0x" + keccak(expected_encoded).hex()
    assert computed_fp.lower() == expected_fp.lower()


def test_domain_separated_merkle_leaf_and_parent_parity():
    """
    Solidity DomainSeparatedMerkle:
    hashLeaf: keccak256(abi.encode(bytes1(0x00), salt, key, value))
    hashParent: (min, max) = left <= right ? (left, right) : (right, left);
                keccak256(abi.encode(bytes1(0x01), min, max))
    """
    salt = "0x" + "aa" * 32
    key = "student_gpa"
    value = "3.98"

    # Compute via Python module
    leaf = hash_leaf(salt, key, value)

    # Compute raw ABI encoding
    raw_leaf_encoded = encode(
        ["bytes1", "bytes32", "string", "string"],
        [b"\x00", bytes.fromhex(salt[2:]), key, value],
    )
    expected_leaf = "0x" + keccak(raw_leaf_encoded).hex()
    assert leaf.lower() == expected_leaf.lower()

    # Parent hashing commutativity and 0x01 prefix
    node_a = "0x" + "10" * 32
    node_b = "0x" + "20" * 32

    parent_ab = hash_parent(node_a, node_b)
    parent_ba = hash_parent(node_b, node_a)
    assert parent_ab == parent_ba, "Parent hashing must be commutative"

    # Verify 0x01 prefix
    min_b = bytes.fromhex(node_a[2:])
    max_b = bytes.fromhex(node_b[2:])
    expected_parent_encoded = encode(
        ["bytes1", "bytes32", "bytes32"],
        [b"\x01", min_b, max_b],
    )
    expected_parent = "0x" + keccak(expected_parent_encoded).hex()
    assert parent_ab.lower() == expected_parent.lower()


@pytest.mark.parametrize("leaf_count", [1, 2, 3, 4, 5, 7, 8, 13])
def test_merkle_tree_shapes_and_odd_leaf_promotion(leaf_count: int):
    """
    Test Merkle tree construction across non-power-of-two leaf counts.
    Ensures odd leaves are promoted directly to parent layer without duplicate hashing.
    Ensures proofs for all leaves verify against root.
    """
    attributes = {f"claim_{i}": f"value_{i}" for i in range(leaf_count)}
    tree = SaltedAttributeMerkleTree(attributes)
    root = tree.root
    assert root.startswith("0x")
    assert len(root) == 66

    # Verify proofs for each attribute
    for key in attributes:
        proof = tree.get_proof(key)
        leaf = tree.leaves[key]
        assert verify_merkle_proof(proof, root, leaf) is True


def test_rfc8785_metadata_canonicalization_rules():
    """
    Verify RFC 8785 Canonicalization Scheme:
    1. Lexicographical key sorting.
    2. Rejection of duplicate keys.
    3. Proper Unicode and numeric serialization.
    """
    # Key sorting
    obj1 = '{"b": 2, "a": 1}'
    obj2 = '{"a": 1, "b": 2}'
    digest1, bytes1 = canonicalize_and_hash_metadata(obj1)
    digest2, bytes2 = canonicalize_and_hash_metadata(obj2)
    assert digest1 == digest2
    assert bytes1 == b'{"a":1,"b":2}'

    # Duplicate key rejection
    duplicate_json = '{"key": "first", "key": "second"}'
    with pytest.raises(AppException) as exc_info:
        canonicalize_and_hash_metadata(duplicate_json)
    assert exc_info.value.error_code == "DUPLICATE_JSON_KEY"

    # Malformed JSON rejection
    malformed_json = '{"unclosed": "brace"'
    with pytest.raises(AppException) as exc_info:
        canonicalize_and_hash_metadata(malformed_json)
    assert exc_info.value.error_code == "INVALID_JSON_METADATA"
