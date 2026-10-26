import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { VerificationBreakdown } from '@/components/status/VerificationBreakdown';
import { VerificationResponse } from '@/types/credential';

describe('Authoritative Verification Gates & Honest Reporting', () => {
  const baseResponse: VerificationResponse = {
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

  it('renders "Authoritative Verification: VALID" when all gates pass', () => {
    render(<VerificationBreakdown result={baseResponse} />);
    expect(screen.getByText(/Authoritative Verification: VALID/i)).toBeInTheDocument();
    expect(screen.getByText(/Verified Valid/i)).toBeInTheDocument();
  });

  it('NEVER reports valid when blockchain verification is unavailable (Honest Verification Boundary)', () => {
    const blockchainOffline: VerificationResponse = {
      ...baseResponse,
      blockchain_available: false,
      is_valid: false,
      details: 'Blockchain node is offline or unreachable. Verification cannot be confirmed.',
    };

    render(<VerificationBreakdown result={blockchainOffline} />);

    // Must NOT state "VALID"
    expect(screen.queryByText(/Authoritative Verification: VALID/i)).not.toBeInTheDocument();
    // Must explicitly highlight incomplete verification
    expect(screen.getByText(/Verification Incomplete: BLOCKCHAIN UNAVAILABLE/i)).toBeInTheDocument();
    // Must display the honest verification warning
    expect(screen.getByText(/Honest Verification Notice:/i)).toBeInTheDocument();
    expect(screen.getByText(/be certified as verified without live on-chain state confirmation/i)).toBeInTheDocument();
  });

  it('displays INVALID when credential has dynamically expired', () => {
    const expiredCred: VerificationResponse = {
      ...baseResponse,
      is_valid: false,
      is_expired: true,
      blockchain_code: 'Expired (4)',
      details: 'Credential expiration timestamp has elapsed dynamically against current block timestamp.',
    };

    render(<VerificationBreakdown result={expiredCred} />);
    expect(screen.getByText(/Authoritative Verification: INVALID/i)).toBeInTheDocument();
    expect(screen.getByText('Expired')).toBeInTheDocument();
  });

  it('displays INVALID when credential has been suspended or revoked', () => {
    const revokedCred: VerificationResponse = {
      ...baseResponse,
      is_valid: false,
      lifecycle_status: 'REVOKED',
      blockchain_code: 'InvalidStoredStatus (3)',
      details: 'Credential has been permanently revoked by issuing institution.',
    };

    render(<VerificationBreakdown result={revokedCred} />);
    expect(screen.getByText(/Authoritative Verification: INVALID/i)).toBeInTheDocument();
    expect(screen.getByText('REVOKED')).toBeInTheDocument();
  });

  it('displays INVALID when document, metadata, or Merkle root digest mismatch occurs', () => {
    const tamperedCred: VerificationResponse = {
      ...baseResponse,
      is_valid: false,
      digest_match: false,
      blockchain_code: 'HashMismatch (2)',
      details: 'Computed composite fingerprint does not match on-chain registered fingerprint.',
    };

    render(<VerificationBreakdown result={tamperedCred} />);
    expect(screen.getByText(/Authoritative Verification: INVALID/i)).toBeInTheDocument();
    expect(screen.getByText('Hash Mismatch')).toBeInTheDocument();
  });
});
