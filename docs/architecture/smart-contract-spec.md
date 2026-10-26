# Smart Contract Specification: Phase 1

This document specifies the architecture, interfaces, data models, state transitions, cryptographic invariants, and test suites for **`IssuerRegistry.sol`** and **`CredentialRegistry.sol`**.

---

## 1. Architectural Overview & Key Decisions

### 1.1 Separation of Cryptographic Primitives
To support selective disclosure without conflating documents, attribute claims, and identity:
* **`documentDigest` (`bytes32`)**: The cryptographic digest (Keccak-256 / SHA-256) of the complete visual certificate (e.g., rendered PDF or canonical presentation).
* **`metadataDigest` (`bytes32`)**: The cryptographic digest of the RFC 8785 canonicalized metadata payload.
* **`merkleRoot` (`bytes32`)**: The root of the domain-separated, salted, sorted-pair Merkle tree formed from individual credential attributes.
* **`credentialId` (`bytes32`)**: Unique business identifier of the credential (e.g., UUID or `keccak256("DIPLOMA-2026-0042")`).
* **`version` (`uint32`)**: Monotonically increasing version counter for the given `(issuerId, credentialId)`.
* **`fingerprint` (`bytes32`)**: The composite fingerprint anchored on-chain binding all 6 parameters:
  $$\text{fingerprint} = \text{keccak256}\Big(\text{abi.encode}(\text{documentDigest}, \text{metadataDigest}, \text{merkleRoot}, \text{issuerId}, \text{credentialId}, \text{version})\Big)$$

---

## 2. Permitted Lifecycle State Transition Matrix

The smart contract tracks stored statuses and computes dynamic expiration without gas overhead.

### Stored Statuses:
* `None` (0): Unregistered
* `Active` (1): In good standing
* `Suspended` (2): Temporarily paused
* `Revoked` (3): Permanently invalidated (Terminal)
* `Superseded` (4): Replaced by a newer version (Terminal except for fraud revocation)
* `Archived` (5): Administratively retired (Terminal except for fraud revocation)

### Transition Matrix:

| From State | To `Active` | To `Suspended` | To `Revoked` | To `Superseded` | To `Archived` |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **`None`** |  (via `issueCredential`) | ❌ | ❌ | ❌ | ❌ |
| **`Active`** | ❌ (Already Active) |  (`suspendCredential`) |  (`revokeCredential`) |  (`supersedeCredential`) |  (`archiveCredential`) |
| **`Suspended`** |  (`reactivateCredential`) | ❌ |  (`revokeCredential`) | ❌ (Must reactivate first) |  (`archiveCredential`) |
| **`Revoked`** | ❌ (Terminal) | ❌ (Terminal) | ❌ (Terminal) | ❌ (Terminal) | ❌ (Terminal) |
| **`Superseded`**| ❌ (Terminal) | ❌ (Terminal) |  (Retroactive Fraud) | ❌ (Terminal) | ❌ (Terminal) |
| **`Archived`** | ❌ (Terminal) | ❌ (Terminal) |  (Retroactive Fraud) | ❌ (Terminal) | ❌ (Terminal) |

*Any transition marked with ❌ reverts with `InvalidLifecycleTransition(currentStatus, targetStatus)`.*

---

## 3. Cryptographic Standards & Domain Separation

### 3.1 Domain-Separated Leaf & Node Hashing
To prevent second-preimage attacks where an intermediate node could be submitted as a leaf:
* **Leaf Domain Separator**: `0x00` byte prefix
* **Internal Node Separator**: `0x01` byte prefix

$$\text{leaf}_i = \text{keccak256}\Big(\text{abi.encode}(\text{bytes1}(0x00), \text{bytes32 } s_i, \text{string } \text{key}_i, \text{string } \text{value}_i)\Big)$$

$$\text{parent} = \text{keccak256}\Big(\text{abi.encode}(\text{bytes1}(0x01), \min(\text{bytes32 left}, \text{bytes32 right}), \max(\text{bytes32 left}, \text{bytes32 right}))\Big)$$

> **Authoritative Specification & OpenZeppelin Note**: While this design adopts commutative sorted-pair ordering, the addition of the `0x01` domain separator prefix and typed 32-byte padded `abi.encode` makes this a **custom construction that is NOT byte-for-byte compatible with OpenZeppelin's standard `MerkleProof.sol`** (which hashes un-prefixed packed pairs via `bytes.concat(min, max)`). All verification routines across Python, TypeScript, and Solidity must use this exact domain-separated construction.

### 3.2 Salt Generation & Attribute Ordering
* **Salt Generation**: 256 bits generated via CSPRNG (`secrets.token_bytes(32)` in Python; `crypto.getRandomValues(new Uint8Array(32))` in TypeScript).
* **Attribute Ordering**: Claims are sorted lexicographically by canonical ASCII/UTF-8 key (RFC 8785) prior to leaf generation.
* **Odd-Leaf Rule**: If a level contains an odd number of nodes, the unpaired node is **promoted directly** to the parent level without duplication, preventing duplicate-leaf malleability.

### 3.3 Test Vector (Cross-Language Bit-Level Parity)

```text
Claim:
  key:   "degree"
  value: "B.S. Computer Science"
  salt:  0x0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef

Encoding (abi.encode):
  0x00 (padded to 32 bytes)
  salt (32 bytes)
  offset of key
  offset of value
  length and UTF-8 bytes of key
  length and UTF-8 bytes of value

Leaf Hash:
  keccak256(abi.encode(bytes1(0x00), bytes32(salt), string("degree"), string("B.S. Computer Science")))
```

