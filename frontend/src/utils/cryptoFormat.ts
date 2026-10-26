/**
 * Utilities for formatting, validating, and generating 32-byte hexadecimal strings
 * used across EVM smart contracts, Merkle trees, and cryptographic digests.
 */

export function isValidBytes32Hex(value: string | undefined | null): boolean {
  if (!value) return false;
  const trimmed = value.trim();
  return /^0x[0-9a-fA-F]{64}$/.test(trimmed) && trimmed !== '0x' + '0'.repeat(64);
}

export function normalizeBytes32Hex(value: string): string {
  const trimmed = value.trim().toLowerCase();
  if (trimmed.startsWith('0x')) {
    return trimmed;
  }
  return `0x${trimmed}`;
}

export function formatHash(hash: string | null | undefined, lead = 8, trail = 6): string {
  if (!hash) return '—';
  const clean = hash.trim();
  if (clean.length <= lead + trail + 2) return clean;
  return `${clean.substring(0, lead + 2)}…${clean.substring(clean.length - trail)}`;
}

export function generateRandomBytes32(): string {
  const bytes = new Uint8Array(32);
  window.crypto.getRandomValues(bytes);
  return '0x' + Array.from(bytes).map(b => b.toString(16).padStart(2, '0')).join('');
}

export async function copyToClipboard(text: string): Promise<boolean> {
  try {
    if (navigator?.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return true;
    }
    return false;
  } catch {
    return false;
  }
}
