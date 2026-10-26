// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "./interfaces/ICredentialRegistry.sol";
import "./interfaces/IIssuerRegistry.sol";

/**
 * @title CredentialRegistry
 * @notice Anchors 6-input composite credential fingerprints, enforces version monotonicity,
 *         executes lifecycle state transitions, validates reason codes, and performs comprehensive verification.
 */
contract CredentialRegistry is ICredentialRegistry {
    IIssuerRegistry public immutable issuerRegistry;

    mapping(bytes32 => CredentialRecord) private _credentials;
    mapping(bytes32 => mapping(bytes32 => uint32)) private _latestVersions;
    mapping(bytes32 => mapping(bytes32 => mapping(uint32 => bytes32))) private _versionFingerprints;

    constructor(address issuerRegistryAddress) {
        if (issuerRegistryAddress == address(0)) {
            revert ZeroDigestNotAllowed();
        }
        issuerRegistry = IIssuerRegistry(issuerRegistryAddress);
    }

    /**
     * @dev Validates that a lifecycle modification reason code is supported (1 through 5).
     */
    function _validateReasonCode(uint8 reasonCode) internal pure {
        if (reasonCode < 1 || reasonCode > 5) {
            revert UnsupportedReasonCode(reasonCode);
        }
    }

    /**
     * @notice Pure deterministic calculation of the 6-input composite credential fingerprint.
     */
    function computeFingerprint(
        bytes32 documentDigest,
        bytes32 metadataDigest,
        bytes32 merkleRoot,
        bytes32 issuerId,
        bytes32 credentialId,
        uint32 version
    ) public pure override returns (bytes32) {
        return keccak256(abi.encode(documentDigest, metadataDigest, merkleRoot, issuerId, credentialId, version));
    }

    /**
     * @notice Issues a new credential anchored to the caller's accredited issuer ID.
     */
    function issueCredential(
        bytes32 credentialId,
        bytes32 documentDigest,
        bytes32 metadataDigest,
        bytes32 merkleRoot,
        uint32 version,
        uint64 expiresAt
    ) external override returns (bytes32 fingerprint) {
        (bool isAuthorized, bytes32 issuerId) = issuerRegistry.getIssuerBySigningAddress(msg.sender);
        if (!isAuthorized) {
            revert CallerNotAuthorizedIssuer(msg.sender);
        }
        if (credentialId == bytes32(0)) {
            revert ZeroIdentifierNotAllowed();
        }
        if (documentDigest == bytes32(0) || metadataDigest == bytes32(0) || merkleRoot == bytes32(0)) {
            revert ZeroDigestNotAllowed();
        }
        if (expiresAt != 0 && expiresAt <= block.timestamp) {
            revert InvalidExpirationTime(expiresAt);
        }

        uint32 currentLatest = _latestVersions[issuerId][credentialId];
        if (currentLatest == 0) {
            if (version != 1) {
                revert InvalidCredentialVersion(1, version);
            }
        } else {
            if (version != currentLatest + 1) {
                revert InvalidCredentialVersion(currentLatest + 1, version);
            }
        }

        fingerprint = computeFingerprint(documentDigest, metadataDigest, merkleRoot, issuerId, credentialId, version);
        if (_credentials[fingerprint].issuedAt != 0) {
            revert CredentialAlreadyExists(fingerprint);
        }

        _latestVersions[issuerId][credentialId] = version;
        _versionFingerprints[issuerId][credentialId][version] = fingerprint;

        uint64 nowTime = uint64(block.timestamp);
        _credentials[fingerprint] = CredentialRecord({
            fingerprint: fingerprint,
            credentialId: credentialId,
            issuerId: issuerId,
            documentDigest: documentDigest,
            metadataDigest: metadataDigest,
            merkleRoot: merkleRoot,
            version: version,
            status: StoredStatus.Active,
            issuedAt: nowTime,
            expiresAt: expiresAt,
            statusUpdatedAt: nowTime,
            supersededBy: bytes32(0)
        });

        emit CredentialIssued(
            fingerprint,
            credentialId,
            issuerId,
            documentDigest,
            metadataDigest,
            merkleRoot,
            version,
            expiresAt
        );
    }

    /**
     * @notice Temporarily suspends an active credential with reason code validation.
     */
    function suspendCredential(bytes32 fingerprint, uint8 reasonCode) external override {
        _validateReasonCode(reasonCode);

        CredentialRecord storage rec = _credentials[fingerprint];
        if (rec.issuedAt == 0) {
            revert CredentialNotFound(fingerprint);
        }

        (bool isAuthorized, bytes32 callerIssuer) = issuerRegistry.getIssuerBySigningAddress(msg.sender);
        if (!isAuthorized) {
            revert CallerNotAuthorizedIssuer(msg.sender);
        }
        if (callerIssuer != rec.issuerId) {
            revert CallerNotCredentialIssuer(rec.issuerId, callerIssuer);
        }
        if (rec.status != StoredStatus.Active) {
            revert InvalidLifecycleTransition(rec.status, StoredStatus.Suspended);
        }

        rec.status = StoredStatus.Suspended;
        rec.statusUpdatedAt = uint64(block.timestamp);

        emit CredentialSuspended(fingerprint, rec.issuerId, reasonCode);
    }

    /**
     * @notice Reactivates a suspended credential back to Active status.
     */
    function reactivateCredential(bytes32 fingerprint) external override {
        CredentialRecord storage rec = _credentials[fingerprint];
        if (rec.issuedAt == 0) {
            revert CredentialNotFound(fingerprint);
        }

        (bool isAuthorized, bytes32 callerIssuer) = issuerRegistry.getIssuerBySigningAddress(msg.sender);
        if (!isAuthorized) {
            revert CallerNotAuthorizedIssuer(msg.sender);
        }
        if (callerIssuer != rec.issuerId) {
            revert CallerNotCredentialIssuer(rec.issuerId, callerIssuer);
        }
        if (rec.status != StoredStatus.Suspended) {
            revert InvalidLifecycleTransition(rec.status, StoredStatus.Active);
        }

        rec.status = StoredStatus.Active;
        rec.statusUpdatedAt = uint64(block.timestamp);

        emit CredentialReactivated(fingerprint, rec.issuerId);
    }

    /**
     * @notice Permanently revokes a credential with reason code validation. Terminal transition.
     */
    function revokeCredential(bytes32 fingerprint, uint8 reasonCode) external override {
        _validateReasonCode(reasonCode);

        CredentialRecord storage rec = _credentials[fingerprint];
        if (rec.issuedAt == 0) {
            revert CredentialNotFound(fingerprint);
        }

        (bool isAuthorized, bytes32 callerIssuer) = issuerRegistry.getIssuerBySigningAddress(msg.sender);
        if (!isAuthorized) {
            revert CallerNotAuthorizedIssuer(msg.sender);
        }
        if (callerIssuer != rec.issuerId) {
            revert CallerNotCredentialIssuer(rec.issuerId, callerIssuer);
        }
        if (rec.status == StoredStatus.Revoked) {
            revert InvalidLifecycleTransition(rec.status, StoredStatus.Revoked);
        }

        rec.status = StoredStatus.Revoked;
        rec.statusUpdatedAt = uint64(block.timestamp);

        emit CredentialRevoked(fingerprint, rec.issuerId, reasonCode);
    }

    /**
     * @notice Supersedes an active credential with a new version, automatically linking records.
     */
    function supersedeCredential(
        bytes32 oldFingerprint,
        bytes32 newDocumentDigest,
        bytes32 newMetadataDigest,
        bytes32 newMerkleRoot,
        uint64 newExpiresAt
    ) external override returns (bytes32 newFingerprint) {
        CredentialRecord storage oldRec = _credentials[oldFingerprint];
        if (oldRec.issuedAt == 0) {
            revert CredentialNotFound(oldFingerprint);
        }

        (bool isAuthorized, bytes32 callerIssuer) = issuerRegistry.getIssuerBySigningAddress(msg.sender);
        if (!isAuthorized) {
            revert CallerNotAuthorizedIssuer(msg.sender);
        }
        if (callerIssuer != oldRec.issuerId) {
            revert CallerNotCredentialIssuer(oldRec.issuerId, callerIssuer);
        }
        if (oldRec.status != StoredStatus.Active) {
            revert InvalidLifecycleTransition(oldRec.status, StoredStatus.Superseded);
        }
        if (newDocumentDigest == bytes32(0) || newMetadataDigest == bytes32(0) || newMerkleRoot == bytes32(0)) {
            revert ZeroDigestNotAllowed();
        }
        if (newExpiresAt != 0 && newExpiresAt <= block.timestamp) {
            revert InvalidExpirationTime(newExpiresAt);
        }

        if (oldRec.version == type(uint32).max) {
            revert VersionOverflowNotAllowed();
        }

        uint32 newVersion = oldRec.version + 1;
        newFingerprint = computeFingerprint(
            newDocumentDigest,
            newMetadataDigest,
            newMerkleRoot,
            oldRec.issuerId,
            oldRec.credentialId,
            newVersion
        );

        if (_credentials[newFingerprint].issuedAt != 0) {
            revert CredentialAlreadyExists(newFingerprint);
        }

        uint64 nowTime = uint64(block.timestamp);

        oldRec.status = StoredStatus.Superseded;
        oldRec.supersededBy = newFingerprint;
        oldRec.statusUpdatedAt = nowTime;

        _latestVersions[oldRec.issuerId][oldRec.credentialId] = newVersion;
        _versionFingerprints[oldRec.issuerId][oldRec.credentialId][newVersion] = newFingerprint;

        _credentials[newFingerprint] = CredentialRecord({
            fingerprint: newFingerprint,
            credentialId: oldRec.credentialId,
            issuerId: oldRec.issuerId,
            documentDigest: newDocumentDigest,
            metadataDigest: newMetadataDigest,
            merkleRoot: newMerkleRoot,
            version: newVersion,
            status: StoredStatus.Active,
            issuedAt: nowTime,
            expiresAt: newExpiresAt,
            statusUpdatedAt: nowTime,
            supersededBy: bytes32(0)
        });

        emit CredentialSuperseded(oldFingerprint, newFingerprint, oldRec.issuerId);
        emit CredentialIssued(
            newFingerprint,
            oldRec.credentialId,
            oldRec.issuerId,
            newDocumentDigest,
            newMetadataDigest,
            newMerkleRoot,
            newVersion,
            newExpiresAt
        );
    }

    /**
     * @notice Administratively archives an active or suspended credential with reason code validation.
     */
    function archiveCredential(bytes32 fingerprint, uint8 reasonCode) external override {
        _validateReasonCode(reasonCode);

        CredentialRecord storage rec = _credentials[fingerprint];
        if (rec.issuedAt == 0) {
            revert CredentialNotFound(fingerprint);
        }

        (bool isAuthorized, bytes32 callerIssuer) = issuerRegistry.getIssuerBySigningAddress(msg.sender);
        if (!isAuthorized) {
            revert CallerNotAuthorizedIssuer(msg.sender);
        }
        if (callerIssuer != rec.issuerId) {
            revert CallerNotCredentialIssuer(rec.issuerId, callerIssuer);
        }
        if (rec.status != StoredStatus.Active && rec.status != StoredStatus.Suspended) {
            revert InvalidLifecycleTransition(rec.status, StoredStatus.Archived);
        }

        rec.status = StoredStatus.Archived;
        rec.statusUpdatedAt = uint64(block.timestamp);

        emit CredentialArchived(fingerprint, rec.issuerId, reasonCode);
    }

    /**
     * @notice Returns the full stored record for a credential fingerprint.
     */
    function getCredential(bytes32 fingerprint) external view override returns (CredentialRecord memory) {
        CredentialRecord memory rec = _credentials[fingerprint];
        if (rec.issuedAt == 0) {
            revert CredentialNotFound(fingerprint);
        }
        return rec;
    }

    /**
     * @notice Returns the latest version counter recorded for a credential ID.
     */
    function getLatestVersion(bytes32 issuerId, bytes32 credentialId) external view override returns (uint32) {
        return _latestVersions[issuerId][credentialId];
    }

    /**
     * @notice Returns the credential fingerprint for a specific historical version.
     */
    function getVersionFingerprint(bytes32 issuerId, bytes32 credentialId, uint32 version) external view override returns (bytes32) {
        return _versionFingerprints[issuerId][credentialId][version];
    }

    /**
     * @notice Returns the full CredentialRecord for a specific historical version.
     */
    function getCredentialByVersion(bytes32 issuerId, bytes32 credentialId, uint32 version) external view override returns (CredentialRecord memory) {
        bytes32 fp = _versionFingerprints[issuerId][credentialId][version];
        if (fp == bytes32(0)) {
            revert CredentialNotFound(fp);
        }
        return _credentials[fp];
    }

    /**
     * @notice Comprehensive verification resolving stored status, dynamic expiry, 3-way digest integrity, and issuer standing.
     */
    function verifyCredential(
        bytes32 fingerprint,
        bytes32 claimedDocumentDigest,
        bytes32 claimedMetadataDigest,
        bytes32 claimedMerkleRoot
    ) external view override returns (VerificationResult memory) {
        CredentialRecord memory rec = _credentials[fingerprint];
        if (rec.issuedAt == 0) {
            return VerificationResult({
                isValid: false,
                code: VerificationCode.NotFound,
                storedStatus: StoredStatus.None,
                issuerId: bytes32(0),
                isIssuerActive: false,
                expiresAt: 0
            });
        }

        bool issuerActive = issuerRegistry.isIssuerActive(rec.issuerId);

        if (
            rec.documentDigest != claimedDocumentDigest ||
            rec.metadataDigest != claimedMetadataDigest ||
            rec.merkleRoot != claimedMerkleRoot
        ) {
            return VerificationResult({
                isValid: false,
                code: VerificationCode.HashMismatch,
                storedStatus: rec.status,
                issuerId: rec.issuerId,
                isIssuerActive: issuerActive,
                expiresAt: rec.expiresAt
            });
        }

        if (rec.status != StoredStatus.Active) {
            return VerificationResult({
                isValid: false,
                code: VerificationCode.InvalidStoredStatus,
                storedStatus: rec.status,
                issuerId: rec.issuerId,
                isIssuerActive: issuerActive,
                expiresAt: rec.expiresAt
            });
        }

        if (rec.expiresAt != 0 && block.timestamp >= rec.expiresAt) {
            return VerificationResult({
                isValid: false,
                code: VerificationCode.Expired,
                storedStatus: rec.status,
                issuerId: rec.issuerId,
                isIssuerActive: issuerActive,
                expiresAt: rec.expiresAt
            });
        }

        if (!issuerActive) {
            return VerificationResult({
                isValid: false,
                code: VerificationCode.IssuerNotActive,
                storedStatus: rec.status,
                issuerId: rec.issuerId,
                isIssuerActive: false,
                expiresAt: rec.expiresAt
            });
        }

        return VerificationResult({
            isValid: true,
            code: VerificationCode.Valid,
            storedStatus: StoredStatus.Active,
            issuerId: rec.issuerId,
            isIssuerActive: true,
            expiresAt: rec.expiresAt
        });
    }
}
