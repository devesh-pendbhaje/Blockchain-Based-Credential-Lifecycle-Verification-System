import axios from 'axios';
import { AppError, ApiErrorPayload } from '@/types/api';

export function parseApiError(err: unknown): AppError {
  if (axios.isAxiosError(err)) {
    // Network / connection error (e.g. backend server down)
    if (!err.response) {
      return {
        type: 'NETWORK_ERROR',
        errorCode: 'NETWORK_OFFLINE',
        message: err.message || 'Unable to connect to the backend server. Verify that FastAPI is running.',
        raw: err,
      };
    }

    const status = err.response.status;
    const data = err.response.data as ApiErrorPayload | undefined;

    // Check if error payload conforms to FastAPI centralized error structure
    if (data && typeof data === 'object') {
      const errorCode = data.error_code || `HTTP_${status}`;
      const message = data.message || err.message || 'An unexpected API error occurred.';
      const errors = data.details?.errors;

      let type: AppError['type'] = 'HTTP_ERROR';
      if (status === 401) {
        type = 'AUTH_UNAUTHORIZED';
      } else if (status === 403) {
        type = 'AUTH_FORBIDDEN';
      } else if (status === 422 || errorCode === 'VALIDATION_ERROR') {
        type = 'VALIDATION_ERROR';
      } else if (errorCode.includes('BLOCKCHAIN')) {
        type = 'BLOCKCHAIN_UNAVAILABLE';
      }

      return {
        type,
        statusCode: status,
        errorCode,
        message,
        details: Array.isArray(errors) ? errors : undefined,
        raw: data,
      };
    }

    // Generic HTTP error without standardized payload
    let type: AppError['type'] = 'HTTP_ERROR';
    if (status === 401) type = 'AUTH_UNAUTHORIZED';
    else if (status === 403) type = 'AUTH_FORBIDDEN';

    return {
      type,
      statusCode: status,
      errorCode: `HTTP_${status}`,
      message: err.message || `Request failed with status code ${status}`,
      raw: err.response.data,
    };
  }

  if (err instanceof Error) {
    return {
      type: 'HTTP_ERROR',
      errorCode: 'CLIENT_ERROR',
      message: err.message,
      raw: err,
    };
  }

  return {
    type: 'HTTP_ERROR',
    errorCode: 'UNKNOWN_ERROR',
    message: String(err) || 'An unknown error occurred.',
    raw: err,
  };
}
