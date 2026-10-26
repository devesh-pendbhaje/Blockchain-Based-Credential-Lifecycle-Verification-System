import os
from typing import Dict, List, Optional, Tuple
from eth_abi import encode
from eth_utils import keccak
from app.core.exceptions import AppException


def _clean_bytes32(hex_str: str) -> bytes:
    clean = hex_str.strip().lower()
    if clean.startswith("0x"):
        clean = clean[2:]
    if len(clean) != 64:
        raise ValueError(f"Expected 64 hex characters (32 bytes), got {len(clean)}")
    return bytes.fromhex(clean)


def generate_salt() -> str:
    """
    Generates a cryptographically secure 256-bit blinding salt using os.urandom.
    Never uses timestamps, counters, or pseudorandom PRNGs.
    """
    return "0x" + os.urandom(32).hex()


def hash_leaf(salt: str, key: str, value: str) -> str:
    """
    Computes a domain-separated leaf hash matching Solidity DomainSeparatedMerkle.hashLeaf:
    keccak256(abi.encode(bytes1(0x00), salt, key, value))
    """
    salt_bytes = _clean_bytes32(salt)
    encoded = encode(
        ["bytes1", "bytes32", "string", "string"],
        [b"\x00", salt_bytes, key, value],
    )
    return "0x" + keccak(encoded).hex().lower()


def hash_parent(left: str, right: str) -> str:
    """
    Computes a domain-separated commutative sorted-pair parent node hash matching
    Solidity DomainSeparatedMerkle.hashParent:
    (minNode, maxNode) = left <= right ? (left, right) : (right, left);
    keccak256(abi.encode(bytes1(0x01), minNode, maxNode))
    """
    left_b = _clean_bytes32(left)
    right_b = _clean_bytes32(right)
    min_b, max_b = (left_b, right_b) if left_b <= right_b else (right_b, left_b)

    encoded = encode(
        ["bytes1", "bytes32", "bytes32"],
        [b"\x01", min_b, max_b],
    )
    return "0x" + keccak(encoded).hex().lower()


def compute_merkle_root(leaf_hashes: List[str]) -> str:
    """
    Computes the Merkle root from an array of precomputed leaf hashes,
    promoting unpaired odd leaves directly to the parent layer without duplication.
    Matches Solidity DomainSeparatedMerkle.computeRoot.
    """
    if not leaf_hashes:
        raise AppException(
            message="Cannot compute Merkle root on empty leaves array.",
            error_code="EMPTY_LEAVES_NOT_ALLOWED",
            status_code=400,
        )
    if len(leaf_hashes) == 1:
        return leaf_hashes[0].lower()

    current_level = [h.lower() for h in leaf_hashes]

    while len(current_level) > 1:
        next_level = []
        total = len(current_level)
        for i in range(0, total, 2):
            if i + 1 < total:
                next_level.append(hash_parent(current_level[i], current_level[i + 1]))
            else:
                # Promote unpaired odd leaf directly to parent layer without hashing against itself
                next_level.append(current_level[i])
        current_level = next_level

    return current_level[0]


def generate_merkle_proof(leaf_hashes: List[str], target_index: int) -> List[str]:
    """
    Generates a sibling proof path for the target leaf index ascending from leaf to root.
    Promoted odd nodes correctly skip pairing at levels where they were unpaired.
    """
    if not leaf_hashes:
        raise AppException(
            message="Cannot generate proof on empty leaves array.",
            error_code="EMPTY_LEAVES_NOT_ALLOWED",
            status_code=400,
        )
    if target_index < 0 or target_index >= len(leaf_hashes):
        raise AppException(
            message=f"Target leaf index {target_index} out of range (0 to {len(leaf_hashes) - 1}).",
            error_code="INDEX_OUT_OF_BOUNDS",
            status_code=400,
        )

    proof: List[str] = []
    current_level = [h.lower() for h in leaf_hashes]
    idx = target_index

    while len(current_level) > 1:
        total = len(current_level)
        # Check if current node has a sibling at this level
        if idx % 2 == 0:
            if idx + 1 < total:
                proof.append(current_level[idx + 1])
        else:
            proof.append(current_level[idx - 1])

        # Compute next level
        next_level = []
        for i in range(0, total, 2):
            if i + 1 < total:
                next_level.append(hash_parent(current_level[i], current_level[i + 1]))
            else:
                next_level.append(current_level[i])

        current_level = next_level
        idx = idx // 2

    return proof


def verify_merkle_proof(proof: List[str], root: str, leaf: str) -> bool:
    """
    Verifies a domain-separated Merkle proof against a target root matching
    Solidity DomainSeparatedMerkle.verifyProof.
    """
    computed = leaf.lower()
    for sibling in proof:
        computed = hash_parent(computed, sibling.lower())
    return computed == root.lower()


class SaltedAttributeMerkleTree:
    """
    Cryptographically secure salted attribute Merkle tree builder and proof generator.
    Guarantees canonical attribute sorting and 1-to-1 parity with DomainSeparatedMerkle.sol.
    """

    def __init__(
        self,
        attributes: Dict[str, str],
        salts: Optional[Dict[str, str]] = None,
    ):
        if not attributes:
            raise AppException(
                message="Cannot construct Merkle tree with empty attributes.",
                error_code="EMPTY_ATTRIBUTES",
                status_code=400,
            )

        # Canonical deterministic key ordering (lexicographical sort)
        self.keys = sorted(attributes.keys())
        self.attributes = attributes
        self.salts: Dict[str, str] = {}
        self.leaves: Dict[str, str] = {}
        self.ordered_leaves: List[str] = []

        provided_salts = salts or {}
        for key in self.keys:
            val = str(attributes[key])
            salt = provided_salts.get(key) or generate_salt()
            # Validate salt format
            _clean_bytes32(salt)
            self.salts[key] = salt.lower()
            leaf = hash_leaf(self.salts[key], key, val)
            self.leaves[key] = leaf
            self.ordered_leaves.append(leaf)

        self.root = compute_merkle_root(self.ordered_leaves)

    def get_proof(self, key: str) -> List[str]:
        if key not in self.leaves:
            raise AppException(
                message=f"Attribute key '{key}' not found in Merkle tree.",
                error_code="ATTRIBUTE_NOT_FOUND",
                status_code=404,
            )
        idx = self.keys.index(key)
        return generate_merkle_proof(self.ordered_leaves, idx)

    def get_all_proofs(self) -> Dict[str, List[str]]:
        return {key: self.get_proof(key) for key in self.keys}
