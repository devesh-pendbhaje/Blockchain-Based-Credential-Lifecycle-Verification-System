# System Architecture and Sequence Diagrams

**Project**: Blockchain-Based Credential Lifecycle Verification System  
**Document**: Architectural Sequence Diagrams  
**Date**: October 25, 2026  
**Status**: Verified & Implemented  

---

## 1. Overview

This document provides formal sequence diagrams detailing the four core workflows of the Blockchain-Based Credential Lifecycle Verification System:
1. **Credential Issuance and On-Chain Anchoring**
2. **Zero-Trust Public Verification**
3. **Holder Sovereign Wallet and Anti-Replay Challenge-Response**
4. **Zero-PII QR Code Generation and Physical/Camera Scanning**

All diagrams reflect the actual implemented software components in the FastAPI backend, React frontend, PostgreSQL database, and Sepolia Ethereum smart contracts.

---

## 2. Sequence Diagram 1: Credential Issuance and Sepolia Anchoring

This workflow details how an institutional issuer generates, cryptographically binds, encrypts, and on-chain anchors a verifiable credential while maintaining the strict zero-PII on-chain invariant.

```mermaid
sequenceDiagram
    autonumber
    actor Issuer as "Authorized Issuer"
    participant UI as "Frontend (Issuer Portal)"
    participant API as "FastAPI (Backend)"
    participant Crypto as "Crypto & Merkle Engine"
    participant Storage as "Encrypted Storage (AES-256-GCM)"
    participant DB as "PostgreSQL Database"
    participant Sepolia as "Sepolia (CredentialRegistry)"

    Issuer->>UI: Submit Credential Form (PII Attributes & Doc)
    UI->>API: POST /api/v1/credentials/issue (JWT Auth)
    
    API->>Crypto: Canonicalize Metadata (RFC 8785)
    Crypto-->>API: metadata_digest
    
    API->>Crypto: Build Salted Attribute Merkle Tree
    Crypto-->>API: merkle_root & salted_leaves
    
    API->>Crypto: Compute 6-Input Composite Fingerprint
    Note over API,Crypto: Keccak256(doc_hash || merkle_root || issuer_id || subject_id || ts || schema_version)
    Crypto-->>API: authoritative_composite_fingerprint
    
    API->>Storage: Encrypt PII & Document (Envelope AES-256-GCM)
    Storage-->>API: ciphertext, encrypted_dek, iv, tag
    
    API->>DB: Persist Credential Record (Status: PENDING_ANCHOR)
    DB-->>API: DB Commit Success
    
    API->>Sepolia: issueCredential(fingerprint, issuerAddress, expiryTs)
    Note over API,Sepolia: Transaction mined on Sepolia (Chain ID 11155111)
    Sepolia-->>API: TxReceipt (blockNumber, txHash, gasUsed)
    
    API->>DB: Update Record (Status: ACTIVE, txHash, blockNumber)
    DB-->>API: DB Commit Success
    
    API-->>UI: 201 Created (CredentialResponse with Fingerprint)
    UI-->>Issuer: Display Success & Nav to Credential Details
```

---

## 3. Sequence Diagram 2: Zero-Trust Public Verification

This workflow details how any anonymous public verifier or relying party validates a credential's authenticity without authentication, institutional credentials, or access to sensitive holder PII.

```mermaid
sequenceDiagram
    autonumber
    actor Verifier as "Public Verifier / Relying Party"
    participant UI as "Verification Portal (/verify)"
    participant API as "FastAPI (/credentials/fingerprint/...)"
    participant DB as "PostgreSQL (Encrypted Store)"
    participant Sepolia as "Sepolia (CredentialRegistry.sol)"

    Verifier->>UI: Enter 32-byte Composite Fingerprint
    UI->>API: GET /api/v1/credentials/fingerprint/{fp}/verify (Anonymous)
    
    par Database Query
        API->>DB: Query Credential by Fingerprint
        DB-->>API: Return DB Record & Verification Metadata
    and Smart Contract Verification
        API->>Sepolia: verifyCredential(fingerprint) (Read-only view)
        Note over API,Sepolia: Dynamic block.timestamp evaluation
        Sepolia-->>API: Status (ACTIVE/REVOKED/EXPIRED), Issuer, Timestamps
    end
    
    API->>API: Re-compute Cryptographic Digests & Cross-check
    Note over API: Recompute SHA-256 document hash & Merkle root
    
    alt Status is ACTIVE and Digests Match
        API-->>UI: 200 OK (is_valid: true, status: ACTIVE, on_chain_verified: true)
        UI-->>Verifier: Display Emerald "VALID" Badge & Sepolia Block Confirmation
    else Status is REVOKED / EXPIRED or Not Found
        API-->>UI: 200 OK (is_valid: false, status: REVOKED/EXPIRED/NOT_FOUND)
        UI-->>Verifier: Display Amber/Crimson "INVALID" Badge with Audit Cause
    end
```

