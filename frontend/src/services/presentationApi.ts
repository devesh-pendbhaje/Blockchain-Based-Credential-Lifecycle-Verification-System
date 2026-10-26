import apiClient from './apiClient';
import {
  PresentationGenerateRequest,
  PresentationResponse,
  PresentationVerifyRequest,
  PresentationVerifyResponse,
} from '@/types/presentation';

export const presentationApi = {
  generatePresentation: async (payload: PresentationGenerateRequest): Promise<PresentationResponse> => {
    const { data } = await apiClient.post<PresentationResponse>('/api/v1/presentations/generate', payload);
    return data;
  },

  verifyPresentation: async (payload: PresentationVerifyRequest): Promise<PresentationVerifyResponse> => {
    const { data } = await apiClient.post<PresentationVerifyResponse>('/api/v1/presentations/verify', payload);
    return data;
  },
};
