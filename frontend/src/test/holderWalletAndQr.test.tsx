import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { HolderWalletPage } from '@/pages/HolderWalletPage';
import { CredentialQrModal } from '@/components/qr/CredentialQrModal';
import { QrScannerModal } from '@/components/qr/QrScannerModal';

// Mock health probe and credential APIs
vi.mock('@/services/healthApi', () => ({
  healthApi: {
    getLiveness: vi.fn().mockResolvedValue({ status: 'live' }),
    getReadiness: vi.fn().mockResolvedValue({ status: 'ready', database: 'connected' }),
  },
}));

vi.mock('@/services/credentialApi', () => ({
  credentialApi: {
    listCredentials: vi.fn().mockResolvedValue([
      {
        credential_id: '0xfc6e5fd58a5741b9110a663efd7dcc5ca18d12ccfb4fcc47d64f98c0d8e2a07a',
        issuer_id: '0xc102e1537a30a64b1fae371152e6c4a6a76e1d5407cfd040a8669bdbff4be231',
        current_version: 1,
        current_fingerprint: '0xa5925f830b0488f75940061910f73c7027a7049e537b229e37d45e7ef438ef77',
        current_status: 'ACTIVE',
        issuance_status: 'CONFIRMED',
        issuance_tx_hash: '78224b80171f9f95e123bbaef362720a173eac04e9d8e52b1ab16ebe3875394d',
        created_at: '2026-10-19T13:17:44.306239Z',
        updated_at: '2026-10-19T13:17:44.306239Z',
      },
    ]),
    getCredential: vi.fn().mockResolvedValue({
      credential_id: '0xfc6e5fd58a5741b9110a663efd7dcc5ca18d12ccfb4fcc47d64f98c0d8e2a07a',
      issuer_id: '0xc102e1537a30a64b1fae371152e6c4a6a76e1d5407cfd040a8669bdbff4be231',
      current_version: 1,
      current_fingerprint: '0xa5925f830b0488f75940061910f73c7027a7049e537b229e37d45e7ef438ef77',
      current_status: 'ACTIVE',
      issuance_status: 'CONFIRMED',
      created_at: '2026-10-19T13:17:44.306239Z',
      updated_at: '2026-10-19T13:17:44.306239Z',
    }),
    getCredentialVersions: vi.fn().mockResolvedValue([
      {
        credential_id: '0xfc6e5fd58a5741b9110a663efd7dcc5ca18d12ccfb4fcc47d64f98c0d8e2a07a',
        version: 1,
        fingerprint: '0xa5925f830b0488f75940061910f73c7027a7049e537b229e37d45e7ef438ef77',
        document_digest: '0x551009ffcfc1499eba8ebe2b114949e1fecd05129403ac74084cc02dc2ad6987',
        metadata_digest: '0x47e9b87fac9e5bbd23b1d57d44264cc73dbf152d0421422c15979c81a3f148f5',
        merkle_root: '0xecd9566a09a9b01c956f75f9ad2e660a44f60df7cb28f2aa9bc04d5d49023dd9',
        expires_at: 0,
        issuance_status: 'CONFIRMED',
        issuance_tx_hash: '78224b80171f9f95e123bbaef362720a173eac04e9d8e52b1ab16ebe3875394d',
        block_number: 11948413,
        chain_id: 11155111,
        created_at: '2026-10-19T13:17:44.306239Z',
      },
    ]),
    verifyCredential: vi.fn().mockResolvedValue({
      fingerprint: '0xa5925f830b0488f75940061910f73c7027a7049e537b229e37d45e7ef438ef77',
      database_found: true,
      blockchain_available: true,
      is_valid: true,
      lifecycle_status: 'ACTIVE',
      is_expired: false,
      digest_match: true,
      blockchain_code: 'VALID',
      details: 'Blockchain verified: status is ACTIVE, verification code is VALID.',
      checked_at: '2026-10-25T11:12:15.315235Z',
    }),
  },
}));

describe('Holder Wallet & QR Verification Workflows', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('renders HolderWalletPage and displays sovereign credential metrics', async () => {
    render(
      <MemoryRouter initialEntries={['/wallet']}>
        <Routes>
          <Route path="/wallet" element={<HolderWalletPage />} />
        </Routes>
      </MemoryRouter>
    );

    expect(screen.getByRole('heading', { name: /Holder Verifiable Credential Wallet/i })).toBeInTheDocument();
    expect(screen.getByText(/Total Held/i)).toBeInTheDocument();
    expect(screen.getByText(/Active & Good Standing/i)).toBeInTheDocument();
    expect(screen.getByText(/Strict Zero-PII/i)).toBeInTheDocument();

    // Verify credential card appears
    await waitFor(() => {
      expect(screen.getByText('v1')).toBeInTheDocument();
      expect(screen.getAllByText(/Sepolia Anchored/i).length).toBeGreaterThanOrEqual(1);
    });
  });

  it('renders CredentialQrModal with zero-PII guarantee badge and action buttons', async () => {
    const handleClose = vi.fn();
    render(
      <CredentialQrModal
        isOpen={true}
        onClose={handleClose}
        fingerprint="0xa5925f830b0488f75940061910f73c7027a7049e537b229e37d45e7ef438ef77"
        credentialId="0xfc6e5fd58a5741b9110a663efd7dcc5ca18d12ccfb4fcc47d64f98c0d8e2a07a"
        version={1}
      />
    );

    expect(screen.getByText(/Verification QR Pass/i)).toBeInTheDocument();
    expect(screen.getByText(/Strict Zero-PII: Encodes only public composite fingerprint/i)).toBeInTheDocument();
    expect(screen.getByText(/Download PNG/i)).toBeInTheDocument();
    expect(screen.getByText(/Copy Link/i)).toBeInTheDocument();
  });

  it('opens and closes QrScannerModal correctly', () => {
    const handleScan = vi.fn();
    const handleClose = vi.fn();

    const { rerender } = render(
      <QrScannerModal isOpen={true} onClose={handleClose} onScan={handleScan} />
    );

    expect(screen.getByText(/Scan Verification QR Code/i)).toBeInTheDocument();
    expect(screen.getByText(/Upload Image/i)).toBeInTheDocument();
    expect(screen.getByText(/Live Camera/i)).toBeInTheDocument();

    // Click close button (first button with svg X)
    const buttons = screen.getAllByRole('button');
    const closeBtn = buttons[0]; // modal top-right close button
    fireEvent.click(closeBtn);
    expect(handleClose).toHaveBeenCalled();

    rerender(<QrScannerModal isOpen={false} onClose={handleClose} onScan={handleScan} />);
    expect(screen.queryByText(/Scan Verification QR Code/i)).not.toBeInTheDocument();
  });
});
