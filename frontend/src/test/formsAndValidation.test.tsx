import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { IssuersPage } from '@/pages/IssuersPage';
import { issuerCreateSchema } from '@/schemas/issuerSchema';
import { credentialCreateSchema } from '@/schemas/credentialSchema';
import { issuerApi } from '@/services/issuerApi';

vi.mock('@/services/healthApi', () => ({
  healthApi: {
    getLiveness: vi.fn().mockResolvedValue({ status: 'live' }),
    getReadiness: vi.fn().mockResolvedValue({ status: 'ready', database: 'connected', blockchain_rpc: 'connected' }),
  },
}));

describe('Form Validation & Error Handling', () => {
  describe('Zod Schema Validation', () => {
    it('rejects invalid length or non-hex string for bytes32 field', () => {
      const invalidShort = issuerCreateSchema.safeParse({
        issuer_id: '0x123',
        display_name: 'Test University',
        status: 'ACTIVE',
      });
      expect(invalidShort.success).toBe(false);

      const invalidChars = issuerCreateSchema.safeParse({
        issuer_id: '0x' + 'z'.repeat(64),
        display_name: 'Test University',
        status: 'ACTIVE',
      });
      expect(invalidChars.success).toBe(false);
    });

    it('rejects zero address/hash for issuer_id and credential_id', () => {
      const zeroHash = '0x' + '0'.repeat(64);
      const res = issuerCreateSchema.safeParse({
        issuer_id: zeroHash,
        display_name: 'Test University',
        status: 'ACTIVE',
      });
      expect(res.success).toBe(false);
      if (!res.success) {
        expect(res.error.issues[0].message).toMatch(/Zero address\/hash is disallowed/i);
      }
    });

    it('accepts valid 66-character 0x-prefixed 32-byte hex strings', () => {
      const validHash = '0x1111111111111111111111111111111111111111111111111111111111111111';
      const res = issuerCreateSchema.safeParse({
        issuer_id: validHash,
        display_name: 'Accredited University',
        status: 'ACTIVE',
      });
      expect(res.success).toBe(true);
    });

    it('enforces all 5 cryptographic inputs for credential issuance', () => {
      const incomplete = credentialCreateSchema.safeParse({
        credential_id: '0x1111111111111111111111111111111111111111111111111111111111111111',
        issuer_id: '0x2222222222222222222222222222222222222222222222222222222222222222',
        // missing document_digest, metadata_digest, merkle_root
      });
      expect(incomplete.success).toBe(false);
    });
  });

  describe('Duplicate Issuer ID Rejection', () => {
    it('displays API conflict error when issuer already exists in database', async () => {
      vi.spyOn(issuerApi, 'createIssuer').mockRejectedValueOnce({
        type: 'HTTP_ERROR',
        statusCode: 409,
        errorCode: 'ENTITY_CONFLICT',
        message: "Issuer with ID '0x1111111111111111111111111111111111111111111111111111111111111111' already exists in database.",
      });

      render(
        <MemoryRouter>
          <IssuersPage />
        </MemoryRouter>
      );

      const validId = '0x1111111111111111111111111111111111111111111111111111111111111111';
      const idInput = screen.getByPlaceholderText(/0x9a8b.../i);
      const nameInput = screen.getByPlaceholderText(/e.g. Stanford University/i);
      const submitBtn = screen.getByRole('button', { name: /Register Issuer Record/i });

      fireEvent.change(idInput, { target: { value: validId } });
      fireEvent.change(nameInput, { target: { value: 'Duplicate College' } });
      fireEvent.click(submitBtn);

      await waitFor(() => {
        expect(screen.getByText(/already exists in database/i)).toBeInTheDocument();
      });
    });
  });
});
