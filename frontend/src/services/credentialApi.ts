import apiClient from './apiClient';
import {
  CredentialCreateRequest,
  CredentialResponse,
  CredentialVersionResponse,
  VerificationResponse,
} from '@/types/credential';

export const credentialApi = {
  reconcile: async (id: string, version: number): Promise<CredentialResponse> => {
    const {data} = await apiClient.post(`/api/v1/credentials/${encodeURIComponent(id)}/versions/${version}/anchor`);
    return data;
  },
  createCredential: async (payload: CredentialCreateRequest): Promise<CredentialResponse> => {
    const { data } = await apiClient.post<CredentialResponse>('/api/v1/credentials', payload);
    return data;
  },

  getCredential: async (credentialId: string): Promise<CredentialResponse> => {
    const { data } = await apiClient.get<CredentialResponse>(`/api/v1/credentials/${encodeURIComponent(credentialId)}`);
    return data;
  },

  getCredentialByFingerprint: async (fingerprint: string): Promise<CredentialResponse> => {
    const { data } = await apiClient.get<CredentialResponse>(
      `/api/v1/credentials/fingerprint/${encodeURIComponent(fingerprint)}`
    );
    return data;
  },

  verifyCredential: async (fingerprint: string): Promise<VerificationResponse> => {
    const { data } = await apiClient.get<VerificationResponse>(
      `/api/v1/credentials/fingerprint/${encodeURIComponent(fingerprint)}/verify`
    );
    return data;
  },

  getCredentialVersions: async (credentialId: string): Promise<CredentialVersionResponse[]> => {
    const { data } = await apiClient.get<CredentialVersionResponse[]>(
      `/api/v1/credentials/${encodeURIComponent(credentialId)}/versions`
    );
    return data;
  },

  listCredentials: async (limit: number = 50, offset: number = 0): Promise<CredentialResponse[]> => {
    const { data } = await apiClient.get<CredentialResponse[]>('/api/v1/credentials', {
      params: { limit, offset },
    });
    return data;
  },

  suspendCredential: async (credentialId: string, reasonCode: number = 1): Promise<CredentialResponse> => {
    const { data } = await apiClient.post<CredentialResponse>(
      `/api/v1/credentials/${encodeURIComponent(credentialId)}/suspend`,
      { reason_code: reasonCode }
    );
    return data;
  },

  reactivateCredential: async (credentialId: string, reasonCode: number = 1): Promise<CredentialResponse> => {
    const { data } = await apiClient.post<CredentialResponse>(
      `/api/v1/credentials/${encodeURIComponent(credentialId)}/reactivate`,
      { reason_code: reasonCode }
    );
    return data;
  },

  revokeCredential: async (credentialId: string, reasonCode: number = 1): Promise<CredentialResponse> => {
    const { data } = await apiClient.post<CredentialResponse>(
      `/api/v1/credentials/${encodeURIComponent(credentialId)}/revoke`,
      { reason_code: reasonCode }
    );
    return data;
  },

  reconcileAndAnchorVersion: async (credentialId: string, version: number): Promise<CredentialResponse> => {
    const { data } = await apiClient.post<CredentialResponse>(
      `/api/v1/credentials/${encodeURIComponent(credentialId)}/versions/${version}/anchor`
    );
    return data;
  },
};
