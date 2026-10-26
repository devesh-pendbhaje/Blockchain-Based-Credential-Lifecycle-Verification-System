// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "../libraries/DomainSeparatedMerkle.sol";

contract MerkleTestHelper {
    function hashLeaf(bytes32 salt, string memory key, string memory value) external pure returns (bytes32) {
        return DomainSeparatedMerkle.hashLeaf(salt, key, value);
    }

    function hashParent(bytes32 left, bytes32 right) external pure returns (bytes32) {
        return DomainSeparatedMerkle.hashParent(left, right);
    }

    function verifyProof(bytes32[] memory proof, bytes32 root, bytes32 leaf) external pure returns (bool) {
        return DomainSeparatedMerkle.verifyProof(proof, root, leaf);
    }

    function computeRoot(bytes32[] memory leaves) external pure returns (bytes32) {
        return DomainSeparatedMerkle.computeRoot(leaves);
    }
}
