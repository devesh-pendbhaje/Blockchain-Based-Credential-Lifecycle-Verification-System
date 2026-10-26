export interface MerkleBuildTreeRequest {
  attributes: Record<string, string>;
  salts?: Record<string, string>;
}

export interface MerkleBuildTreeResponse {
  merkle_root: string;
  ordered_keys: string[];
  leaves: Record<string, string>;
  salts: Record<string, string>;
  proofs: Record<string, string[]>;
}

export interface MerkleVerifyProofRequest {
  root: string;
  leaf: string;
  proof: string[];
}

export interface MerkleVerifyProofResponse {
  is_valid: boolean;
}
