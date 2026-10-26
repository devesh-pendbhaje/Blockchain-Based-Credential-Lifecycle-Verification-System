export type IssuerLifecycleStatus = 'ACTIVE' | 'SUSPENDED' | 'REVOKED';

export interface IssuerCreateRequest {
  issuer_id: string; // 0x + 64 hex characters
  display_name: string;
  metadata_uri?: string | null;
  status?: IssuerLifecycleStatus;
}

export interface IssuerResponse {
  issuer_id: string;
  display_name: string;
  metadata_uri: string | null;
  status: IssuerLifecycleStatus;
  created_at: string;
  updated_at: string;
  on_chain_registered: boolean | null;
  on_chain_note: string;
}

export interface IssuerStatusResponse {
  issuer_id: string;
  db_status: IssuerLifecycleStatus;
  on_chain_status: string | null;
  is_on_chain_active: boolean | null;
  checked_at: string;
}
