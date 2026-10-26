import React, { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  Search,
  History,
  ShieldCheck,
  QrCode,
} from 'lucide-react';
import { PageHeader } from '@/components/layout/PageHeader';
import { Bytes32Input } from '@/components/forms/Bytes32Input';
import { HashBadge } from '@/components/status/HashBadge';
import { StatusBadge } from '@/components/status/StatusBadge';
import { VerificationBreakdown } from '@/components/status/VerificationBreakdown';
import { AlertBanner } from '@/components/feedback/AlertBanner';
import { LoadingSpinner } from '@/components/feedback/LoadingSpinner';
import { CredentialQrModal } from '@/components/qr/CredentialQrModal';
import { credentialApi } from '@/services/credentialApi';
import {
  CredentialResponse,
  CredentialVersionResponse,
  VerificationResponse,
} from '@/types/credential';
import { AppError } from '@/types/api';
import { formatDate } from '@/utils/date';
import { isValidBytes32Hex } from '@/utils/cryptoFormat';

export const CredentialDetailsPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const queryParam = searchParams.get('id') || searchParams.get('credential_id') || '';

  const [inputQuery, setInputQuery] = useState(queryParam);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<AppError | null>(null);
  const [isQrModalOpen, setIsQrModalOpen] = useState(false);

  // Loaded data
  const [credential, setCredential] = useState<CredentialResponse | null>(null);
  const [versions, setVersions] = useState<CredentialVersionResponse[]>([]);
  const [verification, setVerification] = useState<VerificationResponse | null>(null);

  const fetchCredentialData = async (identifier: string) => {
    const clean = identifier.trim();
    if (!clean) return;

    if (!isValidBytes32Hex(clean)) {
      setError({
        type: 'VALIDATION_ERROR',
        errorCode: 'INVALID_HEX',
        message: 'Identifier must be a 0x-prefixed 32-byte hexadecimal string (66 characters total).',
      });
      return;
    }

    setIsLoading(true);
    setError(null);
    setCredential(null);
    setVersions([]);
    setVerification(null);

    try {
      // 1. Try resolving as credential_id
      let cred: CredentialResponse;
      try {
        cred = await credentialApi.getCredential(clean);
      } catch (e) {
        // If 404, try querying by fingerprint
        cred = await credentialApi.getCredentialByFingerprint(clean);
      }

      setCredential(cred);
      setSearchParams({ id: cred.credential_id });

      // 2. Fetch version history and live verification concurrently
      const [versionsList, verifyResp] = await Promise.all([
        credentialApi.getCredentialVersions(cred.credential_id).catch(() => []),
        credentialApi.verifyCredential(cred.current_fingerprint).catch(() => null),
      ]);

      setVersions(versionsList);
      setVerification(verifyResp);
    } catch (err) {
      setError(err as AppError);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (queryParam) {
      fetchCredentialData(queryParam);
    }
  }, [queryParam]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    fetchCredentialData(inputQuery);
  };

  return (
    <div className="space-y-8 animate-in fade-in">
      <PageHeader
        title="Credential Lifecycle & Version Inspector"
        description="Inspect multi-version credential histories, on-chain transaction provenance, authoritative composite fingerprints, and cryptographic verification gates."
        breadcrumbs={[{ label: 'Credentials', path: '/credentials' }, { label: 'Lifecycle Inspector' }]}
      />

      {/* Query Bar */}
      <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 space-y-4">
        <form onSubmit={handleSearch} className="space-y-3">
          <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300">
            Query by Credential ID or Composite Fingerprint (32-byte Hex)
          </label>
          <div className="flex gap-2">
            <div className="flex-1">
              <Bytes32Input
                value={inputQuery}
                onChange={setInputQuery}
                placeholder="Enter 32-byte hex Credential ID or Fingerprint..."
              />
            </div>
            <button
              type="submit"
              disabled={isLoading || !inputQuery}
              className="px-5 py-2 bg-brand-600 hover:bg-brand-500 text-white rounded-lg text-xs font-semibold transition-colors disabled:opacity-50 shrink-0 flex items-center gap-1.5"
            >
              {isLoading ? <LoadingSpinner size="sm" /> : <Search className="w-4 h-4" />}
              <span>Inspect</span>
            </button>
          </div>
        </form>

        {error && <AlertBanner error={error} onDismiss={() => setError(null)} />}
      </div>

      {isLoading && <LoadingSpinner label="Querying credential lifecycle record & smart contract..." />}

      {/* Main Details View */}
      {credential && (
        <div className="space-y-6 animate-in fade-in">
          {/* Header Card */}
          <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-6 space-y-6">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-4">
              <div>
                <div className="flex items-center gap-3">
                  <h2 className="text-xl font-bold text-slate-100">Credential Lifecycle Record</h2>
                  <span className="text-xs px-2 py-0.5 rounded bg-brand-950 text-brand-300 border border-brand-800 font-mono">
                    v{credential.current_version}
                  </span>
                </div>
                <div className="mt-2 flex flex-wrap items-center gap-3">
                  <HashBadge hash={credential.credential_id} label="Cred ID" truncate={false} />
                  <HashBadge hash={credential.issuer_id} label="Issuer" truncate />
                </div>
              </div>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setIsQrModalOpen(true)}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-950/60 hover:bg-emerald-950 border border-emerald-800/80 text-emerald-300 text-xs font-medium transition-colors shadow-sm"
                >
                  <QrCode className="w-3.5 h-3.5 text-emerald-400" />
                  <span>View QR Pass</span>
                </button>
                <StatusBadge status={credential.current_status} size="md" />
              </div>
            </div>

            {/* Authoritative Composite Fingerprint */}
            <div className="p-4 bg-slate-950 border border-slate-800 rounded-lg space-y-2">
              <span className="text-xs font-mono uppercase tracking-wider text-slate-400 font-semibold">
                Current Authoritative Composite Fingerprint
              </span>
              <div className="p-2.5 bg-slate-900 rounded border border-slate-750 font-mono text-xs text-brand-300 select-all break-all">
                {credential.current_fingerprint}
              </div>
            </div>

            {/* Timestamps & Issuance Transaction Info */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs text-slate-400">
              <div className="p-3 bg-slate-950/60 rounded border border-slate-800">
                <span className="text-slate-500 block mb-1">Created At</span>
                <span className="text-slate-200 font-mono">{formatDate(credential.created_at)}</span>
              </div>
              <div className="p-3 bg-slate-950/60 rounded border border-slate-800">
                <span className="text-slate-500 block mb-1">Issuance Status</span>
                <span className="text-slate-200 font-mono">{credential.issuance_status}</span>
              </div>
              <div className="p-3 bg-slate-950/60 rounded border border-slate-800">
                <span className="text-slate-500 block mb-1">On-Chain Tx Hash</span>
                <span className="font-mono text-slate-200">
                  {credential.issuance_tx_hash ? (
                    <HashBadge hash={credential.issuance_tx_hash} truncate />
                  ) : (
                    'Not anchored yet'
                  )}
                </span>
              </div>
            </div>
          </div>

          {/* Verification Gates Breakdown */}
          {verification && (
            <div className="space-y-3">
              <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-300 flex items-center gap-2">
                <ShieldCheck className="w-4 h-4 text-brand-400" />
                <span>Authoritative Verification Outcome</span>
              </h3>
              <VerificationBreakdown result={verification} />
            </div>
          )}

          {/* Historical Versions Sequence (Multi-Version Traversal) */}
          {versions.length > 0 && (
            <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-6 space-y-4">
              <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                <div className="flex items-center gap-2">
                  <History className="w-4 h-4 text-brand-400" />
                  <h3 className="text-sm font-semibold text-slate-100">
                    Chronological Version History ({versions.length} versions)
                  </h3>
                </div>
                <span className="text-xs font-mono text-slate-400">Strict Version Monotonicity</span>
              </div>

              <div className="space-y-4">
                {versions.map((ver) => {
                  const isCurrent = ver.version === credential.current_version;
                  return (
                    <div
                      key={ver.version}
                      className={`p-4 rounded-xl border transition-colors ${
                        isCurrent
                          ? 'bg-slate-950/80 border-brand-800/80 shadow-md'
                          : 'bg-slate-950/40 border-slate-800/80 opacity-75'
                      }`}
                    >
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-850 pb-3">
                        <div className="flex items-center gap-2.5">
                          <span className="text-xs font-bold text-slate-100 bg-slate-800 px-2 py-0.5 rounded font-mono">
                            v{ver.version}
                          </span>
                          {isCurrent && (
                            <span className="text-[10px] font-semibold text-brand-400 bg-brand-950 px-2 py-0.5 rounded border border-brand-800">
                              CURRENT
                            </span>
                          )}
                          <span className="text-xs text-slate-400 font-mono">
                            {formatDate(ver.created_at)}
                          </span>
                        </div>

                        <div className="text-xs text-slate-400">
                          Expires: <span className="text-slate-300 font-mono">{formatDate(ver.expires_at)}</span>
                        </div>
                      </div>

                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-3 text-xs">
                        <div>
                          <span className="text-slate-500 font-medium block">Fingerprint:</span>
                          <HashBadge hash={ver.fingerprint} truncate={false} />
                        </div>
                        <div>
                          <span className="text-slate-500 font-medium block">Salted Merkle Root:</span>
                          <HashBadge hash={ver.merkle_root} truncate={false} />
                        </div>
                        <div>
                          <span className="text-slate-500 font-medium block">Document Digest:</span>
                          <HashBadge hash={ver.document_digest} truncate={false} />
                        </div>
                        <div>
                          <span className="text-slate-500 font-medium block">Metadata Digest:</span>
                          <HashBadge hash={ver.metadata_digest} truncate={false} />
                        </div>
                      </div>

                      {ver.superseded_by_fingerprint && (
                        <div className="mt-3 pt-2 border-t border-slate-850 text-xs text-amber-400 flex items-center gap-2 font-mono">
                          <span>Superseded by:</span>
                          <HashBadge hash={ver.superseded_by_fingerprint} truncate />
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* QR Pass Modal */}
          <CredentialQrModal
            isOpen={isQrModalOpen}
            onClose={() => setIsQrModalOpen(false)}
            fingerprint={credential.current_fingerprint}
            credentialId={credential.credential_id}
            version={credential.current_version}
          />
        </div>
      )}
    </div>
  );
};
