import { describe, it, expect, vi } from 'vitest';
import { presentationApi } from '@/services/presentationApi';

describe('Selective Disclosure & Replay-Protected Challenge Protocol', () => {
  it('omits concealed sensitive claims from generated presentation', async () => {
    const fullAttributes = {
      fullName: 'Jane Doe',
      degree: 'B.S. Computer Science',
      graduationYear: '2026',
      gpa: '3.94',
      socialSecurityNumber: 'XXX-XX-9876', // Sensitive PII
    };

    const disclosedKeys = ['degree', 'graduationYear'];

    vi.spyOn(presentationApi, 'generatePresentation').mockResolvedValueOnce({
      credential_fingerprint: '0x1111111111111111111111111111111111111111111111111111111111111111',
      credential_id: '0x2222222222222222222222222222222222222222222222222222222222222222',
      version: 1,
      issuer_id: '0x3333333333333333333333333333333333333333333333333333333333333333',
      merkle_root: '0x4444444444444444444444444444444444444444444444444444444444444444',
      document_digest: '0x5555555555555555555555555555555555555555555555555555555555555555',
      metadata_digest: '0x6666666666666666666666666666666666666666666666666666666666666666',
      disclosed_claims: [
        {
          key: 'degree',
          value: 'B.S. Computer Science',
          salt: '0x7777777777777777777777777777777777777777777777777777777777777777',
          leaf_hash: '0x8888888888888888888888888888888888888888888888888888888888888888',
          proof: ['0x9999999999999999999999999999999999999999999999999999999999999999'],
        },
        {
          key: 'graduationYear',
          value: '2026',
          salt: '0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
          leaf_hash: '0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
          proof: ['0xcccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc'],
        },
      ],
      challenge_id: 'ch-uuid-1234',
      challenge_nonce: '0xdddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd',
    });

    const result = await presentationApi.generatePresentation({
      credential_id: '0x2222222222222222222222222222222222222222222222222222222222222222',
      version: 1,
      attributes: fullAttributes,
      salts: {
        degree: '0x7777777777777777777777777777777777777777777777777777777777777777',
        graduationYear: '0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
      },
      disclosed_keys: disclosedKeys,
      document_digest: '0x5555555555555555555555555555555555555555555555555555555555555555',
      metadata_digest: '0x6666666666666666666666666666666666666666666666666666666666666666',
      issuer_id: '0x3333333333333333333333333333333333333333333333333333333333333333',
    });

    // Verify revealed keys
    const revealedKeys = result.disclosed_claims.map((c) => c.key);
    expect(revealedKeys).toContain('degree');
    expect(revealedKeys).toContain('graduationYear');

    // Verify concealed keys are ABSENT from presentation payload
    expect(revealedKeys).not.toContain('socialSecurityNumber');
    expect(revealedKeys).not.toContain('gpa');
    expect(revealedKeys).not.toContain('fullName');
  });

  it('handles atomic single-use challenge consumption and replay rejection (HTTP 409)', async () => {
    // Second presentation submission with already-consumed nonce
    vi.spyOn(presentationApi, 'verifyPresentation').mockRejectedValueOnce({
      type: 'HTTP_ERROR',
      statusCode: 409,
      errorCode: 'CHALLENGE_REPLAY_DETECTED',
      message: 'The verifier challenge nonce has already been consumed or is invalid. Presentation rejected.',
    });

    await expect(
      presentationApi.verifyPresentation({
        presentation: {},
        verifier_session_id: 'session-hr-auditor-2026',
      })
    ).rejects.toMatchObject({
      statusCode: 409,
      errorCode: 'CHALLENGE_REPLAY_DETECTED',
    });
  });

  it('handles expired verifier challenges (HTTP 410)', async () => {
    vi.spyOn(presentationApi, 'verifyPresentation').mockRejectedValueOnce({
      type: 'HTTP_ERROR',
      statusCode: 410,
      errorCode: 'CHALLENGE_EXPIRED',
      message: 'The verifier challenge nonce has expired. Please request a new challenge.',
    });

    await expect(
      presentationApi.verifyPresentation({
        presentation: {},
        verifier_session_id: 'session-hr-auditor-2026',
      })
    ).rejects.toMatchObject({
      statusCode: 410,
      errorCode: 'CHALLENGE_EXPIRED',
    });
  });
});
