import { expect } from "chai";
import { ethers } from "hardhat";
import { IssuerRegistry } from "../typechain-types";
import { SignerWithAddress } from "@nomicfoundation/hardhat-ethers/signers";

describe("IssuerRegistry Contract", function () {
  let issuerRegistry: IssuerRegistry;
  let admin: SignerWithAddress;
  let issuer1: SignerWithAddress;
  let issuer2: SignerWithAddress;
  let newSigner: SignerWithAddress;
  let stranger: SignerWithAddress;

  const issuerId1 = ethers.keccak256(ethers.toUtf8Bytes("did:web:university-a.edu"));
  const issuerId2 = ethers.keccak256(ethers.toUtf8Bytes("did:web:university-b.edu"));
  const metadataUri1 = "ipfs://QmUniversityAMetadata";

  beforeEach(async function () {
    [admin, issuer1, issuer2, newSigner, stranger] = await ethers.getSigners();

    const IssuerRegistryFactory = await ethers.getContractFactory("IssuerRegistry");
    issuerRegistry = (await IssuerRegistryFactory.deploy(admin.address)) as IssuerRegistry;
    await issuerRegistry.waitForDeployment();
  });

  describe("Governance Onboarding & Guardrails", function () {
    it("allows governance admin to register an active issuer", async function () {
      await expect(issuerRegistry.connect(admin).registerIssuer(issuerId1, issuer1.address, metadataUri1))
        .to.emit(issuerRegistry, "IssuerRegistered")
        .withArgs(issuerId1, issuer1.address, metadataUri1);

      const record = await issuerRegistry.getIssuer(issuerId1);
      expect(record.issuerId).to.equal(issuerId1);
      expect(record.signingAddress).to.equal(issuer1.address);
      expect(record.status).to.equal(1); // IssuerStatus.Active

      expect(await issuerRegistry.isIssuerActive(issuerId1)).to.be.true;

      const [isAuthorized, resolvedId] = await issuerRegistry.getIssuerBySigningAddress(issuer1.address);
      expect(isAuthorized).to.be.true;
      expect(resolvedId).to.equal(issuerId1);
    });

    it("reverts registration when caller is not governance admin", async function () {
      await expect(
        issuerRegistry.connect(stranger).registerIssuer(issuerId1, issuer1.address, metadataUri1)
      ).to.be.revertedWithCustomError(issuerRegistry, "NotGovernanceAdmin");
    });

    it("reverts registration with address(0)", async function () {
      await expect(
        issuerRegistry.connect(admin).registerIssuer(issuerId1, ethers.ZeroAddress, metadataUri1)
      ).to.be.revertedWithCustomError(issuerRegistry, "InvalidZeroAddress");
    });

    it("reverts registration of duplicate issuer ID", async function () {
      await issuerRegistry.connect(admin).registerIssuer(issuerId1, issuer1.address, metadataUri1);

      await expect(
        issuerRegistry.connect(admin).registerIssuer(issuerId1, newSigner.address, "ipfs://new")
      ).to.be.revertedWithCustomError(issuerRegistry, "IssuerAlreadyRegistered");
    });

    it("reverts registration if signing address is already assigned to another issuer", async function () {
      await issuerRegistry.connect(admin).registerIssuer(issuerId1, issuer1.address, metadataUri1);

      await expect(
        issuerRegistry.connect(admin).registerIssuer(issuerId2, issuer1.address, "ipfs://uni-b")
      ).to.be.revertedWithCustomError(issuerRegistry, "AddressAlreadyAssigned");
    });

    it("reverts deployment with zero admin address", async function () {
      const IssuerRegistryFactory = await ethers.getContractFactory("IssuerRegistry");
      await expect(IssuerRegistryFactory.deploy(ethers.ZeroAddress)).to.be.revertedWithCustomError(
        issuerRegistry,
        "OwnableInvalidOwner"
      );
    });
  });

  describe("Issuer Status Lifecycle Management", function () {
    beforeEach(async function () {
      await issuerRegistry.connect(admin).registerIssuer(issuerId1, issuer1.address, metadataUri1);
    });

    it("allows governance to suspend and reactivate an issuer", async function () {
      await expect(issuerRegistry.connect(admin).setIssuerStatus(issuerId1, 2)) // Suspended
        .to.emit(issuerRegistry, "IssuerStatusUpdated")
        .withArgs(issuerId1, 1, 2);

      expect(await issuerRegistry.isIssuerActive(issuerId1)).to.be.false;

      const [isAuthorized] = await issuerRegistry.getIssuerBySigningAddress(issuer1.address);
      expect(isAuthorized).to.be.false;

      // Reactivate
      await issuerRegistry.connect(admin).setIssuerStatus(issuerId1, 1); // Active
      expect(await issuerRegistry.isIssuerActive(issuerId1)).to.be.true;
    });

    it("allows governance to permanently revoke an issuer", async function () {
      await expect(issuerRegistry.connect(admin).setIssuerStatus(issuerId1, 3)) // Revoked
        .to.emit(issuerRegistry, "IssuerStatusUpdated")
        .withArgs(issuerId1, 1, 3);

      expect(await issuerRegistry.isIssuerActive(issuerId1)).to.be.false;
      const [isAuthorized] = await issuerRegistry.getIssuerBySigningAddress(issuer1.address);
      expect(isAuthorized).to.be.false;
    });

    it("reverts status update for nonexistent issuer", async function () {
      const randomId = ethers.keccak256(ethers.toUtf8Bytes("random"));
      await expect(
        issuerRegistry.connect(admin).setIssuerStatus(randomId, 2)
      ).to.be.revertedWithCustomError(issuerRegistry, "IssuerNotFound");
    });
  });

  describe("2-Step Self-Service Key Rotation", function () {
    beforeEach(async function () {
      await issuerRegistry.connect(admin).registerIssuer(issuerId1, issuer1.address, metadataUri1);
    });

    it("executes valid 2-step key rotation and updates bidirectional mappings", async function () {
      await expect(issuerRegistry.connect(issuer1).proposeSigningAddress(newSigner.address))
        .to.emit(issuerRegistry, "SigningKeyRotationProposed")
        .withArgs(issuerId1, issuer1.address, newSigner.address);

      let record = await issuerRegistry.getIssuer(issuerId1);
      expect(record.pendingSigningAddress).to.equal(newSigner.address);

      // New signer accepts
      await expect(issuerRegistry.connect(newSigner).acceptSigningAddress())
        .to.emit(issuerRegistry, "SigningKeyRotated")
        .withArgs(issuerId1, issuer1.address, newSigner.address);

      record = await issuerRegistry.getIssuer(issuerId1);
      expect(record.signingAddress).to.equal(newSigner.address);
      expect(record.pendingSigningAddress).to.equal(ethers.ZeroAddress);

      // Old address is no longer authorized
      const [oldAuth] = await issuerRegistry.getIssuerBySigningAddress(issuer1.address);
      expect(oldAuth).to.be.false;

      // New address is now authorized
      const [newAuth, resolvedId] = await issuerRegistry.getIssuerBySigningAddress(newSigner.address);
      expect(newAuth).to.be.true;
      expect(resolvedId).to.equal(issuerId1);
    });

    it("reverts if unauthorized caller attempts to accept pending rotation", async function () {
      await issuerRegistry.connect(issuer1).proposeSigningAddress(newSigner.address);

      await expect(
        issuerRegistry.connect(stranger).acceptSigningAddress()
      ).to.be.revertedWithCustomError(issuerRegistry, "NotPendingSigner");
    });

    it("reverts if proposing address(0) or already assigned address or same address", async function () {
      await issuerRegistry.connect(admin).registerIssuer(issuerId2, issuer2.address, "ipfs://b");

      await expect(
        issuerRegistry.connect(issuer1).proposeSigningAddress(ethers.ZeroAddress)
      ).to.be.revertedWithCustomError(issuerRegistry, "InvalidZeroAddress");

      await expect(
        issuerRegistry.connect(issuer1).proposeSigningAddress(issuer2.address)
      ).to.be.revertedWithCustomError(issuerRegistry, "AddressAlreadyAssigned");

      await expect(
        issuerRegistry.connect(issuer1).proposeSigningAddress(issuer1.address)
      ).to.be.revertedWithCustomError(issuerRegistry, "SameAddressReassignment");
    });

    it("reverts proposal if issuer is suspended", async function () {
      await issuerRegistry.connect(admin).setIssuerStatus(issuerId1, 2); // Suspend

      await expect(
        issuerRegistry.connect(issuer1).proposeSigningAddress(newSigner.address)
      ).to.be.revertedWithCustomError(issuerRegistry, "NotAuthorizedIssuer");
    });
  });

  describe("Emergency Admin Key Rotation", function () {
    beforeEach(async function () {
      await issuerRegistry.connect(admin).registerIssuer(issuerId1, issuer1.address, metadataUri1);
    });

    it("allows governance admin to emergency rotate signing address in one step", async function () {
      await expect(
        issuerRegistry.connect(admin).emergencyRotateSigningAddress(issuerId1, newSigner.address)
      )
        .to.emit(issuerRegistry, "SigningKeyRotated")
        .withArgs(issuerId1, issuer1.address, newSigner.address);

      const record = await issuerRegistry.getIssuer(issuerId1);
      expect(record.signingAddress).to.equal(newSigner.address);

      const [newAuth] = await issuerRegistry.getIssuerBySigningAddress(newSigner.address);
      expect(newAuth).to.be.true;

      const [oldAuth] = await issuerRegistry.getIssuerBySigningAddress(issuer1.address);
      expect(oldAuth).to.be.false;
    });

    it("reverts emergency rotation to address(0) or already assigned address", async function () {
      await expect(
        issuerRegistry.connect(admin).emergencyRotateSigningAddress(issuerId1, ethers.ZeroAddress)
      ).to.be.revertedWithCustomError(issuerRegistry, "InvalidZeroAddress");

      await expect(
        issuerRegistry.connect(admin).emergencyRotateSigningAddress(issuerId1, issuer1.address)
      ).to.be.revertedWithCustomError(issuerRegistry, "SameAddressReassignment");
    });
  });
});
