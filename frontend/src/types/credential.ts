export type CredentialLifecycleStatus = 'ACTIVE' | 'SUSPENDED' | 'REVOKED' | 'SUPERSEDED' | 'EXPIRED';

export interface CredentialCreateRequest {
  credential_id: string; // 0x + 64 hex characters
  issuer_id: string;     // 0x + 64 hex characters
  document_digest: string; // 0x + 64 hex characters
  metadata_digest: string; // 0x + 64 hex characters
  merkle_root: string;     // 0x + 64 hex characters
  version?: number;
  expires_at?: number;
  idempotency_key?: string | null;
}

export interface CredentialResponse {
  credential_id: string;
  issuer_id: string;
  current_version: number;
  current_fingerprint: string;
  current_status: CredentialLifecycleStatus | string;
  issuance_status: string;
  issuance_tx_hash: string | null;
  created_at: string;
  updated_at: string;
}

export interface CredentialVersionResponse {
  credential_id: string;
  version: number;
  fingerprint: string;
  document_digest: string;
  metadata_digest: string;
  merkle_root: string;
  expires_at: number;
  issuance_status: string;
  issuance_tx_hash: string | null;
  block_number: number | null;
  chain_id: number | null;
  superseded_by_fingerprint: string | null;
  created_at: string;
}

export interface VerificationResponse {
  fingerprint: string;
  database_found: boolean;
  blockchain_available: boolean;
  is_valid: boolean;
  lifecycle_status: string | null;
  is_expired: boolean | null;
  digest_match: boolean | null;
  blockchain_code: string | null;
  details: string;
  checked_at: string;
}
