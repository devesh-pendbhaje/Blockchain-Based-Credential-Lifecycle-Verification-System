export interface DocumentUploadResponse {
  storage_id: string;
  document_digest: string;
  content_type: string;
  byte_size: number;
  storage_adapter: string;
  created_at: string;
}

export interface CanonicalMetadataRequest {
  metadata: unknown;
}

export interface CanonicalMetadataResponse {
  metadata_digest: string;
  canonical_bytes_length: number;
  canonical_json: string;
}

export interface StorageMetadataResponse {
  storage_id: string;
  document_digest: string;
  content_type: string;
  byte_size: number;
  envelope_version: number;
  created_at: string | null;
}
