// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

interface IIssuerRegistry {
    enum IssuerStatus { Inactive, Active, Suspended, Revoked }

    struct IssuerRecord {
        bytes32 issuerId;
        address signingAddress;
        address pendingSigningAddress;
        IssuerStatus status;
        string metadataUri;
        uint64 registeredAt;
        uint64 statusUpdatedAt;
    }

    // --- Custom Errors ---
    error NotGovernanceAdmin();
    error NotAuthorizedIssuer();
    error IssuerAlreadyRegistered(bytes32 issuerId);
    error IssuerNotFound(bytes32 issuerId);
    error AddressAlreadyAssigned(address signingAddress);
    error InvalidZeroAddress();
    error ZeroIdentifierNotAllowed();
    error SameAddressReassignment();
    error NoPendingRotation();
    error NotPendingSigner();

    // --- Events (Zero PII: Only IDs, Addresses, and Status Enums) ---
    event IssuerRegistered(bytes32 indexed issuerId, address indexed signingAddress, string metadataUri);
    event IssuerStatusUpdated(bytes32 indexed issuerId, IssuerStatus oldStatus, IssuerStatus newStatus);
    event SigningKeyRotationProposed(bytes32 indexed issuerId, address indexed currentKey, address indexed proposedKey);
    event SigningKeyRotated(bytes32 indexed issuerId, address indexed oldKey, address indexed newKey);
    event IssuerMetadataUpdated(bytes32 indexed issuerId, string newMetadataUri);

    // --- Governance Functions ---
    function registerIssuer(
        bytes32 issuerId,
        address initialSigningAddress,
        string calldata metadataUri
    ) external;

    function setIssuerStatus(bytes32 issuerId, IssuerStatus newStatus) external;

    function emergencyRotateSigningAddress(bytes32 issuerId, address newSigningAddress) external;

    // --- 2-Step Key Rotation ---
    function proposeSigningAddress(address newSigningAddress) external;

    function acceptSigningAddress() external;

    // --- Verification Functions ---
    function isIssuerActive(bytes32 issuerId) external view returns (bool);

    function getIssuerBySigningAddress(address signingAddress) external view returns (bool isAuthorized, bytes32 issuerId);

    function getIssuer(bytes32 issuerId) external view returns (IssuerRecord memory);
}
