import axios, { AxiosError, AxiosInstance, InternalAxiosRequestConfig } from 'axios';
import { parseApiError } from '@/utils/errorParser';

import { tokenStore } from '@/services/tokenStore';

// Base URL configured through Vite environment variable
const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export const apiClient: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  timeout: 15000,
  headers: {
    'Accept': 'application/json',
  },
});

// Request Interceptor: Attach in-memory bearer token if present; avoid logging sensitive bodies
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = tokenStore.getToken();
    if (token && !config.headers.Authorization) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error: AxiosError) => {
    return Promise.reject(parseApiError(error));
  }
);

// Response Interceptor: Format errors consistently and clear expired session on 401
apiClient.interceptors.response.use(
  (response) => {
    return response;
  },
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      // Clear in-memory token when backend rejects as unauthorized/expired
      tokenStore.clearToken();
    }
    const parsed = parseApiError(error);
    return Promise.reject(parsed);
  }
);

export default apiClient;
