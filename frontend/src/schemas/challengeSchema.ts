import { z } from 'zod';

const BYTES32_REGEX = /^0x[0-9a-fA-F]{64}$/;

export const challengeCreateSchema = z.object({
  verifier_session_id: z
    .string()
    .trim()
    .min(1, 'Verifier Session ID is required')
    .max(128, 'Session ID cannot exceed 128 characters'),
  credential_fingerprint: z
    .string()
    .trim()
    .regex(BYTES32_REGEX, 'Fingerprint must be a 0x-prefixed 32-byte hex string')
    .optional()
    .or(z.literal('')),
  expiry_seconds: z.coerce.number().int().min(10, 'Minimum expiry is 10s').max(3600, 'Maximum expiry is 3600s').default(300),
});

export type ChallengeCreateFormValues = z.infer<typeof challengeCreateSchema>;
