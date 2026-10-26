import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { AuthProvider } from '@/context/AuthContext';
import { AuthIndicator } from '@/components/auth/AuthIndicator';
import { IssuersPage } from '@/pages/IssuersPage';
import { VerificationPage } from '@/pages/VerificationPage';
import { authApi } from '@/services/authApi';
import { credentialApi } from '@/services/credentialApi';
import { VerificationResponse } from '@/types/credential';
import { tokenStore } from '@/services/tokenStore';

vi.mock('@/services/authApi', () => ({
  authApi: {
    getAuthConfig: vi.fn().mockResolvedValue({
      auth_mode: 'oidc',
      environment: 'development',
      dev_mode_available: true,
      issuer_url: 'https://auth.institutional-consortium.org/realms/credentials',
      audience: 'blockchain-credential-api',
      allowed_algorithms: ['RS256'],
    }),
    getDevToken: vi.fn().mockImplementation(async ({ persona }) => {
      // Create a mock RS256 token payload
      const header = btoa(JSON.stringify({ alg: 'RS256', typ: 'JWT', kid: 'local-dev-rsa-1' }));
      const now = Math.floor(Date.now() / 1000);
      let payloadObj = {
        sub: persona === 'admin' ? 'admin-sec-ops' : persona === 'issuer' ? 'issuer-authority-01' : 'verifier-auditor-01',
        roles: persona === 'admin' ? ['admin', 'issuer', 'verifier'] : [persona],
        iss: 'https://auth.institutional-consortium.org/realms/credentials',
        aud: 'blockchain-credential-api',
        iat: now,
        exp: now + 7200,
      };
      const payload = btoa(JSON.stringify(payloadObj));
      return {
        access_token: `${header}.${payload}.mock-signature-boundary`,
        token_type: 'Bearer',
        expires_in: 7200,
        roles: payloadObj.roles,
        sub: payloadObj.sub,
      };
    }),
  },
}));

vi.mock('@/services/issuerApi', () => ({
  issuerApi: {
    createIssuer: vi.fn(),
    getIssuer: vi.fn(),
    getIssuerStatus: vi.fn(),
  },
}));

describe('Frontend Authentication Flow', () => {
  beforeEach(() => {
    tokenStore.clearToken();
    vi.clearAllMocks();
  });

  it('renders "Sign In" button when unauthenticated in AuthIndicator', () => {
    render(
      <AuthProvider>
        <AuthIndicator />
      </AuthProvider>
    );

    const signInBtn = screen.getByTestId('sign-in-btn');
    expect(signInBtn).toBeInTheDocument();
    expect(signInBtn).toHaveTextContent(/sign in/i);
  });

  it('opens AuthModal upon clicking "Sign In"', async () => {
    render(
      <AuthProvider>
        <AuthIndicator />
      </AuthProvider>
    );

    const signInBtn = screen.getByTestId('sign-in-btn');
    fireEvent.click(signInBtn);

    expect(screen.getByText(/Institutional Identity & Authentication/i)).toBeInTheDocument();
    expect(screen.getByText(/System Administrator/i)).toBeInTheDocument();
    expect(screen.getByText(/Accredited Institutional Issuer/i)).toBeInTheDocument();
  });

  it('signs in as System Administrator and displays authenticated user in AuthIndicator', async () => {
    render(
      <AuthProvider>
        <AuthIndicator />
      </AuthProvider>
    );

    // Open modal
    fireEvent.click(screen.getByTestId('sign-in-btn'));

    // Click System Administrator persona
    const adminPersonaBtn = screen.getByText(/System Administrator/i).closest('button');
    expect(adminPersonaBtn).not.toBeNull();
    fireEvent.click(adminPersonaBtn!);

    await waitFor(() => {
      expect(authApi.getDevToken).toHaveBeenCalledWith({ persona: 'admin' });
      expect(screen.getByText('admin-sec-ops')).toBeInTheDocument();
    });
  });

  it('displays authentication required banner on IssuersPage when unauthenticated', () => {
    render(
      <AuthProvider>
        <MemoryRouter>
          <IssuersPage />
        </MemoryRouter>
      </AuthProvider>
    );

    expect(screen.getByText(/Institutional Authentication Required/i)).toBeInTheDocument();
  });

  it('allows unauthenticated verification queries on VerificationPage without authentication barrier', async () => {
    const mockVerificationResult: VerificationResponse = {
      fingerprint: '0x1111111111111111111111111111111111111111111111111111111111111111',
      database_found: true,
      blockchain_available: true,
      is_valid: true,
      lifecycle_status: 'ACTIVE',
      is_expired: false,
      digest_match: true,
      blockchain_code: 'Valid (0)',
      details: 'Credential is valid, active, and cryptographically verified on-chain.',
      checked_at: new Date().toISOString(),
    };

    const verifySpy = vi.spyOn(credentialApi, 'verifyCredential').mockResolvedValueOnce(mockVerificationResult);

    render(
      <AuthProvider>
        <MemoryRouter initialEntries={['/verify?fingerprint=0x1111111111111111111111111111111111111111111111111111111111111111']}>
          <VerificationPage />
        </MemoryRouter>
      </AuthProvider>
    );

    expect(screen.getByRole('heading', { name: /Public Credential Verification Portal/i })).toBeInTheDocument();
    expect(screen.queryByText(/Institutional Authentication Required/i)).not.toBeInTheDocument();

    await waitFor(() => {
      expect(verifySpy).toHaveBeenCalledWith('0x1111111111111111111111111111111111111111111111111111111111111111');
      expect(screen.getByText(/Authoritative Verification: VALID/i)).toBeInTheDocument();
    });
  });
});
