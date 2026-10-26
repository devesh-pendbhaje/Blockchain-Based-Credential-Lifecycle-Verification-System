import { z } from 'zod';

const BYTES32_REGEX = /^0x[0-9a-fA-F]{64}$/;
const ZERO_BYTES32 = '0x' + '0'.repeat(64);

export const issuerCreateSchema = z.object({
  issuer_id: z
    .string()
    .trim()
    .regex(BYTES32_REGEX, 'Issuer ID must be a 0x-prefixed 32-byte hex string (66 characters total)')
    .refine((val) => val.toLowerCase() !== ZERO_BYTES32, 'Zero address/hash is disallowed for issuer ID'),
  display_name: z
    .string()
    .trim()
    .min(1, 'Display name is required')
    .max(255, 'Display name cannot exceed 255 characters'),
  metadata_uri: z
    .string()
    .trim()
    .max(1024, 'Metadata URI cannot exceed 1024 characters')
    .optional()
    .or(z.literal('')),
  status: z.enum(['ACTIVE', 'SUSPENDED', 'REVOKED']).default('ACTIVE'),
});

export type IssuerCreateFormValues = z.infer<typeof issuerCreateSchema>;