---

## 4. Sequence Diagram 3: Holder Sovereign Wallet & Anti-Replay Challenge-Response

This workflow details how a credential subject (holder) manages credentials locally, selects specific attributes to disclose, and signs a single-use replay-protected challenge requested by a verifier.

```mermaid
sequenceDiagram
    autonumber
    actor Holder as "Credential Holder"
    participant Wallet as "Holder Sovereign Wallet (/wallet)"
    participant Verifier as "Relying Party / Employer"
    participant API as "FastAPI Backend"
    participant DB as "PostgreSQL Store"

    Holder->>Wallet: Open Sovereign Wallet (Loads held credentials from localStorage)
    Verifier->>API: POST /api/v1/challenges (Request Nonce for Holder)
    API->>API: Generate 256-bit CSPRNG Nonce (TTL 5 mins)
    API->>DB: Save Nonce Record (Status: ACTIVE)
    API-->>Verifier: Return Challenge (challenge_id, nonce, expires_at)
    
    Verifier->>Holder: Present Challenge Request (challenge_id, nonce, requested_attributes)
    Holder->>Wallet: Select Attributes to Disclose (e.g., GPA, Degree)
    
    Wallet->>API: POST /api/v1/selective-disclosure/presentation
    Note over Wallet,API: Discloses only selected leaf salts + Merkle sibling hashes + Nonce Signature
    API->>API: Verify Merkle Proof Against Stored Merkle Root
    
    API->>DB: Atomically Consume Nonce (UPDATE ... WHERE status = ACTIVE)
    alt Nonce Already Consumed (Replay Attack)
        DB-->>API: Zero rows updated
        API-->>Wallet: 400 Bad Request ("Challenge already consumed")
    else Nonce Valid and Unused
        DB-->>API: Nonce updated to CONSUMED
        API-->>Wallet: 200 OK (presentation_verified: true)
        Wallet-->>Holder: Presentation Verified Successfully
        Holder-->>Verifier: Submit Verified Presentation Proof
    end
```

---

## 5. Sequence Diagram 4: Zero-PII QR Pass Generation and Camera Scanning

This workflow details how the holder renders an ephemeral, zero-PII QR pass, and how a field verifier scans the QR code via hardware camera or file upload to trigger instant cryptographic verification.

```mermaid
sequenceDiagram
    autonumber
    actor Holder as "Credential Holder"
    participant WalletUI as "Holder Wallet / Details Page"
    actor Verifier as "Field Verifier"
    participant ScanUI as "Verification Page Scanner Modal"
    participant Cam as "Device Camera / Image File"
    participant API as "FastAPI Backend"

    Holder->>WalletUI: Click "View QR Pass"
    WalletUI->>WalletUI: Encode Verification URL into QR Matrix
    Note over WalletUI: Payload: https://domain/verify?fingerprint=0x...<br/>(ZERO-PII INVARIANT: No name, no email, no grades)
    WalletUI-->>Holder: Render High-Contrast Scalable QR Code
    
    Verifier->>ScanUI: Click "Scan QR Pass" on /verify
    ScanUI->>Cam: Request Camera Access (navigator.mediaDevices)
    Cam-->>ScanUI: Live Video Stream / Drag-and-Drop Image File
    
    loop Real-Time Video Frame Loop (100ms)
        ScanUI->>ScanUI: jsQR(imageData, width, height)
    end
    
    ScanUI->>ScanUI: Extract URL Parameter '?fingerprint=0x...'
    ScanUI->>ScanUI: Validate 64-char Hexadecimal Structure
    ScanUI-->>ScanUI: Close Modal & Populate Verification Input
    
    ScanUI->>API: GET /api/v1/credentials/fingerprint/{fp}/verify
    API-->>ScanUI: Return Instant On-Chain Verification Verdict
    ScanUI-->>Verifier: Display Authenticity, Issuer Identity, and Blockchain Proof
```
