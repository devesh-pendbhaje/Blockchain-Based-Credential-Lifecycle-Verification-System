import apiClient from './apiClient';
import { IssuerCreateRequest, IssuerResponse, IssuerStatusResponse } from '@/types/issuer';

export const issuerApi = {
  createIssuer: async (payload: IssuerCreateRequest): Promise<IssuerResponse> => {
    const { data } = await apiClient.post<IssuerResponse>('/api/v1/issuers', payload);
    return data;
  },

  getIssuer: async (issuerId: string): Promise<IssuerResponse> => {
    const { data } = await apiClient.get<IssuerResponse>(`/api/v1/issuers/${encodeURIComponent(issuerId)}`);
    return data;
  },

  getIssuerStatus: async (issuerId: string): Promise<IssuerStatusResponse> => {
    const { data } = await apiClient.get<IssuerStatusResponse>(`/api/v1/issuers/${encodeURIComponent(issuerId)}/status`);
    return data;
  },
};
