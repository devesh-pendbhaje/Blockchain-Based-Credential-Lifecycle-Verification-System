import { expect } from "chai";
import { ethers } from "hardhat";
import { time } from "@nomicfoundation/hardhat-network-helpers";
import { CredentialRegistry, IssuerRegistry } from "../typechain-types";
import { SignerWithAddress } from "@nomicfoundation/hardhat-ethers/signers";

describe("CredentialRegistry Contract", function () {
  let issuerRegistry: IssuerRegistry;
  let credentialRegistry: CredentialRegistry;
  let admin: SignerWithAddress;
  let issuer1: SignerWithAddress;
  let issuer2: SignerWithAddress;
  let stranger: SignerWithAddress;
  let issuer1Rotated: SignerWithAddress;

  const issuerId1 = ethers.keccak256(ethers.toUtf8Bytes("did:web:university-a.edu"));
  const issuerId2 = ethers.keccak256(ethers.toUtf8Bytes("did:web:university-b.edu"));

  const credentialId = ethers.keccak256(ethers.toUtf8Bytes("DIPLOMA-2026-0042"));
  const documentDigest1 = ethers.keccak256(ethers.toUtf8Bytes("pdf-certificate-v1"));
  const metadataDigest1 = ethers.keccak256(ethers.toUtf8Bytes("canonical-metadata-json-v1"));
  const merkleRoot1 = ethers.keccak256(ethers.toUtf8Bytes("merkleRoot-salted-claims-v1"));

  const documentDigest2 = ethers.keccak256(ethers.toUtf8Bytes("pdf-certificate-v2"));
  const metadataDigest2 = ethers.keccak256(ethers.toUtf8Bytes("canonical-metadata-json-v2"));
  const merkleRoot2 = ethers.keccak256(ethers.toUtf8Bytes("merkleRoot-salted-claims-v2"));

  beforeEach(async function () {
    [admin, issuer1, issuer2, stranger, issuer1Rotated] = await ethers.getSigners();

    const IssuerRegistryFactory = await ethers.getContractFactory("IssuerRegistry");
    issuerRegistry = (await IssuerRegistryFactory.deploy(admin.address)) as IssuerRegistry;
    await issuerRegistry.waitForDeployment();

    const CredentialRegistryFactory = await ethers.getContractFactory("CredentialRegistry");
    credentialRegistry = (await CredentialRegistryFactory.deploy(
      await issuerRegistry.getAddress()
    )) as CredentialRegistry;
    await credentialRegistry.waitForDeployment();

    // Register active issuer1
    await issuerRegistry.connect(admin).registerIssuer(issuerId1, issuer1.address, "ipfs://uni-a");
  });

  describe("6-Input Composite Fingerprint Calculation", function () {
    it("computes exact composite fingerprint matching the 6-input formula", async function () {
      const version = 1;
      const expectedFingerprint = ethers.keccak256(
        ethers.AbiCoder.defaultAbiCoder().encode(
          ["bytes32", "bytes32", "bytes32", "bytes32", "bytes32", "uint32"],
          [documentDigest1, metadataDigest1, merkleRoot1, issuerId1, credentialId, version]
        )
      );

      const computed = await credentialRegistry.computeFingerprint(
        documentDigest1,
        metadataDigest1,
        merkleRoot1,
        issuerId1,
        credentialId,
        version
      );

      expect(computed).to.equal(expectedFingerprint);
    });

    it("enforces component sensitivity: modifying any single component alters fingerprint", async function () {
      const baseFingerprint = await credentialRegistry.computeFingerprint(
        documentDigest1,
        metadataDigest1,
        merkleRoot1,
        issuerId1,
        credentialId,
        1
      );

      const altered = ethers.keccak256(ethers.toUtf8Bytes("altered-value"));

      // 1. Alter documentDigest
      expect(
        await credentialRegistry.computeFingerprint(
          altered,
          metadataDigest1,
          merkleRoot1,
          issuerId1,
          credentialId,
          1
        )
      ).to.not.equal(baseFingerprint);

      // 2. Alter metadataDigest
      expect(
        await credentialRegistry.computeFingerprint(
          documentDigest1,
          altered,
          merkleRoot1,
          issuerId1,
          credentialId,
          1
        )
      ).to.not.equal(baseFingerprint);

      // 3. Alter merkleRoot
      expect(
        await credentialRegistry.computeFingerprint(
          documentDigest1,
          metadataDigest1,
          altered,
          issuerId1,
          credentialId,
          1
        )
      ).to.not.equal(baseFingerprint);

      // 4. Alter issuerId
      expect(
        await credentialRegistry.computeFingerprint(
          documentDigest1,
          metadataDigest1,
          merkleRoot1,
          altered,
          credentialId,
          1
        )
      ).to.not.equal(baseFingerprint);

      // 5. Alter credentialId
      expect(
        await credentialRegistry.computeFingerprint(
          documentDigest1,
          metadataDigest1,
          merkleRoot1,
          issuerId1,
          altered,
          1
        )
      ).to.not.equal(baseFingerprint);

      // 6. Alter version
      expect(
        await credentialRegistry.computeFingerprint(
          documentDigest1,
          metadataDigest1,
          merkleRoot1,
          issuerId1,
          credentialId,
          2
        )
      ).to.not.equal(baseFingerprint);
    });
  });

  describe("Issuance & Version Monotonicity Guardrails", function () {
    it("allows authorized issuer to issue version 1 credential", async function () {
      const expiresAt = (await time.latest()) + 3600; // 1 hour from now

      const expectedFingerprint = await credentialRegistry.computeFingerprint(
        documentDigest1,
        metadataDigest1,
        merkleRoot1,
        issuerId1,
        credentialId,
        1
      );

      await expect(
        credentialRegistry.connect(issuer1).issueCredential(
          credentialId,
          documentDigest1,
          metadataDigest1,
          merkleRoot1,
          1,
          expiresAt
        )
      )
        .to.emit(credentialRegistry, "CredentialIssued")
        .withArgs(
          expectedFingerprint,
          credentialId,
          issuerId1,
          documentDigest1,
          metadataDigest1,
          merkleRoot1,
          1,
          expiresAt
        );

      const record = await credentialRegistry.getCredential(expectedFingerprint);
      expect(record.status).to.equal(1); // StoredStatus.Active
      expect(record.version).to.equal(1);
      expect(record.issuerId).to.equal(issuerId1);
      expect(record.documentDigest).to.equal(documentDigest1);
      expect(record.metadataDigest).to.equal(metadataDigest1);
      expect(record.merkleRoot).to.equal(merkleRoot1);
      expect(record.expiresAt).to.equal(expiresAt);

      expect(await credentialRegistry.getLatestVersion(issuerId1, credentialId)).to.equal(1);
    });

    it("reverts initial issuance if version is not 1", async function () {
      await expect(
        credentialRegistry.connect(issuer1).issueCredential(
          credentialId,
          documentDigest1,
          metadataDigest1,
          merkleRoot1,
          2, // Invalid initial version
          0
        )
      ).to.be.revertedWithCustomError(credentialRegistry, "InvalidCredentialVersion");
    });

    it("reverts issuance from unauthorized caller", async function () {
      await expect(
        credentialRegistry.connect(stranger).issueCredential(
          credentialId,
          documentDigest1,
          metadataDigest1,
          merkleRoot1,
          1,
          0
        )
      ).to.be.revertedWithCustomError(credentialRegistry, "CallerNotAuthorizedIssuer");
    });

    it("reverts issuance with zero documentDigest, zero metadataDigest, or zero merkleRoot", async function () {
      await expect(
        credentialRegistry.connect(issuer1).issueCredential(
          credentialId,
          ethers.ZeroHash,
          metadataDigest1,
          merkleRoot1,
          1,
          0
        )
      ).to.be.revertedWithCustomError(credentialRegistry, "ZeroDigestNotAllowed");

      await expect(
        credentialRegistry.connect(issuer1).issueCredential(
          credentialId,
          documentDigest1,
          ethers.ZeroHash,
          merkleRoot1,
          1,
          0
        )
      ).to.be.revertedWithCustomError(credentialRegistry, "ZeroDigestNotAllowed");

      await expect(
        credentialRegistry.connect(issuer1).issueCredential(
          credentialId,
          documentDigest1,
          metadataDigest1,
          ethers.ZeroHash,
          1,
          0
        )
      ).to.be.revertedWithCustomError(credentialRegistry, "ZeroDigestNotAllowed");
    });

    it("reverts issuance with zero credentialId", async function () {
      await expect(
        credentialRegistry.connect(issuer1).issueCredential(
          ethers.ZeroHash,
          documentDigest1,
          metadataDigest1,
          merkleRoot1,
          1,
          0
        )
      ).to.be.revertedWithCustomError(credentialRegistry, "ZeroIdentifierNotAllowed");
    });

    it("reverts issuance with past expiration timestamp", async function () {
      const pastTime = (await time.latest()) - 100;
      await expect(
        credentialRegistry.connect(issuer1).issueCredential(
          credentialId,
          documentDigest1,
          metadataDigest1,
          merkleRoot1,
          1,
          pastTime
        )
      ).to.be.revertedWithCustomError(credentialRegistry, "InvalidExpirationTime");
    });

    it("reverts duplicate issuance with identical fingerprint", async function () {
      await credentialRegistry.connect(issuer1).issueCredential(
        credentialId,
        documentDigest1,
        metadataDigest1,
        merkleRoot1,
        1,
        0
      );

      // Re-issuing exact same credential version reverts with InvalidCredentialVersion (must be version 2)
      await expect(
        credentialRegistry.connect(issuer1).issueCredential(
          credentialId,
          documentDigest1,
          metadataDigest1,
          merkleRoot1,
          1,
          0
        )
      ).to.be.revertedWithCustomError(credentialRegistry, "InvalidCredentialVersion");
    });
  });

  describe("Lifecycle Transitions & Reason Code Validation", function () {
    let fingerprint1: string;

    beforeEach(async function () {
      fingerprint1 = await credentialRegistry.computeFingerprint(
        documentDigest1,
        metadataDigest1,
        merkleRoot1,
        issuerId1,
        credentialId,
        1
      );

      await credentialRegistry.connect(issuer1).issueCredential(
        credentialId,
        documentDigest1,
        metadataDigest1,
        merkleRoot1,
        1,
        0
      );
    });

    it("rejects unsupported reason codes (< 1 or > 5)", async function () {
      await expect(
        credentialRegistry.connect(issuer1).suspendCredential(fingerprint1, 0)
      ).to.be.revertedWithCustomError(credentialRegistry, "UnsupportedReasonCode");

      await expect(
        credentialRegistry.connect(issuer1).suspendCredential(fingerprint1, 6)
      ).to.be.revertedWithCustomError(credentialRegistry, "UnsupportedReasonCode");

      await expect(
        credentialRegistry.connect(issuer1).revokeCredential(fingerprint1, 0)
      ).to.be.revertedWithCustomError(credentialRegistry, "UnsupportedReasonCode");

      await expect(
        credentialRegistry.connect(issuer1).archiveCredential(fingerprint1, 99)
      ).to.be.revertedWithCustomError(credentialRegistry, "UnsupportedReasonCode");
    });

    it("allows issuer to suspend and reactivate an active credential with valid reason code", async function () {
      await expect(credentialRegistry.connect(issuer1).suspendCredential(fingerprint1, 2)) // Reason 2: Audit Hold
        .to.emit(credentialRegistry, "CredentialSuspended")
        .withArgs(fingerprint1, issuerId1, 2);

      let record = await credentialRegistry.getCredential(fingerprint1);
      expect(record.status).to.equal(2); // StoredStatus.Suspended

      // Reactivate
      await expect(credentialRegistry.connect(issuer1).reactivateCredential(fingerprint1))
        .to.emit(credentialRegistry, "CredentialReactivated")
        .withArgs(fingerprint1, issuerId1);

      record = await credentialRegistry.getCredential(fingerprint1);
      expect(record.status).to.equal(1); // StoredStatus.Active
    });

    it("allows issuer to revoke active or suspended credential permanently", async function () {
      await expect(credentialRegistry.connect(issuer1).revokeCredential(fingerprint1, 1)) // Reason 1: Misconduct
        .to.emit(credentialRegistry, "CredentialRevoked")
        .withArgs(fingerprint1, issuerId1, 1);

      const record = await credentialRegistry.getCredential(fingerprint1);
      expect(record.status).to.equal(3); // StoredStatus.Revoked

      // Attempting to reactivate a revoked credential must revert
      await expect(
        credentialRegistry.connect(issuer1).reactivateCredential(fingerprint1)
      ).to.be.revertedWithCustomError(credentialRegistry, "InvalidLifecycleTransition");

      // Attempting to re-revoke a revoked credential must revert
      await expect(
        credentialRegistry.connect(issuer1).revokeCredential(fingerprint1, 1)
      ).to.be.revertedWithCustomError(credentialRegistry, "InvalidLifecycleTransition");
    });

    it("allows issuer to supersede active credential with version 2", async function () {
      const expectedFingerprint2 = await credentialRegistry.computeFingerprint(
        documentDigest2,
        metadataDigest2,
        merkleRoot2,
        issuerId1,
        credentialId,
        2
      );

      await expect(
        credentialRegistry.connect(issuer1).supersedeCredential(
          fingerprint1,
          documentDigest2,
          metadataDigest2,
          merkleRoot2,
          0
        )
      )
        .to.emit(credentialRegistry, "CredentialSuperseded")
        .withArgs(fingerprint1, expectedFingerprint2, issuerId1)
        .and.to.emit(credentialRegistry, "CredentialIssued")
        .withArgs(
          expectedFingerprint2,
          credentialId,
          issuerId1,
          documentDigest2,
          metadataDigest2,
          merkleRoot2,
          2,
          0
        );

      const oldRecord = await credentialRegistry.getCredential(fingerprint1);
      expect(oldRecord.status).to.equal(4); // StoredStatus.Superseded
      expect(oldRecord.supersededBy).to.equal(expectedFingerprint2);

      const newRecord = await credentialRegistry.getCredential(expectedFingerprint2);
      expect(newRecord.status).to.equal(1); // StoredStatus.Active
      expect(newRecord.version).to.equal(2);

      expect(await credentialRegistry.getLatestVersion(issuerId1, credentialId)).to.equal(2);
    });

    it("reverts attempt to supersede a suspended credential directly", async function () {
      await credentialRegistry.connect(issuer1).suspendCredential(fingerprint1, 2);

      await expect(
        credentialRegistry.connect(issuer1).supersedeCredential(
          fingerprint1,
          documentDigest2,
          metadataDigest2,
          merkleRoot2,
          0
        )
      ).to.be.revertedWithCustomError(credentialRegistry, "InvalidLifecycleTransition");
    });

    it("allows issuer to archive an active or suspended credential", async function () {
      await expect(credentialRegistry.connect(issuer1).archiveCredential(fingerprint1, 5)) // Reason 5: End of Program
        .to.emit(credentialRegistry, "CredentialArchived")
        .withArgs(fingerprint1, issuerId1, 5);

      const record = await credentialRegistry.getCredential(fingerprint1);
      expect(record.status).to.equal(5); // StoredStatus.Archived

      // Attempting to reactivate an archived credential reverts
      await expect(
        credentialRegistry.connect(issuer1).reactivateCredential(fingerprint1)
      ).to.be.revertedWithCustomError(credentialRegistry, "InvalidLifecycleTransition");
    });

    it("reverts if unauthorized third-party attempts lifecycle mutation", async function () {
      await issuerRegistry.connect(admin).registerIssuer(issuerId2, issuer2.address, "ipfs://uni-b");

      await expect(
        credentialRegistry.connect(issuer2).suspendCredential(fingerprint1, 2)
      ).to.be.revertedWithCustomError(credentialRegistry, "CallerNotCredentialIssuer");

      await expect(
        credentialRegistry.connect(stranger).revokeCredential(fingerprint1, 1)
      ).to.be.revertedWithCustomError(credentialRegistry, "CallerNotAuthorizedIssuer");
    });
  });

  describe("Comprehensive Verification Logic & Expiry Boundaries", function () {
    let fingerprintValid: string;
    let expiresAt: number;

    beforeEach(async function () {
      expiresAt = (await time.latest()) + 1000;
      fingerprintValid = await credentialRegistry.computeFingerprint(
        documentDigest1,
        metadataDigest1,
        merkleRoot1,
        issuerId1,
        credentialId,
        1
      );

      await credentialRegistry.connect(issuer1).issueCredential(
        credentialId,
        documentDigest1,
        metadataDigest1,
        merkleRoot1,
        1,
        expiresAt
      );
    });

    it("returns Valid (code = 0) for active, unexpired credential with accredited issuer", async function () {
      const result = await credentialRegistry.verifyCredential(
        fingerprintValid,
        documentDigest1,
        metadataDigest1,
        merkleRoot1
      );

      expect(result.isValid).to.be.true;
      expect(result.code).to.equal(0); // VerificationCode.Valid
      expect(result.storedStatus).to.equal(1); // Active
      expect(result.isIssuerActive).to.be.true;
    });

    it("returns HashMismatch (code = 2) when documentDigest, metadataDigest, or merkleRoot is altered", async function () {
      const forged = ethers.keccak256(ethers.toUtf8Bytes("forged"));

      // Alter documentDigest
      let result = await credentialRegistry.verifyCredential(
        fingerprintValid,
        forged,
        metadataDigest1,
        merkleRoot1
      );
      expect(result.isValid).to.be.false;
      expect(result.code).to.equal(2);

      // Alter metadataDigest
      result = await credentialRegistry.verifyCredential(
        fingerprintValid,
        documentDigest1,
        forged,
        merkleRoot1
      );
      expect(result.isValid).to.be.false;
      expect(result.code).to.equal(2);

      // Alter merkleRoot
      result = await credentialRegistry.verifyCredential(
        fingerprintValid,
        documentDigest1,
        metadataDigest1,
        forged
      );
      expect(result.isValid).to.be.false;
      expect(result.code).to.equal(2);
    });

    it("returns NotFound (code = 1) for unregistered fingerprint", async function () {
      const randomFingerprint = ethers.keccak256(ethers.toUtf8Bytes("random-unregistered"));
      const result = await credentialRegistry.verifyCredential(
        randomFingerprint,
        documentDigest1,
        metadataDigest1,
        merkleRoot1
      );

      expect(result.isValid).to.be.false;
      expect(result.code).to.equal(1); // VerificationCode.NotFound
    });

    it("returns Expired (code = 4) dynamically when block timestamp exceeds expiration", async function () {
      await time.increase(1005); // Move past expiresAt

      const result = await credentialRegistry.verifyCredential(
        fingerprintValid,
        documentDigest1,
        metadataDigest1,
        merkleRoot1
      );

      expect(result.isValid).to.be.false;
      expect(result.code).to.equal(4); // VerificationCode.Expired
    });

    it("returns InvalidStoredStatus (code = 3) when credential is suspended or revoked", async function () {
      await credentialRegistry.connect(issuer1).suspendCredential(fingerprintValid, 2);

      let result = await credentialRegistry.verifyCredential(
        fingerprintValid,
        documentDigest1,
        metadataDigest1,
        merkleRoot1
      );

      expect(result.isValid).to.be.false;
      expect(result.code).to.equal(3); // VerificationCode.InvalidStoredStatus
      expect(result.storedStatus).to.equal(2); // Suspended

      await credentialRegistry.connect(issuer1).revokeCredential(fingerprintValid, 1);

      result = await credentialRegistry.verifyCredential(
        fingerprintValid,
        documentDigest1,
        metadataDigest1,
        merkleRoot1
      );

      expect(result.isValid).to.be.false;
      expect(result.code).to.equal(3); // VerificationCode.InvalidStoredStatus
      expect(result.storedStatus).to.equal(3); // Revoked
    });

    it("returns IssuerNotActive (code = 5) when issuing institution is suspended in IssuerRegistry", async function () {
      await issuerRegistry.connect(admin).setIssuerStatus(issuerId1, 2); // Suspend university

      const result = await credentialRegistry.verifyCredential(
        fingerprintValid,
        documentDigest1,
        metadataDigest1,
        merkleRoot1
      );

      expect(result.isValid).to.be.false;
      expect(result.code).to.equal(5); // VerificationCode.IssuerNotActive
      expect(result.isIssuerActive).to.be.false;
    });
  });

  describe("Credential History Queries & Multi-Version Traversal", function () {
    let fpV1: string;
    let fpV2: string;

    beforeEach(async function () {
      fpV1 = await credentialRegistry.computeFingerprint(
        documentDigest1,
        metadataDigest1,
        merkleRoot1,
        issuerId1,
        credentialId,
        1
      );

      await credentialRegistry.connect(issuer1).issueCredential(
        credentialId,
        documentDigest1,
        metadataDigest1,
        merkleRoot1,
        1,
        0
      );

      await credentialRegistry.connect(issuer1).supersedeCredential(
        fpV1,
        documentDigest2,
        metadataDigest2,
        merkleRoot2,
        0
      );

      fpV2 = await credentialRegistry.computeFingerprint(
        documentDigest2,
        metadataDigest2,
        merkleRoot2,
        issuerId1,
        credentialId,
        2
      );
    });

    it("retrieves historical version fingerprints accurately", async function () {
      expect(await credentialRegistry.getVersionFingerprint(issuerId1, credentialId, 1)).to.equal(fpV1);
      expect(await credentialRegistry.getVersionFingerprint(issuerId1, credentialId, 2)).to.equal(fpV2);
      expect(await credentialRegistry.getVersionFingerprint(issuerId1, credentialId, 3)).to.equal(ethers.ZeroHash);
    });

    it("retrieves full historical CredentialRecords across versions", async function () {
      const recV1 = await credentialRegistry.getCredentialByVersion(issuerId1, credentialId, 1);
      expect(recV1.version).to.equal(1);
      expect(recV1.status).to.equal(4); // Superseded
      expect(recV1.supersededBy).to.equal(fpV2);

      const recV2 = await credentialRegistry.getCredentialByVersion(issuerId1, credentialId, 2);
      expect(recV2.version).to.equal(2);
      expect(recV2.status).to.equal(1); // Active
      expect(recV2.supersededBy).to.equal(ethers.ZeroHash);
    });

    it("reverts getCredentialByVersion for nonexistent version", async function () {
      await expect(
        credentialRegistry.getCredentialByVersion(issuerId1, credentialId, 99)
      ).to.be.revertedWithCustomError(credentialRegistry, "CredentialNotFound");
    });
  });

  describe("Historical Key Rotation Invariance & Provenance Permanence", function () {
    let fpIssued: string;

    beforeEach(async function () {
      fpIssued = await credentialRegistry.computeFingerprint(
        documentDigest1,
        metadataDigest1,
        merkleRoot1,
        issuerId1,
        credentialId,
        1
      );

      await credentialRegistry.connect(issuer1).issueCredential(
        credentialId,
        documentDigest1,
        metadataDigest1,
        merkleRoot1,
        1,
        0
      );
    });

    it("preserves credential validity and provenance after issuer signing-key rotation", async function () {
      // 1. Rotate signing key from issuer1 to issuer1Rotated
      await issuerRegistry.connect(admin).emergencyRotateSigningAddress(issuerId1, issuer1Rotated.address);

      // 2. Stored record retains issuerId1 permanently
      const rec = await credentialRegistry.getCredential(fpIssued);
      expect(rec.issuerId).to.equal(issuerId1);

      // 3. Verification remains Valid (code = 0) because issuer institution is active
      const result = await credentialRegistry.verifyCredential(
        fpIssued,
        documentDigest1,
        metadataDigest1,
        merkleRoot1
      );
      expect(result.isValid).to.be.true;
      expect(result.code).to.equal(0);
      expect(result.issuerId).to.equal(issuerId1);

      // 4. Old signing address issuer1 cannot mutate or issue
      await expect(
        credentialRegistry.connect(issuer1).suspendCredential(fpIssued, 2)
      ).to.be.revertedWithCustomError(credentialRegistry, "CallerNotAuthorizedIssuer");

      // 5. New signing address issuer1Rotated can administer the credential
      await expect(
        credentialRegistry.connect(issuer1Rotated).suspendCredential(fpIssued, 2)
      )
        .to.emit(credentialRegistry, "CredentialSuspended")
        .withArgs(fpIssued, issuerId1, 2);

      const updatedRec = await credentialRegistry.getCredential(fpIssued);
      expect(updatedRec.status).to.equal(2); // Suspended
    });
  });
});
