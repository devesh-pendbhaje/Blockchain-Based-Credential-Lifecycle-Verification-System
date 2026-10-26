// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/**
 * @title DomainSeparatedMerkle
 * @notice Custom domain-separated, sorted-pair Merkle tree verification and hashing library.
 * @dev Uses 0x00 prefix for leaves and 0x01 prefix for internal parent nodes.
 *      NOT byte-for-byte compatible with OpenZeppelin's standard MerkleProof.
 */
library DomainSeparatedMerkle {
    error EmptyLeavesNotAllowed();
    error InvalidProofLength();

    /**
     * @notice Computes a domain-separated leaf hash.
     * @param salt 256-bit cryptographically secure random blinding salt.
     * @param key Attribute claim key.
     * @param value Attribute claim value.
     */
    function hashLeaf(
        bytes32 salt,
        string memory key,
        string memory value
    ) internal pure returns (bytes32) {
        return keccak256(abi.encode(bytes1(0x00), salt, key, value));
    }

    /**
     * @notice Computes a domain-separated commutative sorted-pair parent node hash.
     * @param left Child node A.
     * @param right Child node B.
     */
    function hashParent(bytes32 left, bytes32 right) internal pure returns (bytes32) {
        (bytes32 minNode, bytes32 maxNode) = left <= right ? (left, right) : (right, left);
        return keccak256(abi.encode(bytes1(0x01), minNode, maxNode));
    }

    /**
     * @notice Verifies a domain-separated Merkle proof against a target root.
     * @param proof Sibling hashes ascending from leaf to root.
     * @param root Expected Merkle root.
     * @param leaf Computed leaf hash.
     */
    function verifyProof(
        bytes32[] memory proof,
        bytes32 root,
        bytes32 leaf
    ) internal pure returns (bool) {
        bytes32 computedHash = leaf;

        for (uint256 i = 0; i < proof.length; i++) {
            computedHash = hashParent(computedHash, proof[i]);
        }

        return computedHash == root;
    }

    /**
     * @notice Computes the Merkle root from an array of precomputed leaf hashes,
     *         promoting unpaired odd leaves directly to the parent level without duplication.
     * @param leaves Array of leaf hashes.
     */
    function computeRoot(bytes32[] memory leaves) internal pure returns (bytes32) {
        uint256 total = leaves.length;
        if (total == 0) {
            revert EmptyLeavesNotAllowed();
        }
        if (total == 1) {
            return leaves[0];
        }

        bytes32[] memory currentLevel = leaves;

        while (total > 1) {
            uint256 nextTotal = (total + 1) / 2;
            bytes32[] memory nextLevel = new bytes32[](nextTotal);

            uint256 writeIndex = 0;
            for (uint256 i = 0; i < total; i += 2) {
                if (i + 1 < total) {
                    nextLevel[writeIndex] = hashParent(currentLevel[i], currentLevel[i + 1]);
                } else {
                    // Promote unpaired odd leaf directly to parent layer
                    nextLevel[writeIndex] = currentLevel[i];
                }
                writeIndex++;
            }

            currentLevel = nextLevel;
            total = nextTotal;
        }

        return currentLevel[0];
    }
}
