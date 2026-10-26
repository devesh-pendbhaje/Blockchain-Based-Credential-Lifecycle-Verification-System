// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "@openzeppelin/contracts/access/Ownable.sol";
import "./interfaces/IIssuerRegistry.sol";

/**
 * @title IssuerRegistry
 * @notice Maintains accredited issuer identities, operational signing keys, and two-step key rotation.
 */
contract IssuerRegistry is Ownable, IIssuerRegistry {
    mapping(bytes32 => IssuerRecord) private _issuers;
    mapping(address => bytes32) private _signingAddressToIssuerId;
    mapping(address => bytes32) private _pendingAddressToIssuerId;

    modifier onlyGovernance() {
        if (msg.sender != owner()) {
            revert NotGovernanceAdmin();
        }
        _;
    }

    constructor(address initialAdmin) Ownable(initialAdmin) {
        if (initialAdmin == address(0)) {
            revert InvalidZeroAddress();
        }
    }

    /**
     * @notice Accredits a new issuing authority.
     */
    function registerIssuer(
        bytes32 issuerId,
        address initialSigningAddress,
        string calldata metadataUri
    ) external override onlyGovernance {
        if (issuerId == bytes32(0)) {
            revert ZeroIdentifierNotAllowed();
        }
        if (initialSigningAddress == address(0)) {
            revert InvalidZeroAddress();
        }
        if (_issuers[issuerId].registeredAt != 0) {
            revert IssuerAlreadyRegistered(issuerId);
        }
        if (_signingAddressToIssuerId[initialSigningAddress] != bytes32(0)) {
            revert AddressAlreadyAssigned(initialSigningAddress);
        }

        uint64 currentTime = uint64(block.timestamp);
        _issuers[issuerId] = IssuerRecord({
            issuerId: issuerId,
            signingAddress: initialSigningAddress,
            pendingSigningAddress: address(0),
            status: IssuerStatus.Active,
            metadataUri: metadataUri,
            registeredAt: currentTime,
            statusUpdatedAt: currentTime
        });

        _signingAddressToIssuerId[initialSigningAddress] = issuerId;

        emit IssuerRegistered(issuerId, initialSigningAddress, metadataUri);
    }

    /**
     * @notice Updates the administrative status of an issuer (e.g. Active, Suspended, Revoked).
     */
    function setIssuerStatus(bytes32 issuerId, IssuerStatus newStatus) external override onlyGovernance {
        IssuerRecord storage record = _issuers[issuerId];
        if (record.registeredAt == 0) {
            revert IssuerNotFound(issuerId);
        }

        IssuerStatus oldStatus = record.status;
        record.status = newStatus;
        record.statusUpdatedAt = uint64(block.timestamp);

        emit IssuerStatusUpdated(issuerId, oldStatus, newStatus);
    }

    /**
     * @notice Emergency administrative override to rotate a signing key.
     */
    function emergencyRotateSigningAddress(
        bytes32 issuerId,
        address newSigningAddress
    ) external override onlyGovernance {
        IssuerRecord storage record = _issuers[issuerId];
        if (record.registeredAt == 0) {
            revert IssuerNotFound(issuerId);
        }
        if (newSigningAddress == address(0)) {
            revert InvalidZeroAddress();
        }
        if (newSigningAddress == record.signingAddress) {
            revert SameAddressReassignment();
        }
        if (_signingAddressToIssuerId[newSigningAddress] != bytes32(0)) {
            revert AddressAlreadyAssigned(newSigningAddress);
        }

        address oldKey = record.signingAddress;
        delete _signingAddressToIssuerId[oldKey];

        if (record.pendingSigningAddress != address(0)) {
            delete _pendingAddressToIssuerId[record.pendingSigningAddress];
            record.pendingSigningAddress = address(0);
        }

        record.signingAddress = newSigningAddress;
        record.statusUpdatedAt = uint64(block.timestamp);
        _signingAddressToIssuerId[newSigningAddress] = issuerId;

        emit SigningKeyRotated(issuerId, oldKey, newSigningAddress);
    }

    /**
     * @notice Step 1 of self-service key rotation: current active signing key proposes replacement.
     */
    function proposeSigningAddress(address newSigningAddress) external override {
        bytes32 issuerId = _signingAddressToIssuerId[msg.sender];
        if (issuerId == bytes32(0)) {
            revert NotAuthorizedIssuer();
        }

        IssuerRecord storage record = _issuers[issuerId];
        if (record.status != IssuerStatus.Active) {
            revert NotAuthorizedIssuer();
        }
        if (newSigningAddress == address(0)) {
            revert InvalidZeroAddress();
        }
        if (newSigningAddress == msg.sender) {
            revert SameAddressReassignment();
        }
        if (_signingAddressToIssuerId[newSigningAddress] != bytes32(0)) {
            revert AddressAlreadyAssigned(newSigningAddress);
        }

        if (record.pendingSigningAddress != address(0)) {
            delete _pendingAddressToIssuerId[record.pendingSigningAddress];
        }

        record.pendingSigningAddress = newSigningAddress;
        _pendingAddressToIssuerId[newSigningAddress] = issuerId;

        emit SigningKeyRotationProposed(issuerId, msg.sender, newSigningAddress);
    }

    /**
     * @notice Step 2 of self-service key rotation: proposed replacement confirms custody of private key.
     */
    function acceptSigningAddress() external override {
        bytes32 issuerId = _pendingAddressToIssuerId[msg.sender];
        if (issuerId == bytes32(0)) {
            revert NotPendingSigner();
        }

        IssuerRecord storage record = _issuers[issuerId];
        if (record.status != IssuerStatus.Active) {
            revert NotAuthorizedIssuer();
        }

        address oldKey = record.signingAddress;
        delete _signingAddressToIssuerId[oldKey];
        delete _pendingAddressToIssuerId[msg.sender];

        record.signingAddress = msg.sender;
        record.pendingSigningAddress = address(0);
        record.statusUpdatedAt = uint64(block.timestamp);
        _signingAddressToIssuerId[msg.sender] = issuerId;

        emit SigningKeyRotated(issuerId, oldKey, msg.sender);
    }

    /**
     * @notice Returns true if the issuer is registered and currently in Active standing.
     */
    function isIssuerActive(bytes32 issuerId) external view override returns (bool) {
        return (_issuers[issuerId].registeredAt != 0 && _issuers[issuerId].status == IssuerStatus.Active);
    }

    /**
     * @notice Returns authorization status and issuerId bound to a signing address.
     */
    function getIssuerBySigningAddress(
        address signingAddress
    ) external view override returns (bool isAuthorized, bytes32 issuerId) {
        issuerId = _signingAddressToIssuerId[signingAddress];
        if (issuerId == bytes32(0)) {
            return (false, bytes32(0));
        }
        isAuthorized = (_issuers[issuerId].status == IssuerStatus.Active);
    }

    /**
     * @notice Returns the full issuer record.
     */
    function getIssuer(bytes32 issuerId) external view override returns (IssuerRecord memory) {
        IssuerRecord memory record = _issuers[issuerId];
        if (record.registeredAt == 0) {
            revert IssuerNotFound(issuerId);
        }
        return record;
    }
}