---

## 4. `IssuerRegistry.sol` Interface Specification

```solidity
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

    // --- Consistent Verification Functions ---
    function isIssuerActive(bytes32 issuerId) external view returns (bool);

    function getIssuerBySigningAddress(address signingAddress) external view returns (bool isAuthorized, bytes32 issuerId);

    function getIssuer(bytes32 issuerId) external view returns (IssuerRecord memory);
}
```

---

## 5. `CredentialRegistry.sol` Interface Specification

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "./IIssuerRegistry.sol";

interface ICredentialRegistry {
    enum StoredStatus { None, Active, Suspended, Revoked, Superseded, Archived }
    enum VerificationCode {
        Valid,                   // 0: Active, unexpired, authorized issuer
        NotFound,                // 1: Credential not registered
        HashMismatch,            // 2: Claimed digests do not match record
        InvalidStoredStatus,     // 3: Suspended, Revoked, Superseded, or Archived
        Expired,                 // 4: Active but block.timestamp >= expiresAt
        IssuerNotActive          // 5: Credential valid, but issuing institution is inactive
    }

    struct CredentialRecord {
        bytes32 fingerprint;       // Composite hash F
        bytes32 credentialId;      // Business identifier
        bytes32 issuerId;          // Issuer ID in IssuerRegistry
        bytes32 documentDigest;    // Complete visual document hash
        bytes32 metadataDigest;    // Digest of RFC 8785 canonicalized metadata
        bytes32 merkleRoot;        // Salted claims Merkle root
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

    // --- Custom Errors ---
    error CallerNotAuthorizedIssuer(address caller);
    error CredentialAlreadyExists(bytes32 fingerprint);
    error CredentialNotFound(bytes32 fingerprint);
    error CallerNotCredentialIssuer(bytes32 expectedIssuer, bytes32 callerIssuer);
    error InvalidCredentialVersion(uint32 expectedVersion, uint32 providedVersion);
    error InvalidLifecycleTransition(StoredStatus currentStatus, StoredStatus targetStatus);
    error InvalidExpirationTime(uint64 expiresAt);
    error ZeroDigestNotAllowed();
    error UnsupportedReasonCode(uint8 reasonCode);

    // --- Events (Zero PII: Only Hashes, IDs, and Integer Reason Codes) ---
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

    // --- Issuance & State Management ---
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

    // --- View & Verification Functions ---
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

    function verifyCredential(
        bytes32 fingerprint,
        bytes32 claimedDocumentDigest,
        bytes32 claimedMetadataDigest,
        bytes32 claimedMerkleRoot
    ) external view returns (VerificationResult memory);
}
```

---

## 6. Hardhat Test Suite Matrix

### `IssuerRegistry.test.ts`
1. **Access Control**: Revert when non-admin attempts `registerIssuer`, `setIssuerStatus`, or `emergencyRotateSigningAddress`.
2. **Registration Guardrails**: Revert if `issuerId` already exists, if `initialSigningAddress == address(0)`, or if the address is already assigned to another issuer.
3. **Emergency Rotation Hardening**:
   - Revert if target address is `address(0)` (`InvalidZeroAddress`).
   - Revert if target address is already assigned (`AddressAlreadyAssigned`).
   - Confirm old address reverse mapping is deleted and new reverse mapping is active.
4. **2-Step Rotation**:
   - Propose rotation; verify `pendingSigningAddress` set.
   - Non-pending address calling `acceptSigningAddress` reverts with `NotPendingSigner`.
   - Pending address accepts; verify atomic update of active and reverse mappings.
5. **Issuer Status Check Consistency**:
   - Confirm `isIssuerActive(issuerId)` returns `true` when active and `false` when suspended/revoked.

### `CredentialRegistry.test.ts`
1. **Authorized Issuance & Fingerprint Binding**:
   - Only active signing address can issue for its registered `issuerId`.
   - Enforce `version == 1` on initial issuance of a `credentialId`.
   - Verify `computeFingerprint` matches stored `record.fingerprint`.
2. **Version Monotonicity**:
   - Submitting duplicate version or skipped version reverts with `InvalidCredentialVersion`.
   - `supersedeCredential` increments version from `v` to `v + 1` automatically.
3. **State Transition Matrix Compliance**:
   - `Active` $\rightarrow$ `Suspended` $\rightarrow$ `Active` (Passes).
   - `Active` $\rightarrow$ `Revoked` $\rightarrow$ attempt `reactivate` reverts with `InvalidLifecycleTransition`.
   - `Suspended` $\rightarrow$ attempt `supersede` directly reverts; must reactivate first.
   - `Superseded` $\rightarrow$ attempt `reactivate` reverts with `InvalidLifecycleTransition`.
   - `Active` $\rightarrow$ `Archived` (Passes).
4. **Verification Result Discrimination**:
   - Valid credential $\rightarrow$ returns `(isValid = true, code = Valid)`.
   - Tampered Merkle root / document digest $\rightarrow$ returns `(isValid = false, code = HashMismatch)`.
   - Expired credential (`block.timestamp >= expiresAt`) $\rightarrow$ returns `(isValid = false, code = Expired)`.
   - Inactive issuer (`isIssuerActive == false`) $\rightarrow$ returns `(isValid = false, code = IssuerNotActive)`.
5. **Privacy & Event Auditing**:
   - Assert all events emit `uint8 reasonCode` and zero raw strings or PII.
