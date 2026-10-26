import { expect } from "chai";
import { ethers } from "hardhat";
import { MerkleTestHelper } from "../typechain-types";

describe("DomainSeparatedMerkle Library", function () {
  let merkleHelper: MerkleTestHelper;

  beforeEach(async function () {
    const MerkleTestHelperFactory = await ethers.getContractFactory("MerkleTestHelper");
    merkleHelper = await MerkleTestHelperFactory.deploy();
    await merkleHelper.waitForDeployment();
  });

  describe("Leaf & Parent Hashing", function () {
    it("hashes leaf using domain separator 0x00 and typed encoding", async function () {
      const salt = "0x0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef";
      const key = "degree";
      const value = "B.S. Computer Science";

      const expected = ethers.keccak256(
        ethers.AbiCoder.defaultAbiCoder().encode(
          ["bytes1", "bytes32", "string", "string"],
          ["0x00", salt, key, value]
        )
      );

      const onChain = await merkleHelper.hashLeaf(salt, key, value);
      expect(onChain).to.equal(expected);
    });

    it("hashes parent using domain separator 0x01 and sorted pairs", async function () {
      const hashA = ethers.keccak256(ethers.toUtf8Bytes("leaf-A"));
      const hashB = ethers.keccak256(ethers.toUtf8Bytes("leaf-B"));

      const [left, right] = hashA.toLowerCase() < hashB.toLowerCase() ? [hashA, hashB] : [hashB, hashA];

      const expected = ethers.keccak256(
        ethers.AbiCoder.defaultAbiCoder().encode(
          ["bytes1", "bytes32", "bytes32"],
          ["0x01", left, right]
        )
      );

      // Call in order (A, B) and reversed order (B, A) - must yield identical commutative hash
      const onChain1 = await merkleHelper.hashParent(hashA, hashB);
      const onChain2 = await merkleHelper.hashParent(hashB, hashA);

      expect(onChain1).to.equal(expected);
      expect(onChain2).to.equal(expected);
    });
  });

  describe("Merkle Root Calculation & Odd-Leaf Promotion", function () {
    it("reverts root calculation on empty leaves array", async function () {
      await expect(merkleHelper.computeRoot([])).to.be.revertedWithCustomError(
        merkleHelper,
        "EmptyLeavesNotAllowed"
      );
    });

    it("returns the leaf itself when array length is 1", async function () {
      const leaf0 = ethers.keccak256(ethers.toUtf8Bytes("single-leaf"));
      const root = await merkleHelper.computeRoot([leaf0]);
      expect(root).to.equal(leaf0);
    });

    it("computes root for even number of leaves (2 leaves)", async function () {
      const leaf0 = ethers.keccak256(ethers.toUtf8Bytes("leaf-0"));
      const leaf1 = ethers.keccak256(ethers.toUtf8Bytes("leaf-1"));

      const expectedRoot = await merkleHelper.hashParent(leaf0, leaf1);
      const root = await merkleHelper.computeRoot([leaf0, leaf1]);
      expect(root).to.equal(expectedRoot);
    });

    it("promotes unpaired odd leaf directly to parent layer (3 leaves)", async function () {
      const leaf0 = ethers.keccak256(ethers.toUtf8Bytes("leaf-0"));
      const leaf1 = ethers.keccak256(ethers.toUtf8Bytes("leaf-1"));
      const leaf2 = ethers.keccak256(ethers.toUtf8Bytes("leaf-2")); // Unpaired odd leaf

      // Level 1: pair(leaf0, leaf1) -> parent01; leaf2 promoted directly -> parent01 and leaf2
      const parent01 = await merkleHelper.hashParent(leaf0, leaf1);
      // Level 2: pair(parent01, leaf2) -> root
      const expectedRoot = await merkleHelper.hashParent(parent01, leaf2);

      const root = await merkleHelper.computeRoot([leaf0, leaf1, leaf2]);
      expect(root).to.equal(expectedRoot);
    });

    it("computes root for 5 leaves with multiple odd-leaf promotions", async function () {
      const leaves = [
        ethers.keccak256(ethers.toUtf8Bytes("leaf-0")),
        ethers.keccak256(ethers.toUtf8Bytes("leaf-1")),
        ethers.keccak256(ethers.toUtf8Bytes("leaf-2")),
        ethers.keccak256(ethers.toUtf8Bytes("leaf-3")),
        ethers.keccak256(ethers.toUtf8Bytes("leaf-4")),
      ];

      // Level 1: p01 = pair(0,1), p23 = pair(2,3), leaf4 promoted
      const p01 = await merkleHelper.hashParent(leaves[0], leaves[1]);
      const p23 = await merkleHelper.hashParent(leaves[2], leaves[3]);
      const p4 = leaves[4];

      // Level 2: p01_23 = pair(p01, p23), p4 promoted
      const p01_23 = await merkleHelper.hashParent(p01, p23);

      // Level 3: root = pair(p01_23, p4)
      const expectedRoot = await merkleHelper.hashParent(p01_23, p4);

      const root = await merkleHelper.computeRoot(leaves);
      expect(root).to.equal(expectedRoot);
    });
  });

  describe("Proof Verification & Tamper Resistance", function () {
    it("successfully verifies valid proof for a leaf in a 3-leaf tree", async function () {
      const leaf0 = ethers.keccak256(ethers.toUtf8Bytes("leaf-0"));
      const leaf1 = ethers.keccak256(ethers.toUtf8Bytes("leaf-1"));
      const leaf2 = ethers.keccak256(ethers.toUtf8Bytes("leaf-2"));

      const root = await merkleHelper.computeRoot([leaf0, leaf1, leaf2]);

      // Proof for leaf0 is [leaf1, leaf2]
      const proofForLeaf0 = [leaf1, leaf2];
      const isValid = await merkleHelper.verifyProof(proofForLeaf0, root, leaf0);
      expect(isValid).to.be.true;

      // Proof for leaf2 is [parent01]
      const parent01 = await merkleHelper.hashParent(leaf0, leaf1);
      const proofForLeaf2 = [parent01];
      const isValidLeaf2 = await merkleHelper.verifyProof(proofForLeaf2, root, leaf2);
      expect(isValidLeaf2).to.be.true;
    });

    it("rejects proof with altered sibling hash (malformed proof)", async function () {
      const leaf0 = ethers.keccak256(ethers.toUtf8Bytes("leaf-0"));
      const leaf1 = ethers.keccak256(ethers.toUtf8Bytes("leaf-1"));
      const leaf2 = ethers.keccak256(ethers.toUtf8Bytes("leaf-2"));

      const root = await merkleHelper.computeRoot([leaf0, leaf1, leaf2]);

      const forgedSibling = ethers.keccak256(ethers.toUtf8Bytes("forged-sibling"));
      const forgedProof = [forgedSibling, leaf2];

      const isValid = await merkleHelper.verifyProof(forgedProof, root, leaf0);
      expect(isValid).to.be.false;
    });

    it("rejects proof when target root does not match", async function () {
      const leaf0 = ethers.keccak256(ethers.toUtf8Bytes("leaf-0"));
      const leaf1 = ethers.keccak256(ethers.toUtf8Bytes("leaf-1"));

      const fakeRoot = ethers.keccak256(ethers.toUtf8Bytes("fake-root"));
      const isValid = await merkleHelper.verifyProof([leaf1], fakeRoot, leaf0);
      expect(isValid).to.be.false;
    });
  });
});
