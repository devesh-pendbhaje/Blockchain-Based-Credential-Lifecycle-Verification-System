// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "./IIssuerRegistry.sol";

interface ICredentialRegistry {
    enum StoredStatus { None, Active, Suspended, Revoked, Superseded, Archived }
    enum VerificationCode {
        Valid,               // 0: Active, unexpired, authorized issuer
        NotFound,            // 1: Credential not registered
        HashMismatch,        // 2: Claimed digests do not match record
        InvalidStoredStatus, // 3: Suspended, Revoked, Superseded, or Archived
        Expired,             // 4: Active but block.timestamp >= expiresAt
        IssuerNotActive      // 5: Credential valid, but issuing institution is inactive
    }

    struct CredentialRecord {
        bytes32 fingerprint;       // Composite hash F
        bytes32 credentialId;      // Business identifier
        bytes32 issuerId;          // Issuer ID in IssuerRegistry
        bytes32 documentDigest;    // Digest of complete visual certificate document
        bytes32 metadataDigest;    // Digest of RFC 8785 canonicalized metadata
        bytes32 merkleRoot;        // Root of the salted attribute Merkle tree
        uint32 version;            // Monotonically increasing version
        StoredStatus status;       // Stored lifecycle status
        uint64 issuedAt;           // Issuance timestamp
        uint64 expiresAt;          // 0 = never expires
        uint64 statusUpdatedAt;    // Last status mutation timestamp
        bytes32 supersededBy;      // Fingerprint of replacement (if superseded)
    }

    struct VerificationResult {
        bool isValid;
        VerificationCode code;
        StoredStatus storedStatus;
        bytes32 issuerId;
        bool isIssuerActive;
        uint64 expiresAt;
    }

    // Custom Errors
    error CallerNotAuthorizedIssuer(address caller);
    error CredentialAlreadyExists(bytes32 fingerprint);
    error CredentialNotFound(bytes32 fingerprint);
    error CallerNotCredentialIssuer(bytes32 expectedIssuer, bytes32 callerIssuer);
    error InvalidCredentialVersion(uint32 expectedVersion, uint32 providedVersion);
    error InvalidLifecycleTransition(StoredStatus currentStatus, StoredStatus targetStatus);
    error InvalidExpirationTime(uint64 expiresAt);
    error ZeroDigestNotAllowed();
    error ZeroIdentifierNotAllowed();
    error VersionOverflowNotAllowed();
    error UnsupportedReasonCode(uint8 reasonCode);

    // Events (Zero PII, numeric reason codes)
    event CredentialIssued(
        bytes32 indexed fingerprint,
        bytes32 indexed credentialId,
        bytes32 indexed issuerId,
        bytes32 documentDigest,
        bytes32 metadataDigest,
        bytes32 merkleRoot,
        uint32 version,
        uint64 expiresAt
    );
    event CredentialSuspended(bytes32 indexed fingerprint, bytes32 indexed issuerId, uint8 reasonCode);
    event CredentialReactivated(bytes32 indexed fingerprint, bytes32 indexed issuerId);
    event CredentialRevoked(bytes32 indexed fingerprint, bytes32 indexed issuerId, uint8 reasonCode);
    event CredentialSuperseded(bytes32 indexed oldFingerprint, bytes32 indexed newFingerprint, bytes32 indexed issuerId);
    event CredentialArchived(bytes32 indexed fingerprint, bytes32 indexed issuerId, uint8 reasonCode);

    // Lifecycle Functions
    function issueCredential(
        bytes32 credentialId,
        bytes32 documentDigest,
        bytes32 metadataDigest,
        bytes32 merkleRoot,
        uint32 version,
        uint64 expiresAt
    ) external returns (bytes32 fingerprint);

    function suspendCredential(bytes32 fingerprint, uint8 reasonCode) external;
    function reactivateCredential(bytes32 fingerprint) external;
    function revokeCredential(bytes32 fingerprint, uint8 reasonCode) external;
    function supersedeCredential(
        bytes32 oldFingerprint,
        bytes32 newDocumentDigest,
        bytes32 newMetadataDigest,
        bytes32 newMerkleRoot,
        uint64 newExpiresAt
    ) external returns (bytes32 newFingerprint);
    function archiveCredential(bytes32 fingerprint, uint8 reasonCode) external;

    // View & Verification Functions
    function computeFingerprint(
        bytes32 documentDigest,
        bytes32 metadataDigest,
        bytes32 merkleRoot,
        bytes32 issuerId,
        bytes32 credentialId,
        uint32 version
    ) external pure returns (bytes32);

    function getCredential(bytes32 fingerprint) external view returns (CredentialRecord memory);
    function getLatestVersion(bytes32 issuerId, bytes32 credentialId) external view returns (uint32);
    function getVersionFingerprint(bytes32 issuerId, bytes32 credentialId, uint32 version) external view returns (bytes32);
    function getCredentialByVersion(bytes32 issuerId, bytes32 credentialId, uint32 version) external view returns (CredentialRecord memory);
    function verifyCredential(
        bytes32 fingerprint,
        bytes32 claimedDocumentDigest,
        bytes32 claimedMetadataDigest,
        bytes32 claimedMerkleRoot
    ) external view returns (VerificationResult memory);
}
