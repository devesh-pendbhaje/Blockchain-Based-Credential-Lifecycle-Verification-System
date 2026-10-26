import React, { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import {
  Building2,
  Search,
  PlusCircle,
  Info,
  ShieldAlert,
  LogIn,
  Key,
  Lock,
} from 'lucide-react';
import { useAuth } from '@/context/AuthContext';
import { AuthModal } from '@/components/auth/AuthModal';
import { PageHeader } from '@/components/layout/PageHeader';
import { FormField } from '@/components/forms/FormField';
import { Bytes32Input } from '@/components/forms/Bytes32Input';
import { StatusBadge } from '@/components/status/StatusBadge';
import { HashBadge } from '@/components/status/HashBadge';
import { AlertBanner } from '@/components/feedback/AlertBanner';
import { LoadingSpinner } from '@/components/feedback/LoadingSpinner';
import { issuerApi } from '@/services/issuerApi';
import { issuerCreateSchema, IssuerCreateFormValues } from '@/schemas/issuerSchema';
import { IssuerResponse, IssuerStatusResponse } from '@/types/issuer';
import { AppError } from '@/types/api';
import { formatDate } from '@/utils/date';
import { isValidBytes32Hex } from '@/utils/cryptoFormat';

export const IssuersPage: React.FC = () => {
  // Query state
  const [searchId, setSearchId] = useState('');
  const [isSearching, setIsSearching] = useState(false);
  const [issuerData, setIssuerData] = useState<IssuerResponse | null>(null);
  const [issuerStatusData, setIssuerStatusData] = useState<IssuerStatusResponse | null>(null);
  const [searchError, setSearchError] = useState<AppError | null>(null);

  // Creation state
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [createSuccess, setCreateSuccess] = useState<IssuerResponse | null>(null);
  const [createError, setCreateError] = useState<AppError | null>(null);

  // In-session tracked issuers for quick convenience
  const [sessionIssuers, setSessionIssuers] = useState<IssuerResponse[]>([]);

  // Auth context for identity guardrails
  const { isAuthenticated, user, isIssuer, isAdmin } = useAuth();
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);

  const {
    register,
    handleSubmit,
    setValue,
    watch,
    reset,
    formState: { errors },
  } = useForm<IssuerCreateFormValues>({
    resolver: zodResolver(issuerCreateSchema),
    defaultValues: {
      issuer_id: '',
      display_name: '',
      metadata_uri: '',
      status: 'ACTIVE',
    },
  });

  const issuerIdValue = watch('issuer_id');

  const handleLookup = async (idToQuery: string) => {
    const cleanId = idToQuery.trim();
    if (!cleanId) return;

    if (!isValidBytes32Hex(cleanId)) {
      setSearchError({
        type: 'VALIDATION_ERROR',
        errorCode: 'INVALID_HEX',
        message: 'Issuer ID must be a 0x-prefixed 32-byte hexadecimal string (66 characters total).',
      });
      return;
    }

    setIsSearching(true);
    setSearchError(null);
    setIssuerData(null);
    setIssuerStatusData(null);

    try {
      const [details, statusResp] = await Promise.all([
        issuerApi.getIssuer(cleanId),
        issuerApi.getIssuerStatus(cleanId),
      ]);
      setIssuerData(details);
      setIssuerStatusData(statusResp);

      // Add to session list if not already present
      setSessionIssuers((prev) => {
        if (!prev.some((i) => i.issuer_id === details.issuer_id)) {
          return [details, ...prev];
        }
        return prev;
      });
    } catch (err) {
      setSearchError(err as AppError);
    } finally {
      setIsSearching(false);
    }
  };

  const onSubmitCreate = async (values: IssuerCreateFormValues) => {
    setIsSubmitting(true);
    setCreateError(null);
    setCreateSuccess(null);

    try {
      const created = await issuerApi.createIssuer({
        issuer_id: values.issuer_id,
        display_name: values.display_name,
        metadata_uri: values.metadata_uri || null,
        status: values.status,
      });

      setCreateSuccess(created);
      setIssuerData(created);
      setSessionIssuers((prev) => [created, ...prev.filter((i) => i.issuer_id !== created.issuer_id)]);
      reset();
    } catch (err) {
      setCreateError(err as AppError);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="space-y-8 animate-in fade-in">
      <PageHeader
        title="Issuer Management & Registry"
        description="Register and inspect accredited institutional authorities in the off-chain database and examine on-chain smart contract registration standing."
        breadcrumbs={[{ label: 'Issuers' }]}
      />

      {/* Institutional Architecture Notice */}
      <div className="p-4 bg-slate-900/60 border border-slate-800 rounded-xl text-xs space-y-2 text-slate-300">
        <div className="flex items-center gap-2 text-brand-300 font-semibold">
          <Info className="w-4 h-4" />
          <span>Governance Separation Notice</span>
        </div>
        <p className="leading-relaxed text-slate-400">
          Creating an issuer profile registers the authority within the system database. However, in accordance with
          EVM smart contract security rules (<code>IssuerRegistry.sol</code>), on-chain credential anchoring rights
          require multi-sig governance approval and separate smart contract registration.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Left Column: Create Issuer Profile (5 cols) */}
        <div className="lg:col-span-5 space-y-6">
          <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 space-y-5">
            <div className="flex items-center gap-2 border-b border-slate-800 pb-3">
              <PlusCircle className="w-5 h-5 text-brand-400" />
              <h2 className="text-base font-semibold text-slate-100">Create Issuer Profile</h2>
            </div>

            {/* Auth status & sign-in indicator */}
            {!isAuthenticated ? (
              <div className="p-3.5 bg-amber-950/40 border border-amber-800/80 rounded-lg text-xs space-y-2">
                <div className="flex items-center gap-2 text-amber-300 font-semibold">
                  <ShieldAlert className="w-4 h-4 text-amber-400" />
                  <span>Institutional Authentication Required</span>
                </div>
                <p className="text-slate-300 text-[11px] leading-relaxed">
                  Creating an accredited institutional profile requires an <strong>Administrator</strong> or matching <strong>Accredited Issuer</strong> identity.
                </p>
                <button
                  type="button"
                  onClick={() => setIsAuthModalOpen(true)}
                  className="w-full mt-1 py-1.5 px-3 rounded-md bg-amber-600 hover:bg-amber-500 text-white text-xs font-semibold flex items-center justify-center gap-1.5 transition-colors shadow-sm"
                >
                  <LogIn className="w-3.5 h-3.5" />
                  <span>Sign In / Select Persona</span>
                </button>
              </div>
            ) : !isAdmin && !isIssuer ? (
              <div className="p-3.5 bg-rose-950/40 border border-rose-800/80 rounded-lg text-xs space-y-2">
                <div className="flex items-center gap-2 text-rose-300 font-semibold">
                  <Lock className="w-4 h-4 text-rose-400" />
                  <span>Insufficient Permissions</span>
                </div>
                <p className="text-slate-300 text-[11px] leading-relaxed">
                  Current identity <strong>{user?.sub}</strong> has roles [<strong>{user?.roles.join(', ')}</strong>]. Administrator or Issuer privileges required.
                </p>
                <button
                  type="button"
                  onClick={() => setIsAuthModalOpen(true)}
                  className="w-full mt-1 py-1.5 px-3 rounded-md bg-slate-800 hover:bg-slate-750 border border-slate-700 text-slate-200 text-xs font-medium flex items-center justify-center gap-1.5 transition-colors"
                >
                  <Key className="w-3.5 h-3.5" />
                  <span>Switch Institutional Persona</span>
                </button>
              </div>
            ) : (
              <div className="p-2.5 bg-emerald-950/30 border border-emerald-800/60 rounded-lg text-[11px] text-emerald-300 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-emerald-400" />
                  <span>Authenticated as <strong>{user?.roles[0]}</strong> ({user?.sub})</span>
                </div>
                <button
                  type="button"
                  onClick={() => setIsAuthModalOpen(true)}
                  className="text-emerald-400 hover:underline text-[10px] font-medium"
                >
                  Switch
                </button>
              </div>
            )}

            {createSuccess && (
              <AlertBanner
                type="success"
                title="Issuer Profile Created"
                message={`Successfully registered "${createSuccess.display_name}". Note: ${createSuccess.on_chain_note}`}
                onDismiss={() => setCreateSuccess(null)}
              />
            )}

            {createError && (
              <AlertBanner
                error={createError}
                onDismiss={() => setCreateError(null)}
              />
            )}

            <form onSubmit={handleSubmit(onSubmitCreate)} className="space-y-4">
              <FormField
                label="Issuer ID (32-byte Hex)"
                required
                description="Unique 32-byte cryptographic identifier for this issuing institution."
                error={errors.issuer_id?.message}
              >
                <Bytes32Input
                  value={issuerIdValue}
                  onChange={(val) => setValue('issuer_id', val, { shouldValidate: true })}
                  placeholder="0x9a8b... (64 hex characters)"
                  allowGenerate
                />
              </FormField>

              <FormField
                label="Institution Display Name"
                required
                description="Official accredited name of the organization (e.g. Stanford University)."
                error={errors.display_name?.message}
              >
                <input
                  type="text"
                  placeholder="e.g. Stanford University"
                  {...register('display_name')}
                  className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-100 placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-brand-500"
                />
              </FormField>

              <FormField
                label="Public Metadata URI (Optional)"
                description="Pointer to institutional public DID documents, IPFS profile, or metadata."
                error={errors.metadata_uri?.message}
              >
                <input
                  type="text"
                  placeholder="https://example.edu/metadata.json or ipfs://..."
                  {...register('metadata_uri')}
                  className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-100 placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-brand-500 font-mono"
                />
              </FormField>

              <FormField
                label="Initial Lifecycle Status"
                description="Initial status registered in the database."
                error={errors.status?.message}
              >
                <select
                  {...register('status')}
                  className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-100 focus:outline-none focus:ring-2 focus:ring-brand-500"
                >
                  <option value="ACTIVE">ACTIVE — Authorized to issue credentials</option>
                  <option value="SUSPENDED">SUSPENDED — Temporarily paused</option>
                  <option value="REVOKED">REVOKED — Permanently deactivated</option>
                </select>
              </FormField>

              <button
                type="submit"
                disabled={isSubmitting}
                className="w-full py-2.5 px-4 bg-brand-600 hover:bg-brand-500 text-white rounded-lg text-xs font-semibold tracking-wide transition-colors focus:ring-2 focus:ring-brand-500 disabled:opacity-50 flex items-center justify-center gap-2"
              >
                {isSubmitting ? <LoadingSpinner size="sm" /> : <Building2 className="w-4 h-4" />}
                <span>Register Issuer Record</span>
              </button>
            </form>
          </div>
        </div>

        {/* Right Column: Lookup & Details View (7 cols) */}
        <div className="lg:col-span-7 space-y-6">
          {/* Lookup Bar */}
          <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 space-y-4">
            <div className="flex items-center gap-2 border-b border-slate-800 pb-3">
              <Search className="w-5 h-5 text-brand-400" />
              <h2 className="text-base font-semibold text-slate-100">Inspect Issuer Authority</h2>
            </div>

            <div className="space-y-2">
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300">
                Issuer Identifier (0x + 64 Hex)
              </label>
              <div className="flex gap-2">
                <div className="flex-1">
                  <Bytes32Input
                    value={searchId}
                    onChange={setSearchId}
                    placeholder="Enter 32-byte hex issuer ID to inspect..."
                  />
                </div>
                <button
                  type="button"
                  disabled={isSearching || !searchId}
                  onClick={() => handleLookup(searchId)}
                  className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-100 rounded-lg text-xs font-semibold border border-slate-700 transition-colors disabled:opacity-50 shrink-0 flex items-center gap-1.5"
                >
                  {isSearching ? <LoadingSpinner size="sm" /> : <Search className="w-4 h-4" />}
                  <span>Inspect</span>
                </button>
              </div>
            </div>

            {searchError && (
              <AlertBanner
                error={searchError}
                onDismiss={() => setSearchError(null)}
              />
            )}
          </div>

          {/* Issuer Details Card */}
          {issuerData && (
            <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-6 space-y-6 animate-in fade-in">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800 pb-4">
                <div>
                  <h3 className="text-xl font-bold text-slate-100">{issuerData.display_name}</h3>
                  <div className="mt-1">
                    <HashBadge hash={issuerData.issuer_id} label="Issuer ID" truncate={false} />
                  </div>
                </div>
                <div className="shrink-0 flex items-center gap-2">
                  <StatusBadge status={issuerData.status} size="md" />
                </div>
              </div>

              {/* Status Comparison Grid (Database vs On-Chain) */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="p-4 bg-slate-950/70 border border-slate-800/80 rounded-lg space-y-2">
                  <span className="text-xs text-slate-400 font-medium">PostgreSQL Database Status</span>
                  <div className="flex items-center justify-between">
                    <StatusBadge status={issuerData.status} size="sm" />
                    <span className="text-[11px] text-slate-500 font-mono">
                      Updated: {formatDate(issuerData.updated_at)}
                    </span>
                  </div>
                </div>

                <div className="p-4 bg-slate-950/70 border border-slate-800/80 rounded-lg space-y-2">
                  <span className="text-xs text-slate-400 font-medium">EVM Smart Contract Registration</span>
                  <div className="flex items-center justify-between">
                    <StatusBadge
                      status={
                        issuerStatusData?.on_chain_status === 'ACTIVE'
                          ? 'ACTIVE'
                          : issuerStatusData?.on_chain_status === 'UNAVAILABLE'
                          ? 'UNAVAILABLE'
                          : issuerStatusData?.is_on_chain_active
                          ? 'ACTIVE'
                          : 'UNAVAILABLE'
                      }
                      size="sm"
                    />
                    <span className="text-[11px] text-slate-500 font-mono">
                      State: {issuerStatusData?.on_chain_status || 'Unregistered'}
                    </span>
                  </div>
                </div>
              </div>

              {/* Metadata pointer */}
              <div className="space-y-1.5 text-xs">
                <span className="text-slate-400 font-semibold uppercase tracking-wider text-[11px]">
                  Metadata URI Pointer
                </span>
                <div className="p-2.5 bg-slate-950 rounded border border-slate-800 font-mono text-slate-300 break-all select-all">
                  {issuerData.metadata_uri || 'No public metadata URI registered.'}
                </div>
              </div>

              {/* Governance Note */}
              <div className="p-3.5 bg-slate-950/90 rounded-lg border border-slate-800/80 flex items-start gap-2.5 text-xs text-slate-400">
                <Info className="w-4 h-4 text-brand-400 shrink-0 mt-0.5" />
                <span>{issuerData.on_chain_note}</span>
              </div>
            </div>
          )}

          {/* Session Tracked Issuers (No fake counts!) */}
          {sessionIssuers.length > 0 && (
            <div className="bg-slate-900/40 border border-slate-800 rounded-xl p-5 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                  Recent Issuers (Active Session)
                </span>
                <span className="text-[11px] font-mono text-slate-500">
                  {sessionIssuers.length} registered/inspected
                </span>
              </div>

              <div className="space-y-2">
                {sessionIssuers.map((item) => (
                  <div
                    key={item.issuer_id}
                    onClick={() => {
                      setSearchId(item.issuer_id);
                      handleLookup(item.issuer_id);
                    }}
                    className="p-3 bg-slate-950/60 hover:bg-slate-900 border border-slate-800/80 hover:border-slate-700 rounded-lg flex items-center justify-between gap-3 cursor-pointer transition-colors"
                  >
                    <div>
                      <div className="text-xs font-semibold text-slate-200">{item.display_name}</div>
                      <div className="mt-1">
                        <HashBadge hash={item.issuer_id} truncate={true} />
                      </div>
                    </div>
                    <StatusBadge status={item.status} size="sm" />
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      <AuthModal isOpen={isAuthModalOpen} onClose={() => setIsAuthModalOpen(false)} />
    </div>
  );
};
