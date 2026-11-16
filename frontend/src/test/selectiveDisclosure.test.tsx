import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import apiClient from '@/services/apiClient';
import { presentationApi } from '@/services/presentationApi';
import { SelectiveDisclosurePage } from '@/pages/SelectiveDisclosurePage';
import { holderPackages } from '@/services/holderPackages';
import { CredentialPackage } from '@/types/credential';

describe('Selective Disclosure Protocol & UI Verification', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    holderPackages.clear();
  });

  const samplePackage: CredentialPackage = {
    credential_id: '0x2222222222222222222222222222222222222222222222222222222222222222',
    issuer_id: '0x3333333333333333333333333333333333333333333333333333333333333333',
    version: 1,
    fingerprint: '0x1111111111111111111111111111111111111111111111111111111111111111',
    document_digest: '0x5555555555555555555555555555555555555555555555555555555555555555',
    metadata_digest: '0x6666666666666666666666666666666666666666666666666666666666666666',
    merkle_root: '0x4444444444444444444444444444444444444444444444444444444444444444',
    attributes: {
      fullName: 'Jane Doe',
      degree: 'B.S. Computer Science',
      graduationYear: '2026',
      gpa: '3.94',
      socialSecurityNumber: 'XXX-XX-9876',
    },
    salts: {
      fullName: '0x0101010101010101010101010101010101010101010101010101010101010101',
      degree: '0x0202020202020202020202020202020202020202020202020202020202020202',
      graduationYear: '0x0303030303030303030303030303030303030303030303030303030303030303',
      gpa: '0x0404040404040404040404040404040404040404040404040404040404040404',
      socialSecurityNumber: '0x0505050505050505050505050505050505050505050505050505050505050505',
    },
    created_at: new Date().toISOString(),
  };

  it('presentationApi.generatePresentation invokes backend with exact typed payload', async () => {
    const postSpy = vi.spyOn(apiClient, 'post').mockResolvedValueOnce({
      data: {
        credential_fingerprint: samplePackage.fingerprint,
        credential_id: samplePackage.credential_id,
        version: 1,
        issuer_id: samplePackage.issuer_id,
        merkle_root: samplePackage.merkle_root,
        document_digest: samplePackage.document_digest,
        metadata_digest: samplePackage.metadata_digest,
        disclosed_claims: [
          {
            key: 'degree',
            value: 'B.S. Computer Science',
            salt: samplePackage.salts.degree,
            leaf_hash: '0x8888',
            proof: ['0x9999'],
          },
        ],
      },
    });

    const requestPayload = {
      credential_id: samplePackage.credential_id,
      version: 1,
      attributes: samplePackage.attributes,
      salts: samplePackage.salts,
      disclosed_keys: ['degree'],
      document_digest: samplePackage.document_digest,
      metadata_digest: samplePackage.metadata_digest,
      issuer_id: samplePackage.issuer_id,
      challenge_id: 'ch-test-123',
      challenge_nonce: '0xnonce123',
    };

    const res = await presentationApi.generatePresentation(requestPayload);

    expect(postSpy).toHaveBeenCalledWith('/api/v1/presentations/generate', requestPayload);
    expect(res.credential_id).toBe(samplePackage.credential_id);
    expect(res.disclosed_claims).toHaveLength(1);
    expect(res.disclosed_claims[0].key).toBe('degree');
  });

  it('presentationApi.verifyPresentation correctly serializes request to backend endpoint', async () => {
    const postSpy = vi.spyOn(apiClient, 'post').mockResolvedValueOnce({
      data: {
        overall_valid: true,
        selective_disclosure_valid: true,
        disclosed_attributes: { degree: 'B.S. Computer Science' },
        challenge_verified: true,
        fingerprint_verified: true,
        database_status: 'ACTIVE',
        is_current_version: true,
        blockchain_verification: {
          available: true,
          authoritative_verification_available: true,
          on_chain_valid: true,
          code: 'VALID',
        },
        privacy_notice: 'Standard disclosure.',
      },
    });

    const verifyReq = {
      presentation: { credential_id: samplePackage.credential_id },
      verifier_session_id: 'session-hr-auditor-2026',
      require_current_version: true,
    };

    const res = await presentationApi.verifyPresentation(verifyReq);

    expect(postSpy).toHaveBeenCalledWith('/api/v1/presentations/verify', verifyReq);
    expect(res.overall_valid).toBe(true);
    expect(res.blockchain_verification.code).toBe('VALID');
  });

  it('renders attributes and allows toggling disclosure in Step 2', async () => {
    holderPackages.add(samplePackage);
    render(
      <MemoryRouter initialEntries={['/presentations']}>
        <SelectiveDisclosurePage />
      </MemoryRouter>
    );

    // Switch to Step 2 Tab
    const step2Tab = screen.getByText(/2. Holder presentation/i);
    fireEvent.click(step2Tab);

    expect(screen.getByText('socialSecurityNumber')).toBeInTheDocument();
    const degree = screen.getByRole('checkbox', {name: /degree/});
    expect(degree).not.toBeChecked();
    fireEvent.click(degree);
    expect(degree).toBeChecked();
    expect(screen.getByRole('checkbox', {name: /socialSecurityNumber/})).not.toBeChecked();
    expect(window.history.state || {}).not.toHaveProperty('credentialPackage');

  });

  it('requires an imported presentation before verification', async () => {
    vi.spyOn(presentationApi, 'verifyPresentation').mockResolvedValueOnce({
      overall_valid: false,
      selective_disclosure_valid: true,
      disclosed_attributes: { degree: 'B.S. Computer Science' },
      challenge_verified: true,
      fingerprint_verified: true,
      database_status: 'ACTIVE',
      is_current_version: true,
      blockchain_verification: {
        available: false,
        authoritative_verification_available: false,
        is_connected: false,
        code: 'UNAVAILABLE',
        on_chain_valid: false,
      },
      privacy_notice: 'Offline warning',
    });

    holderPackages.add(samplePackage);
    render(
      <MemoryRouter initialEntries={['/presentations']}>
        <SelectiveDisclosurePage />
      </MemoryRouter>
    );

    // Advance to Step 3
    const step3Tab = screen.getByText(/3. Verify presentation/i);
    fireEvent.click(step3Tab);

    // Since presentation is null initially, we verify button is disabled until presentation exists
    const verifyButton = screen.getByRole('button', { name: /^Verify presentation$/i });
    expect(verifyButton).toBeDisabled();
  });
});
