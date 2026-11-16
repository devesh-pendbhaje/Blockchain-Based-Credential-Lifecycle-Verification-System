# Storage Encryption & Key Management Guide

## 1. Overview

The system uses **AES-256-GCM** (Galois/Counter Mode) authenticated symmetric encryption to secure raw certificate files and sensitive documents stored at rest. 

Each stored file includes:
- A cryptographically random 12-byte initialization vector (IV / nonce).
- A 16-byte authentication tag ensuring integrity and authentic provenance.
- The ciphertext payload.

Tampered ciphertext or incorrect decryption keys fail immediately with authentication verification errors before data is exposed.

---

## 2. Cryptographic Key Generation

Storage encryption requires a 256-bit (32-byte) cryptographically secure random key. Generate production keys using OpenSSL or Python's `secrets` module:

### Using OpenSSL (Recommended)
```bash
openssl rand -hex 32
```
*Example output:*
`9f83ab2851cf571e29e9432657d42cf38be1a80d440efb834927b25a3d46f912`

### Using Python
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## 3. Environment Configuration

Configure keys via environment variables or a secure secret store:

```env
# Primary key for encrypting new files and primary decryption attempts
STORAGE_ENCRYPTION_KEY=9f83ab2851cf571e29e9432657d42cf38be1a80d440efb834927b25a3d46f912

# Optional comma-separated list of previous keys for seamless zero-downtime key rotation
STORAGE_PREVIOUS_ENCRYPTION_KEYS=3a4b5c6d7e8f901234567890abcdef1234567890abcdef1234567890abcdef12,8a7b6c5d4e3f201918273645abcdef0123456789abcdef0123456789abcdef01
```

### Production Validation Guardrails
In production mode (`ENVIRONMENT != "development"` and `AUTH_MODE != "local_dev"`), the system enforces strict startup guardrails:
1. `STORAGE_ENCRYPTION_KEY` must be configured.
2. `STORAGE_ENCRYPTION_KEY` must not be any known test/example key (e.g., `0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef`, all-zeros, or all-ones).
3. If validation fails, the backend refuses to start and raises a `RuntimeError` to prevent operating with compromised credentials.

---

## 4. Zero-Downtime Key Rotation Procedure

The storage service supports key rotation with automatic transparent re-encryption on read.

### Rotation Steps:

1. **Generate New Primary Key**:
   ```bash
   NEW_KEY=$(openssl rand -hex 32)
   ```

2. **Update Environment**:
   - Move the current `STORAGE_ENCRYPTION_KEY` to the front of `STORAGE_PREVIOUS_ENCRYPTION_KEYS`.
   - Set `STORAGE_ENCRYPTION_KEY` to the `$NEW_KEY`.

   *Before rotation:*
   ```env
   STORAGE_ENCRYPTION_KEY=KEY_A
   STORAGE_PREVIOUS_ENCRYPTION_KEYS=
   ```

   *After rotation:*
   ```env
   STORAGE_ENCRYPTION_KEY=KEY_B
   STORAGE_PREVIOUS_ENCRYPTION_KEYS=KEY_A
   ```

3. **Deploy Configuration / Restart Backend**:
   - Restart backend instances. New document uploads will immediately be encrypted under `KEY_B`.

4. **Transparent Re-encryption**:
   - When any historical document is retrieved via `retrieve_certificate`, the service:
     1. Attempts decryption with the primary key (`KEY_B`).
     2. If decryption fails, tries each fallback key in `STORAGE_PREVIOUS_ENCRYPTION_KEYS` in order (`KEY_A`).
     3. Once decrypted under `KEY_A`, the service re-encrypts the document under the primary key (`KEY_B`) and atomically updates the stored file (`overwrite=True`).
     4. Subsequent reads decrypt immediately using `KEY_B`.

5. **Decommissioning Old Keys**:
   - After running a batch re-encryption script or when all historical documents have been accessed and migrated, remove deprecated keys from `STORAGE_PREVIOUS_ENCRYPTION_KEYS`.

---

## 5. Key Storage and Backup Recommendations

1. **Never commit keys to Git**: Ensure `.env` and local override files are listed in `.gitignore`.
2. **Use Enterprise Secret Managers**:
   - AWS Secrets Manager / AWS KMS
   - HashiCorp Vault
   - Azure Key Vault
   - Google Cloud Secret Manager
3. **Backup Strategy**:
   - Store encrypted backups of production keys in an offline, air-gapped vault or multi-custody HSM.
   - If an encryption key is lost, AES-256-GCM ciphertext cannot be decrypted or recovered.
