import apiClient from './apiClient';
import {
  CanonicalMetadataResponse,
  DocumentUploadResponse,
  StorageMetadataResponse,
} from '@/types/document';

export const documentApi = {
  uploadCertificate: async (
    file: File,
    onProgress?: (percent: number) => void
  ): Promise<DocumentUploadResponse> => {
    const formData = new FormData();
    formData.append('file', file);

    const { data } = await apiClient.post<DocumentUploadResponse>('/api/v1/documents/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      onUploadProgress: (progressEvent) => {
        if (progressEvent.total && onProgress) {
          const percent = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          onProgress(percent);
        }
      },
    });

    return data;
  },

  canonicalizeMetadata: async (metadata: unknown): Promise<CanonicalMetadataResponse> => {
    const { data } = await apiClient.post<CanonicalMetadataResponse>(
      '/api/v1/documents/canonical-metadata',
      { metadata }
    );
    return data;
  },

  getStorageMetadata: async (storageId: string): Promise<StorageMetadataResponse> => {
    const { data } = await apiClient.get<StorageMetadataResponse>(
      `/api/v1/documents/${encodeURIComponent(storageId)}/metadata`
    );
    return data;
  },
};
