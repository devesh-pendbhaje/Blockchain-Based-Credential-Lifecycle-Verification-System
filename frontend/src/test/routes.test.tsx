import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { AppLayout } from '@/components/layout/AppLayout';
import { DashboardPage } from '@/pages/DashboardPage';
import { IssuersPage } from '@/pages/IssuersPage';
import { CredentialIssuancePage } from '@/pages/CredentialIssuancePage';
import { CredentialDetailsPage } from '@/pages/CredentialDetailsPage';
import { VerificationPage } from '@/pages/VerificationPage';
import { SelectiveDisclosurePage } from '@/pages/SelectiveDisclosurePage';
import { StoredDocumentsPage } from '@/pages/StoredDocumentsPage';
import { NotFoundPage } from '@/pages/NotFoundPage';

// Mock health probe API to return healthy
vi.mock('@/services/healthApi', () => ({
  healthApi: {
    getLiveness: vi.fn().mockResolvedValue({ status: 'live' }),
    getReadiness: vi.fn().mockResolvedValue({
      status: 'ready',
      database: 'connected',
      blockchain_rpc: 'connected',
    }),
  },
}));

describe('Route Rendering & Application Shell', () => {
  const renderWithRoute = (initialPath: string) => {
    return render(
      <MemoryRouter initialEntries={[initialPath]}>
        <Routes>
          <Route path="/" element={<AppLayout />}>
            <Route index element={<DashboardPage />} />
            <Route path="issuers" element={<IssuersPage />} />
            <Route path="credentials" element={<CredentialDetailsPage />} />
            <Route path="credentials/issue" element={<CredentialIssuancePage />} />
            <Route path="verify" element={<VerificationPage />} />
            <Route path="presentations" element={<SelectiveDisclosurePage />} />
            <Route path="documents" element={<StoredDocumentsPage />} />
            <Route path="*" element={<NotFoundPage />} />
          </Route>
        </Routes>
      </MemoryRouter>
    );
  };

  it('renders DashboardPage at root path "/"', () => {
    renderWithRoute('/');
    expect(screen.getByText(/Decentralized Credential Lifecycle Platform/i)).toBeInTheDocument();
    expect(screen.getByText(/Infrastructure Connectivity/i)).toBeInTheDocument();
  });

  it('renders IssuersPage at "/issuers"', () => {
    renderWithRoute('/issuers');
    expect(screen.getByRole('heading', { name: /Issuer Management & Registry/i })).toBeInTheDocument();
    expect(screen.getByText(/Create Issuer Profile/i)).toBeInTheDocument();
  });

  it('renders CredentialIssuancePage at "/credentials/issue"', () => {
    renderWithRoute('/credentials/issue');
    expect(screen.getByRole('heading', { name: /Guided Credential Issuance/i })).toBeInTheDocument();
    expect(screen.getByText(/Step 1: Credential & Issuer Identifiers/i)).toBeInTheDocument();
  });

  it('renders CredentialDetailsPage at "/credentials"', () => {
    renderWithRoute('/credentials');
    expect(screen.getByRole('heading', { name: /Credential Lifecycle & Version Inspector/i })).toBeInTheDocument();
  });

  it('renders VerificationPage at "/verify"', () => {
    renderWithRoute('/verify');
    expect(screen.getByRole('heading', { name: /Public Credential Verification Portal/i })).toBeInTheDocument();
    expect(screen.getByText(/Zero-Trust Credential Query/i)).toBeInTheDocument();
  });

  it('renders SelectiveDisclosurePage at "/presentations"', () => {
    renderWithRoute('/presentations');
    expect(screen.getByRole('heading', { name: /Privacy-Preserving Selective Disclosure/i })).toBeInTheDocument();
    expect(screen.getByText(/Issue Verifier Challenge/i)).toBeInTheDocument();
  });

  it('renders StoredDocumentsPage at "/documents"', () => {
    renderWithRoute('/documents');
    expect(screen.getByRole('heading', { name: /Encrypted Off-Chain Storage & Cryptographic Primitives/i })).toBeInTheDocument();
  });

  it('renders NotFoundPage on unmapped routes', () => {
    renderWithRoute('/non-existent-route-xyz');
    expect(screen.getByText(/404: Endpoint Route Not Found/i)).toBeInTheDocument();
  });
});
