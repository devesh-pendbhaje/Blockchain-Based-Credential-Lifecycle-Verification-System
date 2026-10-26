import React, { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  ShieldCheck,
  QrCode,
  Info,
  Sparkles,
} from 'lucide-react';
import { PageHeader } from '@/components/layout/PageHeader';
import { Bytes32Input } from '@/components/forms/Bytes32Input';
import { VerificationBreakdown } from '@/components/status/VerificationBreakdown';
import { AlertBanner } from '@/components/feedback/AlertBanner';
import { LoadingSpinner } from '@/components/feedback/LoadingSpinner';
import { credentialApi } from '@/services/credentialApi';
import { VerificationResponse } from '@/types/credential';
import { AppError } from '@/types/api';
import { isValidBytes32Hex } from '@/utils/cryptoFormat';
import { QrScannerModal } from '@/components/qr/QrScannerModal';

export const VerificationPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const initialFp = searchParams.get('fingerprint') || '';

  const [fingerprintInput, setFingerprintInput] = useState(initialFp);
  const [isVerifying, setIsVerifying] = useState(false);
  const [isScannerOpen, setIsScannerOpen] = useState(false);
  const [verificationResult, setVerificationResult] = useState<VerificationResponse | null>(null);
  const [error, setError] = useState<AppError | null>(null);

  const performVerification = async (fp: string) => {
    const cleanFp = fp.trim();
    if (!cleanFp) return;

    if (!isValidBytes32Hex(cleanFp)) {
      setError({
        type: 'VALIDATION_ERROR',
        errorCode: 'INVALID_FINGERPRINT',
        message: 'Fingerprint must be a 0x-prefixed 32-byte hexadecimal string (66 characters total).',
      });
      return;
    }

    setIsVerifying(true);
    setError(null);
    setVerificationResult(null);

    try {
      const resp = await credentialApi.verifyCredential(cleanFp);
      setVerificationResult(resp);
      setSearchParams({ fingerprint: cleanFp });
    } catch (err) {
      setError(err as AppError);
    } finally {
      setIsVerifying(false);
    }
  };

  useEffect(() => {
    if (initialFp) {
      performVerification(initialFp);
    }
  }, [initialFp]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    performVerification(fingerprintInput);
  };

  // Sample test vector from Phase 1 / Phase 2 unit tests for verifier convenience
  const sampleTestVector = '0x1111111111111111111111111111111111111111111111111111111111111111';

  return (
    <div className="space-y-8 animate-in fade-in">
      <PageHeader
        title="Public Credential Verification Portal"
        description="Zero-trust cryptographic verification. Inspects on-chain smart contract validity, dynamic block-timestamp expiration, off-chain digest matching, and institutional issuer standing."
        breadcrumbs={[{ label: 'Verification' }]}
      />

      {/* Verification Query Bar */}
      <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-6 space-y-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800 pb-3">
          <div className="flex items-center gap-2">
            <ShieldCheck className="w-5 h-5 text-brand-400" />
            <h2 className="text-base font-semibold text-slate-100">Zero-Trust Credential Query</h2>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setIsScannerOpen(true)}
              className="text-[11px] text-emerald-400 hover:text-emerald-300 bg-emerald-950/60 hover:bg-emerald-950 border border-emerald-800/80 px-2.5 py-1 rounded transition-colors flex items-center gap-1.5 font-mono"
            >
              <QrCode className="w-3.5 h-3.5 text-emerald-400" />
              <span>Scan QR Code</span>
            </button>
            <button
              type="button"
              onClick={() => {
                setFingerprintInput(sampleTestVector);
                performVerification(sampleTestVector);
              }}
              className="text-[11px] text-brand-400 hover:text-brand-300 bg-brand-950/60 hover:bg-brand-950 border border-brand-800/80 px-2.5 py-1 rounded transition-colors flex items-center gap-1 font-mono"
            >
              <Sparkles className="w-3 h-3 text-brand-400" />
              <span>Load Sample Test Vector</span>
            </button>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300">
              Composite Credential Fingerprint (0x + 64 Hex Digits)
            </label>
            <div className="flex gap-2">
              <div className="flex-1">
                <Bytes32Input
                  value={fingerprintInput}
                  onChange={setFingerprintInput}
                  placeholder="Enter 0x... 32-byte composite fingerprint to verify"
                />
              </div>
              <button
                type="submit"
                disabled={isVerifying || !fingerprintInput}
                className="px-6 py-2 bg-brand-600 hover:bg-brand-500 text-white rounded-lg text-xs font-semibold tracking-wide transition-colors disabled:opacity-50 shrink-0 flex items-center gap-2 shadow-lg shadow-brand-950"
              >
                {isVerifying ? <LoadingSpinner size="sm" /> : <ShieldCheck className="w-4 h-4" />}
                <span>Verify Credential</span>
              </button>
            </div>
          </div>
        </form>

        {/* QR Code Scanner Bar */}
        <div className="pt-2 flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs text-slate-400 border-t border-slate-800/60">
          <div className="flex items-center gap-2">
            <QrCode className="w-4 h-4 text-emerald-400" />
            <span>
              Hardware & Image QR Verification: <em>Active</em> (Instant zero-trust resolution via camera or image upload).
            </span>
          </div>
          <button
            type="button"
            onClick={() => setIsScannerOpen(true)}
            className="text-xs text-emerald-400 hover:text-emerald-300 font-medium hover:underline flex items-center gap-1 shrink-0"
          >
            <span>Open QR Scanner</span>
          </button>
        </div>

        {error && <AlertBanner error={error} onDismiss={() => setError(null)} />}

        {/* QR Scanner Modal */}
        <QrScannerModal
          isOpen={isScannerOpen}
          onClose={() => setIsScannerOpen(false)}
          onScan={(fp) => {
            setFingerprintInput(fp);
            performVerification(fp);
          }}
        />
      </div>

      {isVerifying && (
        <LoadingSpinner label="Querying smart contract verification logic & database integrity..." />
      )}

      {/* Authoritative Verification Breakdown Component */}
      {verificationResult && (
        <div className="space-y-6 animate-in fade-in">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-300">
              Authoritative Gate Evaluation
            </h3>
            <span className="text-xs font-mono text-slate-500">
              Zero-Trust Evaluation Engine
            </span>
          </div>

          <VerificationBreakdown result={verificationResult} />

          {/* Verifier Operational Guidelines */}
          <div className="p-5 bg-slate-900/40 border border-slate-800 rounded-xl space-y-3 text-xs text-slate-400">
            <div className="flex items-center gap-2 text-slate-200 font-semibold">
              <Info className="w-4 h-4 text-brand-400" />
              <span>Verifier Interpretation Guide</span>
            </div>
            <ul className="list-disc list-inside space-y-1.5 leading-relaxed">
              <li>
                <strong className="text-slate-300">Valid:</strong> The credential exists, is active in the registry, unexpired dynamically against the current block timestamp, matches the cryptographic digests, and the issuing institution is in good standing.
              </li>
              <li>
                <strong className="text-slate-300">Blockchain Unavailable:</strong> If the EVM node is disconnected, the system reports this limitation explicitly and <span className="text-amber-400 font-semibold">will never</span> declare the credential verified.
              </li>
              <li>
                <strong className="text-slate-300">Suspended / Revoked:</strong> A credential or issuer that has been suspended or revoked will return <code>is_valid: false</code> with immutable reason codes.
              </li>
            </ul>
          </div>
        </div>
      )}
    </div>
  );
};
