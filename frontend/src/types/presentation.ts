export interface DisclosedClaim {
  key: string;
  value: string;
  salt: string;
  leaf_hash: string;
  proof: string[];
}

export interface PresentationGenerateRequest {
  credential_id: string;
  version: number;
  attributes: Record<string, string>;
  salts: Record<string, string>;
  disclosed_keys: string[];
  document_digest: string;
  metadata_digest: string;
  issuer_id: string;
  challenge_id?: string;
  challenge_nonce?: string;
}

export interface PresentationResponse {
  credential_fingerprint: string;
  credential_id: string;
  version: number;
  issuer_id: string;
  merkle_root: string;
  document_digest: string;
  metadata_digest: string;
  disclosed_claims: DisclosedClaim[];
  challenge_id?: string | null;
  challenge_nonce?: string | null;
}

export interface PresentationVerifyRequest {
  presentation: Record<string, unknown>;
  verifier_session_id: string;
  require_current_version?: boolean;
}

export interface PresentationVerifyResponse {
  overall_valid: boolean;
  selective_disclosure_valid: boolean;
  disclosed_attributes: Record<string, string>;
  challenge_verified: boolean;
  fingerprint_verified: boolean;
  database_status: string;
  is_current_version: boolean;
  blockchain_verification: {
    available: boolean;
    result?: unknown;
    reason?: string;
    [key: string]: unknown;
  };
  privacy_notice: string;
}
