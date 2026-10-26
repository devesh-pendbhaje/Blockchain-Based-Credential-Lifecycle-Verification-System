import apiClient from './apiClient';
import {
  MerkleBuildTreeRequest,
  MerkleBuildTreeResponse,
  MerkleVerifyProofRequest,
  MerkleVerifyProofResponse,
} from '@/types/merkle';

export const merkleApi = {
  buildTree: async (payload: MerkleBuildTreeRequest): Promise<MerkleBuildTreeResponse> => {
    const { data } = await apiClient.post<MerkleBuildTreeResponse>('/api/v1/merkle/build-tree', payload);
    return data;
  },

  verifyProof: async (payload: MerkleVerifyProofRequest): Promise<MerkleVerifyProofResponse> => {
    const { data } = await apiClient.post<MerkleVerifyProofResponse>('/api/v1/merkle/verify-proof', payload);
    return data;
  },
};
