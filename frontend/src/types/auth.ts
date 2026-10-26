export interface AuthPrincipal {
  sub: string;
  roles: string[];
  issuerId?: string;
  verifierId?: string;
  email?: string;
  exp?: number;
}

export type AuthStatus = 'authenticated' | 'unauthenticated' | 'expired' | 'forbidden';

export interface AuthConfig {
  auth_mode: string;
  environment: string;
  dev_mode_available: boolean;
  issuer_url: string;
  audience: string;
  allowed_algorithms: string[];
}

export interface DevTokenParams {
  persona: 'admin' | 'issuer' | 'verifier' | 'custom';
  roles?: string[];
  issuer_id?: string;
  verifier_id?: string;
  sub?: string;
  email?: string;
  exp_seconds?: number;
}

export interface DevTokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  roles: string[];
  sub: string;
  issuer_id?: string;
  verifier_id?: string;
}

export interface AuthContextType {
  user: AuthPrincipal | null;
  token: string | null;
  isAuthenticated: boolean;
  status: AuthStatus;
  hasRole: (role: string) => boolean;
  isIssuer: boolean;
  isAdmin: boolean;
  isVerifier: boolean;
  login: (token: string) => void;
  logout: () => void;
  authError: string | null;
  clearError: () => void;
}
