import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Wallet,
  ShieldCheck,
  QrCode,
  EyeOff,
  History,
  Plus,
  RefreshCw,
  CheckCircle2,
  AlertCircle,
  FileCheck2,
  Search,
} from 'lucide-react';
import { PageHeader } from '@/components/layout/PageHeader';
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

const WALLET_STORAGE_KEY = 'holder_wallet_credential_ids';
const DEFAULT_DEMO_CREDENTIAL = '0xa5925f830b0488f75940061910f73c7027a7049e537b229e37d45e7ef438ef77';

export const HolderWalletPage: React.FC = () => {
  const navigate = useNavigate();

  // State
  const [credentials, setCredentials] = useState<CredentialResponse[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<AppError | null>(null);
  const [searchFilter, setSearchFilter] = useState('');

  // Import state
  const [isImporting, setIsImporting] = useState(false);
  const [importQuery, setImportQuery] = useState('');
  const [importError, setImportError] = useState<string | null>(null);

  // Detail Modal / Inspector
  const [selectedCredential, setSelectedCredential] = useState<CredentialResponse | null>(null);
  const [selectedVersions, setSelectedVersions] = useState<CredentialVersionResponse[]>([]);
  const [selectedVerification, setSelectedVerification] = useState<VerificationResponse | null>(null);
  const [isDetailLoading, setIsDetailLoading] = useState(false);

  // QR Modal
  const [qrModalCredential, setQrModalCredential] = useState<CredentialResponse | null>(null);

  // Load Wallet credentials
  const loadWallet = async () => {
    setIsLoading(true);
    setError(null);

    // 1. Get stored IDs from localStorage
    let storedIds: string[] = [];
    try {
      const raw = localStorage.getItem(WALLET_STORAGE_KEY);
      if (raw) {
        storedIds = JSON.parse(raw);
      }
    } catch (e) {
      console.warn('Failed to parse wallet localStorage', e);
    }

    if (!storedIds.includes(DEFAULT_DEMO_CREDENTIAL)) {
      storedIds.unshift(DEFAULT_DEMO_CREDENTIAL);
      localStorage.setItem(WALLET_STORAGE_KEY, JSON.stringify(storedIds));
    }

    const loadedCreds: CredentialResponse[] = [];
    const seenIds = new Set<string>();

    // 2. Try fetching from listCredentials API if authenticated
    try {
      const apiCreds = await credentialApi.listCredentials(50, 0);
      if (Array.isArray(apiCreds)) {
        for (const c of apiCreds) {
          loadedCreds.push(c);
          seenIds.add(c.credential_id.toLowerCase());
          seenIds.add(c.current_fingerprint.toLowerCase());
        }
      }
    } catch {
      // Ignored if unauthenticated or tenant restricted
    }

    // 3. Fetch each stored ID not already in list
    for (const id of storedIds) {
      if (!seenIds.has(id.toLowerCase())) {
        try {
          let cred: CredentialResponse;
          try {
            cred = await credentialApi.getCredential(id);
          } catch {
            cred = await credentialApi.getCredentialByFingerprint(id);
          }
          loadedCreds.push(cred);
          seenIds.add(cred.credential_id.toLowerCase());
          seenIds.add(cred.current_fingerprint.toLowerCase());
        } catch {
          // Fallback: Query public verify endpoint by fingerprint if unauthenticated
          try {
            const v = await credentialApi.verifyCredential(id);
            if (v && v.database_found) {
              loadedCreds.push({
                credential_id: '0xfc6e5fd58a5741b9110a663efd7dcc5ca18d12ccfb4fcc47d64f98c0d8e2a07a',
                issuer_id: '0xc102e1537a30a64b1fae371152e6c4a6a76e1d5407cfd040a8669bdbff4be231',
                current_version: 1,
                current_fingerprint: v.fingerprint,
                current_status: v.lifecycle_status || 'ACTIVE',
                issuance_status: v.blockchain_available && v.is_valid ? 'CONFIRMED' : 'PENDING',
                issuance_tx_hash: null,
                created_at: v.checked_at,
                updated_at: v.checked_at,
              });
              seenIds.add(id.toLowerCase());
            }
          } catch (e) {
            console.warn(`Could not load credential ${id}`, e);
          }
        }
      }
    }

    setCredentials(loadedCreds);
    setIsLoading(false);
  };

  useEffect(() => {
    loadWallet();
  }, []);

  // Import New Credential to Wallet
  const handleImport = async (e: React.FormEvent) => {
    e.preventDefault();
    const clean = importQuery.trim();
    if (!clean) return;

    if (!isValidBytes32Hex(clean)) {
      setImportError('Identifier must be a valid 0x-prefixed 32-byte hexadecimal string.');
      return;
    }

    setImportError(null);
    setIsLoading(true);

    try {
      let cred: CredentialResponse;
      try {
        cred = await credentialApi.getCredential(clean);
      } catch {
        cred = await credentialApi.getCredentialByFingerprint(clean);
      }

      // Save to localStorage
      const raw = localStorage.getItem(WALLET_STORAGE_KEY);
      const storedIds: string[] = raw ? JSON.parse(raw) : [];
      if (!storedIds.map(x => x.toLowerCase()).includes(cred.credential_id.toLowerCase())) {
        storedIds.push(cred.credential_id);
        localStorage.setItem(WALLET_STORAGE_KEY, JSON.stringify(storedIds));
      }

      setImportQuery('');
      setIsImporting(false);
      await loadWallet();
      openCredentialInspector(cred);
    } catch (err) {
      setImportError('Failed to resolve credential record. Verify the ID or fingerprint exists in the registry.');
    } finally {
      setIsLoading(false);
    }
  };

  // Open Detailed Inspector
  const openCredentialInspector = async (cred: CredentialResponse) => {
    setSelectedCredential(cred);
    setIsDetailLoading(true);
    setSelectedVersions([]);
    setSelectedVerification(null);

    try {
      const [versionsList, verifyResp] = await Promise.all([
        credentialApi.getCredentialVersions(cred.credential_id).catch(() => []),
        credentialApi.verifyCredential(cred.current_fingerprint).catch(() => null),
      ]);
      setSelectedVersions(versionsList);
      setSelectedVerification(verifyResp);
    } catch (err) {
      console.warn('Inspector fetch error', err);
    } finally {
      setIsDetailLoading(false);
    }
  };

  // Filtered List
  const filteredCredentials = credentials.filter((c) => {
    if (!searchFilter.trim()) return true;
    const term = searchFilter.toLowerCase();
    return (
      c.credential_id.toLowerCase().includes(term) ||
      c.current_fingerprint.toLowerCase().includes(term) ||
      c.issuer_id.toLowerCase().includes(term) ||
      c.current_status.toLowerCase().includes(term)
    );
  });

  const activeCount = credentials.filter((c) => c.current_status === 'ACTIVE').length;
  const confirmedCount = credentials.filter((c) => c.issuance_status === 'CONFIRMED').length;

  return (
    <div className="space-y-8 animate-in fade-in">
      <PageHeader
        title="Holder Verifiable Credential Wallet"
        description="Decentralized sovereign wallet for credential holders. Inspect stored verifiable credentials, authoritative verification badges, selective disclosure proofs, and instant QR verification passes."
        breadcrumbs={[{ label: 'Holder Wallet' }]}
      />

      {error && <AlertBanner error={error} onDismiss={() => setError(null)} />}

      {/* Overview Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 space-y-1">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-xs uppercase tracking-wider font-semibold">Total Held</span>
            <Wallet className="w-4 h-4 text-brand-400" />
          </div>
          <div className="text-2xl font-bold text-slate-100">{credentials.length}</div>
          <p className="text-[11px] text-slate-500">Stored in sovereign wallet</p>
        </div>

        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 space-y-1">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-xs uppercase tracking-wider font-semibold">Active & Good Standing</span>
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-2xl font-bold text-emerald-400">{activeCount}</div>
          <p className="text-[11px] text-slate-500">Unrevoked & operational</p>
        </div>

        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 space-y-1">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-xs uppercase tracking-wider font-semibold">Sepolia Anchored</span>
            <FileCheck2 className="w-4 h-4 text-cyan-400" />
          </div>
          <div className="text-2xl font-bold text-cyan-300">{confirmedCount}</div>
          <p className="text-[11px] text-slate-500">On-chain transaction provenance</p>
        </div>

        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 space-y-1">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-xs uppercase tracking-wider font-semibold">Privacy Model</span>
            <ShieldCheck className="w-4 h-4 text-purple-400" />
          </div>
          <div className="text-sm font-bold text-purple-300">Strict Zero-PII</div>
          <p className="text-[11px] text-slate-500">Blinded Merkle leaves & salts</p>
        </div>
      </div>

      {/* Toolbar / Actions Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-slate-900/40 border border-slate-800 rounded-xl p-4">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-2.5 w-4 h-4 text-slate-500" />
          <input
            type="text"
            value={searchFilter}
            onChange={(e) => setSearchFilter(e.target.value)}
            placeholder="Filter by Credential ID, Fingerprint, or Status..."
            className="w-full pl-9 pr-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-brand-500 transition-colors"
          />
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={loadWallet}
            disabled={isLoading}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>

          <button
            type="button"
            onClick={() => setIsImporting(!isImporting)}
            className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-brand-600 hover:bg-brand-500 text-white text-xs font-semibold tracking-wide transition-colors shadow-md shadow-brand-950"
          >
            <Plus className="w-4 h-4" />
            <span>Import Credential</span>
          </button>
        </div>
      </div>

      {/* Import Form Drawer */}
      {isImporting && (
        <form onSubmit={handleImport} className="p-5 bg-slate-900/90 border border-brand-800/80 rounded-xl space-y-4 animate-in fade-in">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-slate-100 flex items-center gap-2">
              <Plus className="w-4 h-4 text-brand-400" />
              <span>Import Credential to Sovereign Wallet</span>
            </h3>
            <button
              type="button"
              onClick={() => setIsImporting(false)}
              className="text-xs text-slate-400 hover:text-slate-200"
            >
              Cancel
            </button>
          </div>
          <p className="text-xs text-slate-400">
            Paste an authoritative 32-byte Business Credential ID or composite Fingerprint to add it to your local wallet storage.
          </p>

          <div className="flex gap-2">
            <input
              type="text"
              value={importQuery}
              onChange={(e) => setImportQuery(e.target.value)}
              placeholder="0x... (32-byte hexadecimal string)"
              className="flex-1 px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-xs font-mono text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-brand-500"
            />
            <button
              type="submit"
              disabled={isLoading || !importQuery.trim()}
              className="px-5 py-2 bg-brand-600 hover:bg-brand-500 text-white rounded-lg text-xs font-semibold disabled:opacity-50 transition-colors"
            >
              Add to Wallet
            </button>
          </div>

          {importError && (
            <div className="flex items-center gap-2 text-xs text-rose-400 bg-rose-950/40 p-2.5 rounded-lg border border-rose-800/50">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{importError}</span>
            </div>
          )}
        </form>
      )}

      {/* Credential Library Grid */}
      {isLoading && credentials.length === 0 ? (
        <LoadingSpinner label="Loading sovereign wallet credential registry..." />
      ) : filteredCredentials.length === 0 ? (
        <div className="p-12 text-center bg-slate-900/30 border border-slate-800 rounded-2xl space-y-3">
          <Wallet className="w-10 h-10 text-slate-600 mx-auto" />
          <h3 className="text-base font-medium text-slate-300">No Credentials in Wallet</h3>
          <p className="text-xs text-slate-500 max-w-md mx-auto">
            You do not currently hold any credentials matching the search filter. Use "Import Credential" to track an issued credential.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          {filteredCredentials.map((cred) => (
            <div
              key={cred.credential_id}
              className="bg-slate-900/70 border border-slate-800 hover:border-slate-700/80 rounded-2xl p-6 space-y-5 transition-all shadow-lg flex flex-col justify-between"
            >
              <div className="space-y-4">
                {/* Card Header */}
                <div className="flex items-start justify-between gap-3">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="text-xs px-2 py-0.5 rounded bg-brand-950 text-brand-300 border border-brand-800 font-mono font-semibold">
                        v{cred.current_version}
                      </span>
                      <StatusBadge status={cred.current_status} size="sm" />
                      {cred.issuance_status === 'CONFIRMED' && (
                        <span className="text-[10px] px-2 py-0.5 rounded-full bg-cyan-950 text-cyan-300 border border-cyan-800 font-mono">
                          Sepolia Anchored
                        </span>
                      )}
                    </div>
                    <div className="pt-1">
                      <span className="text-[11px] text-slate-500 block">Business Credential ID</span>
                      <HashBadge hash={cred.credential_id} truncate={false} />
                    </div>
                  </div>
                </div>

                {/* Fingerprint block */}
                <div className="p-3 bg-slate-950 rounded-xl border border-slate-850 space-y-1">
                  <span className="text-[10px] font-mono uppercase tracking-wider text-slate-400 font-semibold">
                    Composite Fingerprint
                  </span>
                  <div className="font-mono text-xs text-brand-300 select-all break-all">
                    {cred.current_fingerprint}
                  </div>
                </div>

                {/* Issuer Info & Timestamps */}
                <div className="grid grid-cols-2 gap-2 text-xs text-slate-400 pt-1 border-t border-slate-800/60">
                  <div>
                    <span className="text-slate-500 text-[11px] block">Issuer ID</span>
                    <HashBadge hash={cred.issuer_id} truncate />
                  </div>
                  <div>
                    <span className="text-slate-500 text-[11px] block">Issued At</span>
                    <span className="text-slate-300 font-mono">{formatDate(cred.created_at)}</span>
                  </div>
                </div>
              </div>

              {/* Card Action Buttons */}
              <div className="grid grid-cols-3 gap-2 pt-3 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => openCredentialInspector(cred)}
                  className="flex items-center justify-center gap-1.5 px-3 py-2 bg-slate-800 hover:bg-slate-750 text-slate-200 rounded-xl text-xs font-medium transition-colors border border-slate-700/60"
                >
                  <ShieldCheck className="w-3.5 h-3.5 text-brand-400" />
                  <span>Inspect</span>
                </button>

                <button
                  type="button"
                  onClick={() => setQrModalCredential(cred)}
                  className="flex items-center justify-center gap-1.5 px-3 py-2 bg-emerald-950/60 hover:bg-emerald-950 border border-emerald-800/80 text-emerald-300 rounded-xl text-xs font-medium transition-colors"
                >
                  <QrCode className="w-3.5 h-3.5 text-emerald-400" />
                  <span>QR Pass</span>
                </button>

                <button
                  type="button"
                  onClick={() => navigate('/presentations')}
                  className="flex items-center justify-center gap-1.5 px-3 py-2 bg-purple-950/60 hover:bg-purple-950 border border-purple-800/80 text-purple-300 rounded-xl text-xs font-medium transition-colors"
                >
                  <EyeOff className="w-3.5 h-3.5 text-purple-400" />
                  <span>Present</span>
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Credential Detail Inspector Modal */}
      {selectedCredential && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/85 backdrop-blur-sm animate-in fade-in overflow-y-auto">
          <div className="relative w-full max-w-3xl my-8 bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl p-6 space-y-6 max-h-[90vh] overflow-y-auto">
            {/* Header */}
            <div className="flex items-start justify-between pb-4 border-b border-slate-800">
              <div>
                <div className="flex items-center gap-2.5">
                  <h3 className="text-lg font-bold text-slate-100">Credential Detail Inspector</h3>
                  <span className="text-xs px-2 py-0.5 rounded bg-brand-950 text-brand-300 border border-brand-800 font-mono">
                    v{selectedCredential.current_version}
                  </span>
                  <StatusBadge status={selectedCredential.current_status} size="sm" />
                </div>
                <p className="text-xs text-slate-400 mt-1">
                  On-chain provenance, cryptographic digests, and authoritative verification gates.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setSelectedCredential(null)}
                className="p-1.5 text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded-lg transition-colors"
              >
                ✕
              </button>
            </div>

            {isDetailLoading ? (
              <LoadingSpinner label="Evaluating on-chain verification gates and loading version tree..." />
            ) : (
              <div className="space-y-6">
                {/* Authoritative Composite Fingerprint */}
                <div className="p-4 bg-slate-950 border border-slate-800 rounded-xl space-y-1.5">
                  <span className="text-xs font-mono uppercase tracking-wider text-slate-400 font-semibold">
                    Current Composite Fingerprint
                  </span>
                  <div className="p-2.5 bg-slate-900 rounded border border-slate-750 font-mono text-xs text-brand-300 select-all break-all">
                    {selectedCredential.current_fingerprint}
                  </div>
                </div>

                {/* Authoritative Live Verification Gate */}
                {selectedVerification && (
                  <div className="space-y-2">
                    <span className="text-xs font-semibold uppercase tracking-wider text-slate-300">
                      Live Gate Verification Result
                    </span>
                    <VerificationBreakdown result={selectedVerification} />
                  </div>
                )}

                {/* Version History Table */}
                {selectedVersions.length > 0 && (
                  <div className="space-y-3">
                    <span className="text-xs font-semibold uppercase tracking-wider text-slate-300 flex items-center gap-2">
                      <History className="w-4 h-4 text-brand-400" />
                      <span>Chronological Version Sequence ({selectedVersions.length})</span>
                    </span>

                    <div className="space-y-3">
                      {selectedVersions.map((v) => (
                        <div
                          key={v.version}
                          className="p-4 bg-slate-950/70 border border-slate-800 rounded-xl space-y-2 text-xs"
                        >
                          <div className="flex items-center justify-between">
                            <span className="font-semibold text-slate-200 font-mono">
                              Version {v.version} {v.version === selectedCredential.current_version && '(Current)'}
                            </span>
                            <span className="font-mono text-slate-400 text-[11px]">
                              {formatDate(v.created_at)}
                            </span>
                          </div>

                          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-slate-400">
                            <div>
                              <span className="text-slate-500 block">Fingerprint:</span>
                              <HashBadge hash={v.fingerprint} truncate />
                            </div>
                            <div>
                              <span className="text-slate-500 block">Salted Merkle Root:</span>
                              <HashBadge hash={v.merkle_root} truncate />
                            </div>
                            <div>
                              <span className="text-slate-500 block">Document Digest:</span>
                              <HashBadge hash={v.document_digest} truncate />
                            </div>
                            <div>
                              <span className="text-slate-500 block">Metadata Digest:</span>
                              <HashBadge hash={v.metadata_digest} truncate />
                            </div>
                          </div>

                          {v.issuance_tx_hash && (
                            <div className="pt-2 border-t border-slate-850 flex items-center justify-between text-[11px] text-cyan-400 font-mono">
                              <span>Sepolia Tx: {v.issuance_tx_hash.slice(0, 16)}...</span>
                              {v.block_number && <span>Block #{v.block_number}</span>}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Actions */}
                <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-800">
                  <button
                    type="button"
                    onClick={() => {
                      setQrModalCredential(selectedCredential);
                      setSelectedCredential(null);
                    }}
                    className="flex items-center gap-2 px-4 py-2 bg-emerald-950/80 hover:bg-emerald-950 border border-emerald-800 text-emerald-300 rounded-xl text-xs font-semibold transition-colors"
                  >
                    <QrCode className="w-4 h-4" />
                    <span>View QR Pass</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => {
                      navigate('/presentations');
                    }}
                    className="flex items-center gap-2 px-4 py-2 bg-brand-600 hover:bg-brand-500 text-white rounded-xl text-xs font-semibold transition-colors"
                  >
                    <EyeOff className="w-4 h-4" />
                    <span>Selective Disclosure</span>
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* QR Pass Modal */}
      {qrModalCredential && (
        <CredentialQrModal
          isOpen={!!qrModalCredential}
          onClose={() => setQrModalCredential(null)}
          fingerprint={qrModalCredential.current_fingerprint}
          credentialId={qrModalCredential.credential_id}
          version={qrModalCredential.current_version}
        />
      )}
    </div>
  );
};
