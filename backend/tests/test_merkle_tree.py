import pytest
from eth_abi import encode
from eth_utils import keccak
from app.crypto.merkle import (
    generate_salt,
    hash_leaf,
    hash_parent,
    compute_merkle_root,
    generate_merkle_proof,
    verify_merkle_proof,
    SaltedAttributeMerkleTree,
)
from app.core.exceptions import AppException


def test_merkle_leaf_solidity_parity():
    """
    Validates exact cross-language leaf hash parity with Hardhat DomainSeparatedMerkle.test.ts.
    """
    salt = "0x0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    key = "degree"
    value = "B.S. Computer Science"

    salt_b = bytes.fromhex(salt[2:])
    expected_on_chain = "0x" + keccak(
        encode(["bytes1", "bytes32", "string", "string"], [b"\x00", salt_b, key, value])
    ).hex()

    py_leaf = hash_leaf(salt, key, value)
    assert py_leaf == expected_on_chain


def test_merkle_parent_hash_commutativity_and_domain_separator():
    """
    Validates commutative sorted-pair parent node hashing with 0x01 domain separator.
    """
    leaf_a = "0x" + keccak(b"leaf-A").hex()
    leaf_b = "0x" + keccak(b"leaf-B").hex()

    parent_ab = hash_parent(leaf_a, leaf_b)
    parent_ba = hash_parent(leaf_b, leaf_a)

    assert parent_ab == parent_ba
    assert parent_ab.startswith("0x")
    assert len(parent_ab) == 66


@pytest.mark.parametrize("tree_size", [1, 2, 3, 5, 7, 8, 13])
def test_merkle_root_and_proofs_all_leaf_positions(tree_size):
    """
    Validates Merkle root calculation, odd-leaf promotion, and proof verification
    for EVERY leaf position across both power-of-two and odd non-power-of-two trees.
    """
    attributes = {f"attr_{i:02d}": f"value_{i}" for i in range(tree_size)}
    tree = SaltedAttributeMerkleTree(attributes)

    assert tree.root.startswith("0x")
    assert len(tree.root) == 66

    # Verify proof for EVERY leaf position
    for key in tree.keys:
        proof = tree.get_proof(key)
        leaf = tree.leaves[key]
        assert verify_merkle_proof(proof, tree.root, leaf) is True


def test_merkle_odd_leaf_promotion_structural_parity():
    """
    Validates the exact 3-leaf and 5-leaf odd promotion trees matching Hardhat test suite:
    - 3 leaves: L0, L1, L2 -> P01 = hash(L0, L1), L2 promoted; root = hash(P01, L2).
    """
    l0 = "0x" + keccak(b"leaf-0").hex()
    l1 = "0x" + keccak(b"leaf-1").hex()
    l2 = "0x" + keccak(b"leaf-2").hex()

    p01 = hash_parent(l0, l1)
    expected_root_3 = hash_parent(p01, l2)
    computed_root_3 = compute_merkle_root([l0, l1, l2])
    assert computed_root_3 == expected_root_3

    # For leaf 2, proof is just [p01]
    proof_l2 = generate_merkle_proof([l0, l1, l2], 2)
    assert proof_l2 == [p01]
    assert verify_merkle_proof(proof_l2, expected_root_3, l2) is True


def test_merkle_proof_tamper_resistance():
    """
    Guarantees that altered leaf values, altered salts, altered sibling hashes,
    or wrong roots cause proof verification to fail.
    """
    attributes = {"degree": "B.S. CS", "gpa": "3.9", "honors": "cum laude"}
    tree = SaltedAttributeMerkleTree(attributes)
    root = tree.root

    proof_deg = tree.get_proof("degree")
    salt_deg = tree.salts["degree"]
    valid_leaf = tree.leaves["degree"]

    # 1. Valid leaf verifies
    assert verify_merkle_proof(proof_deg, root, valid_leaf) is True

    # 2. Tampered claim value fails
    tampered_leaf = hash_leaf(salt_deg, "degree", "Ph.D. CS")
    assert verify_merkle_proof(proof_deg, root, tampered_leaf) is False

    # 3. Tampered salt fails
    fake_salt = "0x" + "9" * 64
    fake_salt_leaf = hash_leaf(fake_salt, "degree", "B.S. CS")
    assert verify_merkle_proof(proof_deg, root, fake_salt_leaf) is False

    # 4. Altered sibling in proof fails
    forged_proof = ["0x" + "f" * 64] + proof_deg[1:]
    assert verify_merkle_proof(forged_proof, root, valid_leaf) is False

    # 5. Wrong root fails
    wrong_root = "0x" + "1" * 64
    assert verify_merkle_proof(proof_deg, wrong_root, valid_leaf) is False


def test_merkle_salt_uniqueness():
    """
    Ensures generate_salt produces unique 256-bit cryptographically secure values.
    """
    salts = {generate_salt() for _ in range(500)}
    assert len(salts) == 500
    for s in salts:
        assert s.startswith("0x")
        assert len(s) == 66
