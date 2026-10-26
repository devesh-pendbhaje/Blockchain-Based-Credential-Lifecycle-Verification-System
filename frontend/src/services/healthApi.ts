import apiClient from './apiClient';
import { LivenessResponse, ReadinessResponse } from '@/types/health';

export const healthApi = {
  getLiveness: async (): Promise<LivenessResponse> => {
    const { data } = await apiClient.get<LivenessResponse>('/health/live');
    return data;
  },

  getReadiness: async (): Promise<ReadinessResponse> => {
    const { data } = await apiClient.get<ReadinessResponse>('/health/ready');
    return data;
  },
};
