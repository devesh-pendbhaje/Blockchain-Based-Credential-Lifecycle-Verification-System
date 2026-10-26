import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import {
  FilePlus,
  Upload,
  Binary,
  Layers,
  CheckCircle2,
  ArrowRight,
  ShieldCheck,
  Info,
  Sparkles,
  FileText,
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
import { JsonEditor } from '@/components/forms/JsonEditor';
import { AttributeMapInput, AttributeEntry } from '@/components/forms/AttributeMapInput';
import { HashBadge } from '@/components/status/HashBadge';
import { StatusBadge } from '@/components/status/StatusBadge';
import { AlertBanner } from '@/components/feedback/AlertBanner';
import { LoadingSpinner } from '@/components/feedback/LoadingSpinner';
import { ConfirmDialog } from '@/components/feedback/ConfirmDialog';
import { credentialApi } from '@/services/credentialApi';
import { documentApi } from '@/services/documentApi';
import { merkleApi } from '@/services/merkleApi';
import { credentialCreateSchema, CredentialCreateFormValues } from '@/schemas/credentialSchema';
import { CredentialResponse } from '@/types/credential';
import { DocumentUploadResponse, CanonicalMetadataResponse } from '@/types/document';
import { MerkleBuildTreeResponse } from '@/types/merkle';
import { AppError } from '@/types/api';

export const CredentialIssuancePage: React.FC = () => {
  // Issuance Wizard Steps
  const [currentStep, setCurrentStep] = useState<number>(1);

  // Auth context for identity guardrails
  const { isAuthenticated, user, isIssuer, isAdmin } = useAuth();
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);

  // Sub-component processing states
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<number>(0);
  const [uploadResult, setUploadResult] = useState<DocumentUploadResponse | null>(null);

  const [isCanonicalizing, setIsCanonicalizing] = useState(false);
  const [metadataJson, setMetadataJson] = useState<string>(
    JSON.stringify(
      {
        institution: "State Technological University",
        degreeProgram: "Bachelor of Science in Computer Science",
        accreditationBody: "National Engineering Accreditation Board",
        conferralDate: "2026-06-15"
      },
      null,
      2
    )
  );
  const [canonicalResult, setCanonicalResult] = useState<CanonicalMetadataResponse | null>(null);

  const [isBuildingMerkle, setIsBuildingMerkle] = useState(false);
  const [attributeEntries, setAttributeEntries] = useState<AttributeEntry[]>([
    { id: '1', key: 'degree', value: 'B.S. Computer Science' },
    { id: '2', key: 'major', value: 'Distributed Systems' },
    { id: '3', key: 'gpa', value: '3.94' },
    { id: '4', key: 'honors', value: 'Summa Cum Laude' },
    { id: '5', key: 'graduationYear', value: '2026' },
  ]);
  const [merkleResult, setMerkleResult] = useState<MerkleBuildTreeResponse | null>(null);

  // Submission state
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [issuanceResult, setIssuanceResult] = useState<CredentialResponse | null>(null);
  const [issuanceError, setIssuanceError] = useState<AppError | null>(null);
  const [showConfirm, setShowConfirm] = useState(false);

  const {
    register,
    handleSubmit,
    setValue,
    watch,
    formState: { errors },
  } = useForm<CredentialCreateFormValues>({
    resolver: zodResolver(credentialCreateSchema),
    defaultValues: {
      credential_id: '',
      issuer_id: '',
      document_digest: '',
      metadata_digest: '',
      merkle_root: '',
      version: 1,
      expires_at: 0,
      idempotency_key: '',
    },
  });

  const credentialIdVal = watch('credential_id');
  const issuerIdVal = watch('issuer_id');
  const documentDigestVal = watch('document_digest');
  const metadataDigestVal = watch('metadata_digest');
  const merkleRootVal = watch('merkle_root');

  // Handle Certificate Upload
  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setIsUploading(true);
    setIssuanceError(null);
    setUploadProgress(0);

    try {
      const resp = await documentApi.uploadCertificate(file, (p) => setUploadProgress(p));
      setUploadResult(resp);
      setValue('document_digest', resp.document_digest, { shouldValidate: true });
    } catch (err) {
      setIssuanceError(err as AppError);
    } finally {
      setIsUploading(false);
    }
  };

  // Handle Canonical Metadata Generation
  const handleCanonicalize = async () => {
    setIsCanonicalizing(true);
    setIssuanceError(null);

    try {
      let parsed: unknown;
      try {
        parsed = JSON.parse(metadataJson);
      } catch (jsonErr) {
        setIssuanceError({
          type: 'VALIDATION_ERROR',
          errorCode: 'JSON_SYNTAX_ERROR',
          message: 'The metadata payload contains invalid JSON syntax.',
        });
        return;
      }

      const resp = await documentApi.canonicalizeMetadata(parsed);
      setCanonicalResult(resp);
      setValue('metadata_digest', resp.metadata_digest, { shouldValidate: true });
    } catch (err) {
      setIssuanceError(err as AppError);
    } finally {
      setIsCanonicalizing(false);
    }
  };

  // Handle Merkle Tree Generation
  const handleBuildMerkleTree = async () => {
    setIsBuildingMerkle(true);
    setIssuanceError(null);

    try {
      const attributes: Record<string, string> = {};
      for (const entry of attributeEntries) {
        const k = entry.key.trim();
        const v = entry.value.trim();
        if (k) {
          attributes[k] = v;
        }
      }

      if (Object.keys(attributes).length === 0) {
        setIssuanceError({
          type: 'VALIDATION_ERROR',
          errorCode: 'EMPTY_ATTRIBUTES',
          message: 'At least one valid key-value attribute is required to construct a Merkle tree.',
        });
        return;
      }

      const resp = await merkleApi.buildTree({ attributes });
      setMerkleResult(resp);
      setValue('merkle_root', resp.merkle_root, { shouldValidate: true });
    } catch (err) {
      setIssuanceError(err as AppError);
    } finally {
      setIsBuildingMerkle(false);
    }
  };

  // Final Submission
  const onFinalSubmit = async (values: CredentialCreateFormValues) => {
    setIsSubmitting(true);
    setIssuanceError(null);

    try {
      const resp = await credentialApi.createCredential({
        credential_id: values.credential_id,
        issuer_id: values.issuer_id,
        document_digest: values.document_digest,
        metadata_digest: values.metadata_digest,
        merkle_root: values.merkle_root,
        version: values.version,
        expires_at: values.expires_at || 0,
        idempotency_key: values.idempotency_key || null,
      });

      setIssuanceResult(resp);
      setShowConfirm(false);
    } catch (err) {
      setIssuanceError(err as AppError);
      setShowConfirm(false);
    } finally {
      setIsSubmitting(false);
    }
  };

  const steps = [
    { num: 1, label: 'Identifiers' },
    { num: 2, label: 'Document (SHA-256)' },
    { num: 3, label: 'Metadata (RFC 8785)' },
    { num: 4, label: 'Salted Merkle Tree' },
    { num: 5, label: 'Review & Issue' },
  ];

  return (
    <div className="space-y-8 animate-in fade-in">
      <PageHeader
        title="Guided Credential Issuance"
        description="Construct authoritative 6-component credential fingerprints using server-side AEAD encrypted storage, RFC 8785 canonical metadata, and domain-separated salted Merkle trees."
        breadcrumbs={[{ label: 'Credentials', path: '/credentials' }, { label: 'Issue' }]}
      />

      {/* Auth Banner */}
      {!isAuthenticated ? (
        <div className="p-4 bg-amber-950/40 border border-amber-800/80 rounded-xl text-xs space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-amber-300 font-semibold">
              <ShieldAlert className="w-4 h-4 text-amber-400" />
              <span>Institutional Authentication Required</span>
            </div>
            <button
              type="button"
              onClick={() => setIsAuthModalOpen(true)}
              className="py-1 px-3 rounded-md bg-amber-600 hover:bg-amber-500 text-white text-xs font-semibold flex items-center gap-1.5 transition-colors shadow-sm"
            >
              <LogIn className="w-3.5 h-3.5" />
              <span>Sign In / Select Persona</span>
            </button>
          </div>
          <p className="text-slate-300 text-[11px] leading-relaxed">
            Credential issuance and encrypted file storage require an <strong>Accredited Issuer</strong> or <strong>Administrator</strong> token bound to your institutional authority.
          </p>
        </div>
      ) : !isAdmin && !isIssuer ? (
        <div className="p-4 bg-rose-950/40 border border-rose-800/80 rounded-xl text-xs space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-rose-300 font-semibold">
              <Lock className="w-4 h-4 text-rose-400" />
              <span>Insufficient Permissions for Credential Issuance</span>
            </div>
            <button
              type="button"
              onClick={() => setIsAuthModalOpen(true)}
              className="py-1 px-3 rounded-md bg-slate-800 hover:bg-slate-750 border border-slate-700 text-slate-200 text-xs font-medium flex items-center gap-1.5 transition-colors"
            >
              <Key className="w-3.5 h-3.5" />
              <span>Switch Institutional Persona</span>
            </button>
          </div>
          <p className="text-slate-300 text-[11px] leading-relaxed">
            Current identity <strong>{user?.sub}</strong> has role(s) [<strong>{user?.roles.join(', ')}</strong>]. Only authenticated Issuers or Administrators may anchor credentials.
          </p>
        </div>
      ) : null}

      {issuanceError && (
        <AlertBanner error={issuanceError} onDismiss={() => setIssuanceError(null)} />
      )}

      {/* Issuance Success Result View */}
      {issuanceResult ? (
        <div className="bg-slate-900/80 border border-emerald-800/80 rounded-xl p-6 space-y-6 animate-in fade-in">
          <div className="flex items-center gap-3">
            <div className="p-3 bg-emerald-950/80 border border-emerald-800 text-emerald-300 rounded-xl">
              <CheckCircle2 className="w-8 h-8" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-slate-100">Credential Issuance Request Persisted</h2>
              <p className="text-xs text-slate-400 mt-0.5">
                Composite fingerprint computed authoritatively by backend engine.
              </p>
            </div>
          </div>

          {/* Resulting Fingerprint Card */}
          <div className="p-4 bg-slate-950 border border-slate-800 rounded-lg space-y-3">
            <span className="text-xs font-mono uppercase tracking-wider text-slate-400 font-semibold">
              Authoritative Composite Fingerprint
            </span>
            <div className="p-3 bg-slate-900 rounded border border-slate-750 font-mono text-sm text-emerald-300 select-all break-all">
              {issuanceResult.current_fingerprint}
            </div>
            <div className="flex flex-wrap items-center gap-4 text-xs">
              <span className="text-slate-400">
                Credential ID: <HashBadge hash={issuanceResult.credential_id} truncate />
              </span>
              <span className="text-slate-400">
                Issuer: <HashBadge hash={issuanceResult.issuer_id} truncate />
              </span>
              <span className="text-slate-400">
                Version: <span className="font-mono text-slate-200">v{issuanceResult.current_version}</span>
              </span>
              <span className="text-slate-400">
                Status: <StatusBadge status={issuanceResult.current_status} size="sm" />
              </span>
            </div>
          </div>

          {/* Architecture Reality Explanation */}
          <div className="p-4 bg-slate-950/80 border border-slate-800/80 rounded-lg text-xs space-y-2 text-slate-300">
            <div className="flex items-center gap-2 text-brand-300 font-semibold">
              <Info className="w-4 h-4" />
              <span>Issuance Lifecycle Clarification</span>
            </div>
            <p className="leading-relaxed text-slate-400">
              The credential request is securely recorded in the PostgreSQL database with lifecycle status{' '}
              <strong className="text-slate-200">{issuanceResult.issuance_status}</strong>. In production consortium
              ledgers, final verification validity requires anchoring this exact composite fingerprint to{' '}
              <code>CredentialRegistry.sol</code> via the issuer's authorized key.
            </p>
          </div>

          <div className="flex gap-3">
            <button
              type="button"
              onClick={() => {
                setIssuanceResult(null);
                setCurrentStep(1);
              }}
              className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold rounded-lg border border-slate-700 transition-colors"
            >
              Issue Another Credential
            </button>
            <Link
              to={`/verify?fingerprint=${encodeURIComponent(issuanceResult.current_fingerprint)}`}
              className="px-4 py-2 bg-brand-600 hover:bg-brand-500 text-white text-xs font-semibold rounded-lg transition-colors flex items-center gap-1.5"
            >
              <ShieldCheck className="w-4 h-4" />
              <span>Test Public Verification</span>
            </Link>
          </div>
        </div>
      ) : (
        /* Wizard Steps Container */
        <div className="space-y-6">
          {/* Step Indicator Header */}
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 border-b border-slate-800 pb-4">
            {steps.map((s) => {
              const isPast = s.num < currentStep;
              const isCurr = s.num === currentStep;
              return (
                <button
                  key={s.num}
                  type="button"
                  onClick={() => setCurrentStep(s.num)}
                  className={`p-2.5 rounded-lg text-left transition-all border ${
                    isCurr
                      ? 'bg-brand-950/80 border-brand-700 text-brand-300'
                      : isPast
                      ? 'bg-slate-900 border-slate-700/60 text-slate-300'
                      : 'bg-slate-900/30 border-slate-800/40 text-slate-500 hover:text-slate-400'
                  }`}
                >
                  <div className="text-[10px] font-mono uppercase tracking-wider">Step {s.num}</div>
                  <div className="text-xs font-semibold truncate mt-0.5">{s.label}</div>
                </button>
              );
            })}
          </div>

          {/* Form Content per Step */}
          <form onSubmit={handleSubmit(() => setShowConfirm(true))} className="space-y-6">
            {/* Step 1: Identifiers */}
            {currentStep === 1 && (
              <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-6 space-y-5 animate-in fade-in">
                <div className="flex items-center gap-2 border-b border-slate-800 pb-3">
                  <FilePlus className="w-5 h-5 text-brand-400" />
                  <h3 className="text-base font-semibold text-slate-100">Step 1: Credential & Issuer Identifiers</h3>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                  <FormField
                    label="Credential Business ID (32-byte Hex)"
                    required
                    description="Unique identifier for this credential (e.g. keccak256 hash of student ID/diploma number)."
                    error={errors.credential_id?.message}
                  >
                    <Bytes32Input
                      value={credentialIdVal}
                      onChange={(val) => setValue('credential_id', val, { shouldValidate: true })}
                      placeholder="0x1111... (64 hex characters)"
                      allowGenerate
                    />
                  </FormField>

                  <FormField
                    label="Issuing Authority ID (32-byte Hex)"
                    required
                    description="Identifier of the accredited issuer from the Issuer Registry."
                    error={errors.issuer_id?.message}
                  >
                    <Bytes32Input
                      value={issuerIdVal}
                      onChange={(val) => setValue('issuer_id', val, { shouldValidate: true })}
                      placeholder="0x2222... (64 hex characters)"
                      allowGenerate
                    />
                  </FormField>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-5 pt-2">
                  <FormField
                    label="Version Counter"
                    required
                    description="Monotonically increasing version (default 1)."
                    error={errors.version?.message}
                  >
                    <input
                      type="number"
                      min={1}
                      max={4294967295}
                      {...register('version')}
                      className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-100 focus:outline-none focus:ring-2 focus:ring-brand-500 font-mono"
                    />
                  </FormField>

                  <FormField
                    label="Expiration Timestamp (Unix Epoch)"
                    description="0 = permanent (never expires). Otherwise seconds since epoch."
                    error={errors.expires_at?.message}
                  >
                    <input
                      type="number"
                      min={0}
                      placeholder="0"
                      {...register('expires_at')}
                      className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-100 focus:outline-none focus:ring-2 focus:ring-brand-500 font-mono"
                    />
                  </FormField>

                  <FormField
                    label="Idempotency Key (Optional)"
                    description="Client correlation key to prevent accidental duplicate submission."
                    error={errors.idempotency_key?.message}
                  >
                    <input
                      type="text"
                      placeholder="idemp-corr-uuid..."
                      {...register('idempotency_key')}
                      className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-100 focus:outline-none focus:ring-2 focus:ring-brand-500 font-mono"
                    />
                  </FormField>
                </div>

                <div className="flex justify-end pt-4">
                  <button
                    type="button"
                    onClick={() => setCurrentStep(2)}
                    className="px-5 py-2.5 bg-brand-600 hover:bg-brand-500 text-white rounded-lg text-xs font-semibold flex items-center gap-2 transition-colors"
                  >
                    <span>Next: Upload Certificate Document</span>
                    <ArrowRight className="w-4 h-4" />
                  </button>
                </div>
              </div>
            )}

            {/* Step 2: Encrypted Document Upload */}
            {currentStep === 2 && (
              <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-6 space-y-5 animate-in fade-in">
                <div className="flex items-center gap-2 border-b border-slate-800 pb-3">
                  <Upload className="w-5 h-5 text-brand-400" />
                  <h3 className="text-base font-semibold text-slate-100">Step 2: Certificate Document & Off-Chain Storage</h3>
                </div>

                <div className="p-4 bg-slate-950/70 border border-slate-800 rounded-lg text-xs space-y-2 text-slate-400">
                  <p>
                    Select an official certificate file (PDF, PNG, or JPEG; max 10MB).
                    The backend streaming processor will compute the exact SHA-256 digest over the raw file bytes,
                    encrypt the file at rest with AES-256-GCM using an isolated 96-bit nonce, and store it off-chain.
                  </p>
                </div>

                <div className="space-y-4">
                  <div className="border-2 border-dashed border-slate-750 hover:border-brand-600/60 rounded-xl p-8 flex flex-col items-center justify-center text-center transition-colors bg-slate-950/40">
                    <FileText className="w-10 h-10 text-slate-500 mb-2" />
                    <label className="cursor-pointer">
                      <span className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg text-xs font-semibold border border-slate-700 transition-colors inline-block">
                        Choose Certificate File
                      </span>
                      <input
                        type="file"
                        accept=".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg"
                        onChange={handleFileUpload}
                        className="hidden"
                      />
                    </label>
                    <p className="text-[11px] text-slate-500 mt-2">PDF, PNG, JPEG up to 10 MB</p>
                  </div>

                  {isUploading && (
                    <div className="space-y-1.5 p-3 bg-slate-950 rounded-lg border border-slate-800">
                      <div className="flex justify-between text-xs text-slate-400">
                        <span>Uploading & encrypting with AES-256-GCM...</span>
                        <span>{uploadProgress}%</span>
                      </div>
                      <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-brand-500 transition-all duration-300"
                          style={{ width: `${uploadProgress}%` }}
                        />
                      </div>
                    </div>
                  )}

                  {uploadResult && (
                    <div className="p-4 bg-slate-950 border border-emerald-800/60 rounded-lg space-y-2 text-xs">
                      <div className="flex items-center gap-2 text-emerald-400 font-semibold">
                        <CheckCircle2 className="w-4 h-4" />
                        <span>Document Encrypted & Persisted</span>
                      </div>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-slate-300 font-mono text-[11px]">
                        <div>Storage ID: {uploadResult.storage_id}</div>
                        <div>Content Type: {uploadResult.content_type} ({uploadResult.byte_size} bytes)</div>
                      </div>
                    </div>
                  )}

                  <FormField
                    label="Computed Document Digest (SHA-256)"
                    required
                    description="0x-prefixed 32-byte hash computed directly over raw visual certificate bytes."
                    error={errors.document_digest?.message}
                  >
                    <Bytes32Input
                      value={documentDigestVal}
                      onChange={(val) => setValue('document_digest', val, { shouldValidate: true })}
                      placeholder="Auto-populated upon certificate upload or enter 32-byte hex"
                      allowGenerate
                    />
                  </FormField>
                </div>

                <div className="flex justify-between pt-4">
                  <button
                    type="button"
                    onClick={() => setCurrentStep(1)}
                    className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs font-semibold"
                  >
                    Back
                  </button>
                  <button
                    type="button"
                    onClick={() => setCurrentStep(3)}
                    className="px-5 py-2.5 bg-brand-600 hover:bg-brand-500 text-white rounded-lg text-xs font-semibold flex items-center gap-2 transition-colors"
                  >
                    <span>Next: Canonicalize Metadata</span>
                    <ArrowRight className="w-4 h-4" />
                  </button>
                </div>
              </div>
            )}

            {/* Step 3: RFC 8785 Canonical Metadata */}
            {currentStep === 3 && (
              <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-6 space-y-5 animate-in fade-in">
                <div className="flex items-center gap-2 border-b border-slate-800 pb-3">
                  <Binary className="w-5 h-5 text-brand-400" />
                  <h3 className="text-base font-semibold text-slate-100">Step 3: RFC 8785 Canonical Metadata Digest</h3>
                </div>

                <p className="text-xs text-slate-400 leading-relaxed">
                  JSON metadata is canonicalized under RFC 8785 (JSON Canonicalization Scheme). This guarantees deterministic
                  UTF-16 key sorting and whitespace stripping before calculating the authoritative Keccak-256 metadata digest.
                </p>

                <div className="space-y-3">
                  <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300">
                    Metadata JSON Payload
                  </label>
                  <JsonEditor
                    value={metadataJson}
                    onChange={setMetadataJson}
                    rows={8}
                  />

                  <div className="flex justify-end">
                    <button
                      type="button"
                      disabled={isCanonicalizing}
                      onClick={handleCanonicalize}
                      className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-brand-300 rounded-lg text-xs font-semibold border border-slate-700 flex items-center gap-2 transition-colors disabled:opacity-50"
                    >
                      {isCanonicalizing ? <LoadingSpinner size="sm" /> : <Sparkles className="w-3.5 h-3.5 text-brand-400" />}
                      <span>Compute RFC 8785 Digest</span>
                    </button>
                  </div>

                  {canonicalResult && (
                    <div className="p-4 bg-slate-950 border border-emerald-800/60 rounded-lg space-y-2 text-xs">
                      <div className="flex items-center gap-2 text-emerald-400 font-semibold">
                        <CheckCircle2 className="w-4 h-4" />
                        <span>Canonical Keccak-256 Digest Computed</span>
                      </div>
                      <div className="font-mono text-[11px] text-slate-300 break-all select-all">
                        {canonicalResult.metadata_digest}
                      </div>
                      <div className="text-[11px] text-slate-500 font-mono">
                        Canonical UTF-8 length: {canonicalResult.canonical_bytes_length} bytes
                      </div>
                    </div>
                  )}

                  <FormField
                    label="Metadata Digest (Keccak-256)"
                    required
                    description="0x-prefixed 32-byte digest of RFC 8785 canonical UTF-8 bytes."
                    error={errors.metadata_digest?.message}
                  >
                    <Bytes32Input
                      value={metadataDigestVal}
                      onChange={(val) => setValue('metadata_digest', val, { shouldValidate: true })}
                      placeholder="Auto-populated by canonicalizer or enter 32-byte hex"
                      allowGenerate
                    />
                  </FormField>
                </div>

                <div className="flex justify-between pt-4">
                  <button
                    type="button"
                    onClick={() => setCurrentStep(2)}
                    className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs font-semibold"
                  >
                    Back
                  </button>
                  <button
                    type="button"
                    onClick={() => setCurrentStep(4)}
                    className="px-5 py-2.5 bg-brand-600 hover:bg-brand-500 text-white rounded-lg text-xs font-semibold flex items-center gap-2 transition-colors"
                  >
                    <span>Next: Build Salted Merkle Tree</span>
                    <ArrowRight className="w-4 h-4" />
                  </button>
                </div>
              </div>
            )}

            {/* Step 4: Salted Attribute Merkle Tree */}
            {currentStep === 4 && (
              <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-6 space-y-5 animate-in fade-in">
                <div className="flex items-center gap-2 border-b border-slate-800 pb-3">
                  <Layers className="w-5 h-5 text-brand-400" />
                  <h3 className="text-base font-semibold text-slate-100">Step 4: Salted Attribute Merkle Tree</h3>
                </div>

                <p className="text-xs text-slate-400 leading-relaxed">
                  Enter discrete attribute claims. The backend will generate cryptographically secure 256-bit blinding
                  salts ($2^{256}$ search space) for each claim and compute the domain-separated Merkle root matching
                  <code>DomainSeparatedMerkle.sol</code>.
                </p>

                <div className="space-y-4">
                  <AttributeMapInput
                    entries={attributeEntries}
                    onChange={setAttributeEntries}
                  />

                  <div className="flex justify-end">
                    <button
                      type="button"
                      disabled={isBuildingMerkle}
                      onClick={handleBuildMerkleTree}
                      className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-brand-300 rounded-lg text-xs font-semibold border border-slate-700 flex items-center gap-2 transition-colors disabled:opacity-50"
                    >
                      {isBuildingMerkle ? <LoadingSpinner size="sm" /> : <Layers className="w-3.5 h-3.5 text-brand-400" />}
                      <span>Generate Tree & 256-bit Salts</span>
                    </button>
                  </div>

                  {merkleResult && (
                    <div className="p-4 bg-slate-950 border border-emerald-800/60 rounded-lg space-y-3 text-xs">
                      <div className="flex items-center justify-between">
                        <span className="flex items-center gap-2 text-emerald-400 font-semibold">
                          <CheckCircle2 className="w-4 h-4" />
                          <span>Domain-Separated Merkle Root Generated</span>
                        </span>
                        <span className="text-[11px] font-mono text-slate-400">
                          {merkleResult.ordered_keys.length} Salted Leaves
                        </span>
                      </div>
                      <div className="font-mono text-[11px] text-slate-200 break-all select-all p-2 bg-slate-900 rounded border border-slate-800">
                        {merkleResult.merkle_root}
                      </div>
                    </div>
                  )}

                  <FormField
                    label="Salted Merkle Root"
                    required
                    description="0x-prefixed 32-byte Merkle root anchored on-chain."
                    error={errors.merkle_root?.message}
                  >
                    <Bytes32Input
                      value={merkleRootVal}
                      onChange={(val) => setValue('merkle_root', val, { shouldValidate: true })}
                      placeholder="Auto-populated by tree builder or enter 32-byte hex"
                      allowGenerate
                    />
                  </FormField>
                </div>

                <div className="flex justify-between pt-4">
                  <button
                    type="button"
                    onClick={() => setCurrentStep(3)}
                    className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs font-semibold"
                  >
                    Back
                  </button>
                  <button
                    type="button"
                    onClick={() => setCurrentStep(5)}
                    className="px-5 py-2.5 bg-brand-600 hover:bg-brand-500 text-white rounded-lg text-xs font-semibold flex items-center gap-2 transition-colors"
                  >
                    <span>Next: Review & Issue Credential</span>
                    <ArrowRight className="w-4 h-4" />
                  </button>
                </div>
              </div>
            )}

            {/* Step 5: Review & Issue */}
            {currentStep === 5 && (
              <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-6 space-y-6 animate-in fade-in">
                <div className="flex items-center gap-2 border-b border-slate-800 pb-3">
                  <ShieldCheck className="w-5 h-5 text-brand-400" />
                  <h3 className="text-base font-semibold text-slate-100">Step 5: Review Composite Inputs</h3>
                </div>

                <div className="p-4 bg-slate-950 border border-slate-800 rounded-lg space-y-3 text-xs">
                  <div className="text-[11px] font-mono uppercase tracking-wider text-slate-400 font-semibold">
                    6-Component Fingerprint Input Payload
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-slate-300">
                    <div className="p-2.5 bg-slate-900 rounded border border-slate-800">
                      <span className="text-slate-500 font-medium block">Credential ID:</span>
                      <HashBadge hash={credentialIdVal} truncate={false} />
                    </div>
                    <div className="p-2.5 bg-slate-900 rounded border border-slate-800">
                      <span className="text-slate-500 font-medium block">Issuer ID:</span>
                      <HashBadge hash={issuerIdVal} truncate={false} />
                    </div>
                    <div className="p-2.5 bg-slate-900 rounded border border-slate-800">
                      <span className="text-slate-500 font-medium block">Document Digest (SHA-256):</span>
                      <HashBadge hash={documentDigestVal} truncate={false} />
                    </div>
                    <div className="p-2.5 bg-slate-900 rounded border border-slate-800">
                      <span className="text-slate-500 font-medium block">Metadata Digest (Keccak-256):</span>
                      <HashBadge hash={metadataDigestVal} truncate={false} />
                    </div>
                    <div className="p-2.5 bg-slate-900 rounded border border-slate-800 md:col-span-2">
                      <span className="text-slate-500 font-medium block">Salted Merkle Root:</span>
                      <HashBadge hash={merkleRootVal} truncate={false} />
                    </div>
                  </div>
                </div>

                <div className="flex justify-between pt-4">
                  <button
                    type="button"
                    onClick={() => setCurrentStep(4)}
                    className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs font-semibold"
                  >
                    Back
                  </button>

                  <button
                    type="submit"
                    disabled={isSubmitting}
                    className="px-6 py-2.5 bg-brand-600 hover:bg-brand-500 text-white rounded-lg text-xs font-semibold tracking-wide transition-colors flex items-center gap-2 shadow-lg shadow-brand-900/50"
                  >
                    {isSubmitting ? <LoadingSpinner size="sm" /> : <ShieldCheck className="w-4 h-4" />}
                    <span>Issue Credential Record</span>
                  </button>
                </div>
              </div>
            )}
          </form>

          {/* Consequential Action Confirmation Dialog */}
          <ConfirmDialog
            isOpen={showConfirm}
            title="Confirm Credential Issuance"
            description="You are about to register a new verifiable credential. The backend will compute the authoritative composite fingerprint and persist the lifecycle record."
            confirmLabel="Confirm & Issue"
            isLoading={isSubmitting}
            onConfirm={handleSubmit(onFinalSubmit)}
            onCancel={() => setShowConfirm(false)}
          />
        </div>
      )}

      <AuthModal isOpen={isAuthModalOpen} onClose={() => setIsAuthModalOpen(false)} />
    </div>
  );
};
