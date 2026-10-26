import apiClient from './apiClient';
import { ChallengeCreateRequest, ChallengeCreateResponse } from '@/types/challenge';

export const challengeApi = {
  createChallenge: async (payload: ChallengeCreateRequest): Promise<ChallengeCreateResponse> => {
    const { data } = await apiClient.post<ChallengeCreateResponse>('/api/v1/challenges', payload);
    return data;
  },
};
