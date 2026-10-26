import { z } from 'zod';

const BYTES32_REGEX = /^0x[0-9a-fA-F]{64}$/;
const ZERO_BYTES32 = '0x' + '0'.repeat(64);

const bytes32Field = (name: string) =>
  z
    .string()
    .trim()
    .regex(BYTES32_REGEX, `${name} must be a 0x-prefixed 32-byte hex string (66 characters total)`)
    .refine((val) => val.toLowerCase() !== ZERO_BYTES32, `${name} cannot be the zero hash`);

export const credentialCreateSchema = z.object({
  credential_id: bytes32Field('Credential ID'),
  issuer_id: bytes32Field('Issuer ID'),
  document_digest: bytes32Field('Document Digest'),
  metadata_digest: bytes32Field('Metadata Digest'),
  merkle_root: bytes32Field('Merkle Root'),
  version: z.coerce.number().int().min(1, 'Version must be an integer >= 1').default(1),
  expires_at: z.coerce.number().int().min(0, 'Expiration must be a valid non-negative Unix timestamp').default(0),
  idempotency_key: z.string().trim().max(128).optional().or(z.literal('')),
});

export type CredentialCreateFormValues = z.infer<typeof credentialCreateSchema>;

export const fingerprintQuerySchema = z.object({
  fingerprint: bytes32Field('Credential Fingerprint'),
});
