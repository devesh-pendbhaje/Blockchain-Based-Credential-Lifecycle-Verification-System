export interface ChallengeCreateRequest {
  verifier_session_id: string;
  credential_fingerprint?: string;
  expiry_seconds?: number;
}

export interface ChallengeCreateResponse {
  challenge_id: string;
  challenge_nonce: string;
  verifier_session_id: string;
  credential_fingerprint: string | null;
  expires_at: string;
  status: string;
}
