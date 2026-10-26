import apiClient from './apiClient';
import { AuthConfig, DevTokenParams, DevTokenResponse, AuthPrincipal } from '@/types/auth';

export const authApi = {
  getAuthConfig: async (): Promise<AuthConfig> => {
    const { data } = await apiClient.get<AuthConfig>('/api/v1/auth/config');
    return data;
  },

  getDevToken: async (params: DevTokenParams): Promise<DevTokenResponse> => {
    const { data } = await apiClient.post<DevTokenResponse>('/api/v1/auth/dev-token', params);
    return data;
  },

  getCurrentUser: async (): Promise<AuthPrincipal & { is_admin: boolean }> => {
    const { data } = await apiClient.get<AuthPrincipal & { is_admin: boolean }>('/api/v1/auth/me');
    return data;
  },
};
