export interface ApiErrorDetail {
  loc?: (string | number)[];
  msg?: string;
  type?: string;
}

export interface ApiErrorPayload {
  error_code: string;
  message: string;
  details?: {
    errors?: ApiErrorDetail[];
    [key: string]: unknown;
  };
}

export type NetworkErrorType =
  | 'HTTP_ERROR'
  | 'VALIDATION_ERROR'
  | 'NETWORK_ERROR'
  | 'BLOCKCHAIN_UNAVAILABLE'
  | 'AUTH_UNAUTHORIZED'
  | 'AUTH_FORBIDDEN';

export interface AppError {
  type: NetworkErrorType;
  statusCode?: number;
  errorCode: string;
  message: string;
  details?: ApiErrorDetail[];
  raw?: unknown;
}
