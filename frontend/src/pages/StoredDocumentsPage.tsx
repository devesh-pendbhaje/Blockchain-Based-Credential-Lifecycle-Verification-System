import React, { useState } from 'react';
import {
  Upload,
  Lock,
  Search,
  CheckCircle2,
  FileText,
  Binary,
  Layers,
  Sparkles,
} from 'lucide-react';
import { PageHeader } from '@/components/layout/PageHeader';
import { FormField } from '@/components/forms/FormField';
import { Bytes32Input } from '@/components/forms/Bytes32Input';
import { JsonEditor } from '@/components/forms/JsonEditor';
import { HashBadge } from '@/components/status/HashBadge';
import { AlertBanner } from '@/components/feedback/AlertBanner';
import { LoadingSpinner } from '@/components/feedback/LoadingSpinner';
import { documentApi } from '@/services/documentApi';
import { merkleApi } from '@/services/merkleApi';
import {
  DocumentUploadResponse,
  StorageMetadataResponse,
  CanonicalMetadataResponse,
} from '@/types/document';
import { AppError } from '@/types/api';
import { formatDate } from '@/utils/date';

export const StoredDocumentsPage: React.FC = () => {
  // 1. Upload state
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadResult, setUploadResult] = useState<DocumentUploadResponse | null>(null);
  const [uploadError, setUploadError] = useState<AppError | null>(null);

  // 2. Storage Inspection state
  const [storageIdInput, setStorageIdInput] = useState('');
  const [isInspecting, setIsInspecting] = useState(false);
  const [storageMeta, setStorageMeta] = useState<StorageMetadataResponse | null>(null);
  const [inspectError, setInspectError] = useState<AppError | null>(null);

  // 3. RFC 8785 Canonicalizer state
  const [metaInput, setMetaInput] = useState('{\n  "institution": "Stanford University",\n  "degree": "M.S. Computer Science",\n  "year": 2026\n}');
  const [isCanonicalizing, setIsCanonicalizing] = useState(false);
  const [canonicalResult, setCanonicalResult] = useState<CanonicalMetadataResponse | null>(null);
  const [canonicalError, setCanonicalError] = useState<AppError | null>(null);

  // 4. Merkle Proof Verifier state
  const [proofRoot, setProofRoot] = useState('');
  const [proofLeaf, setProofLeaf] = useState('');
  const [proofPath, setProofPath] = useState('');
  const [isVerifyingProof, setIsVerifyingProof] = useState(false);
  const [proofVerified, setProofVerified] = useState<boolean | null>(null);
  const [proofError, setProofError] = useState<AppError | null>(null);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Client-side file size check (10MB)
    const MAX_SIZE = 10 * 1024 * 1024;
    if (file.size > MAX_SIZE) {
      setUploadError({
        type: 'VALIDATION_ERROR',
        errorCode: 'FILE_TOO_LARGE',
        message: `File exceeds the maximum permitted upload limit of 10 MB (file size: ${(file.size / (1024 * 1024)).toFixed(2)} MB).`,
      });
      return;
    }

    setIsUploading(true);
    setUploadError(null);
    setUploadResult(null);
    setUploadProgress(0);

    try {
      const resp = await documentApi.uploadCertificate(file, (p) => setUploadProgress(p));
      setUploadResult(resp);
      setStorageIdInput(resp.storage_id);
    } catch (err) {
      setUploadError(err as AppError);
    } finally {
      setIsUploading(false);
    }
  };

  const handleInspectStorage = async (e: React.FormEvent) => {
    e.preventDefault();
    const cleanId = storageIdInput.trim();
    if (!cleanId) return;

    setIsInspecting(true);
    setInspectError(null);
    setStorageMeta(null);

    try {
      const resp = await documentApi.getStorageMetadata(cleanId);
      setStorageMeta(resp);
    } catch (err) {
      setInspectError(err as AppError);
    } finally {
      setIsInspecting(false);
    }
  };

  const handleRunCanonicalize = async () => {
    setIsCanonicalizing(true);
    setCanonicalError(null);
    setCanonicalResult(null);

    try {
      let parsed: unknown;
      try {
        parsed = JSON.parse(metaInput);
      } catch (err) {
        setCanonicalError({
          type: 'VALIDATION_ERROR',
          errorCode: 'INVALID_JSON',
          message: 'The input must be valid JSON syntax.',
        });
        return;
      }

      const resp = await documentApi.canonicalizeMetadata(parsed);
      setCanonicalResult(resp);
    } catch (err) {
      setCanonicalError(err as AppError);
    } finally {
      setIsCanonicalizing(false);
    }
  };

  const handleVerifyMerkleProof = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsVerifyingProof(true);
    setProofError(null);
    setProofVerified(null);

    try {
      let proofArray: string[] = [];
      if (proofPath.trim()) {
        try {
          const parsed = JSON.parse(proofPath);
          if (Array.isArray(parsed)) {
            proofArray = parsed;
          } else {
            throw new Error();
          }
        } catch {
          // Fallback to comma/line split
          proofArray = proofPath.split(/[\n,]/).map((s) => s.trim()).filter(Boolean);
        }
      }

      const resp = await merkleApi.verifyProof({
        root: proofRoot.trim(),
        leaf: proofLeaf.trim(),
        proof: proofArray,
      });

      setProofVerified(resp.is_valid);
    } catch (err) {
      setProofError(err as AppError);
    } finally {
      setIsVerifyingProof(false);
    }
  };

  return (
    <div className="space-y-8 animate-in fade-in">
      <PageHeader
        title="Encrypted Off-Chain Storage & Cryptographic Primitives"
        description="AES-256-GCM envelope encryption at rest, isolated UUID storage identifiers, RFC 8785 JSON canonicalization, and domain-separated Merkle proof verification."
        breadcrumbs={[{ label: 'Documents & Primitives' }]}
      />

      {/* Security Principles Banner */}
      <div className="p-4 bg-slate-900/60 border border-slate-800 rounded-xl text-xs space-y-2 text-slate-300">
        <div className="flex items-center gap-2 text-brand-300 font-semibold">
          <Lock className="w-4 h-4" />
          <span>Authenticated Encryption & Privacy Architecture</span>
        </div>
        <p className="leading-relaxed text-slate-400">
          Raw certificate documents are encrypted using AES-256-GCM with unique 96-bit nonces and AAD binding
          (<code>storage_id:document_digest:content_type</code>). In compliance with zero-trust security guidelines,
          plaintext certificates, decrypted buffers, and encryption keys are <strong>never</strong> cached in persistent
          browser storage or exposed through unauthenticated download links.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Card 1: Encrypted Upload Component */}
        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-6 space-y-5">
          <div className="flex items-center gap-2 border-b border-slate-800 pb-3">
            <Upload className="w-5 h-5 text-brand-400" />
            <h2 className="text-base font-semibold text-slate-100">Upload & Encrypt Certificate Document</h2>
          </div>

          <p className="text-xs text-slate-400 leading-relaxed">
            Upload visual certificates (PDF, PNG, JPEG up to 10MB). The backend will stream and hash the raw bytes
            under SHA-256, encrypt the payload with AES-256-GCM, and assign an isolated UUIDv4 storage identifier.
          </p>

          {uploadError && <AlertBanner error={uploadError} onDismiss={() => setUploadError(null)} />}

          <div className="border-2 border-dashed border-slate-750 hover:border-brand-600/60 rounded-xl p-8 flex flex-col items-center justify-center text-center transition-colors bg-slate-950/40">
            <FileText className="w-10 h-10 text-slate-500 mb-2" />
            <label className="cursor-pointer">
              <span className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg text-xs font-semibold border border-slate-700 transition-colors inline-block">
                Select File to Encrypt
              </span>
              <input
                type="file"
                accept=".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg"
                onChange={handleFileUpload}
                className="hidden"
              />
            </label>
            <p className="text-[11px] text-slate-500 mt-2">Maximum file limit: 10 MB (PDF, PNG, JPEG)</p>
          </div>

          {isUploading && (
            <div className="space-y-1.5 p-3 bg-slate-950 rounded-lg border border-slate-800">
              <div className="flex justify-between text-xs text-slate-400">
                <span>Encrypting with AES-256-GCM envelope...</span>
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
            <div className="p-4 bg-slate-950 border border-emerald-800/80 rounded-lg space-y-3 text-xs animate-in fade-in">
              <div className="flex items-center gap-2 text-emerald-400 font-semibold">
                <CheckCircle2 className="w-4 h-4" />
                <span>Certificate Encrypted & Persisted</span>
              </div>

              <div className="space-y-2 font-mono text-[11px] text-slate-300">
                <div>Storage ID: <span className="text-slate-100">{uploadResult.storage_id}</span></div>
                <div>Document Digest: <HashBadge hash={uploadResult.document_digest} truncate={false} /></div>
                <div>MIME Type: {uploadResult.content_type} ({uploadResult.byte_size} bytes)</div>
                <div>Storage Adapter: {uploadResult.storage_adapter}</div>
              </div>
            </div>
          )}
        </div>

        {/* Card 2: Inspect Storage Metadata */}
        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-6 space-y-5">
          <div className="flex items-center gap-2 border-b border-slate-800 pb-3">
            <Search className="w-5 h-5 text-brand-400" />
            <h2 className="text-base font-semibold text-slate-100">Inspect Storage Object Metadata</h2>
          </div>

          <p className="text-xs text-slate-400 leading-relaxed">
            Inspect off-chain storage properties by UUID identifier. Returns non-secret envelope properties
            (envelope version, content type, document digest) without exposing ciphertext or decryption keys.
          </p>

          {inspectError && <AlertBanner error={inspectError} onDismiss={() => setInspectError(null)} />}

          <form onSubmit={handleInspectStorage} className="space-y-3">
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300">
              Storage Identifier (UUIDv4)
            </label>
            <div className="flex gap-2">
              <input
                type="text"
                placeholder="e.g. 550e8400-e29b-41d4-a716-446655440000"
                value={storageIdInput}
                onChange={(e) => setStorageIdInput(e.target.value)}
                className="flex-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-100 font-mono focus:outline-none focus:ring-2 focus:ring-brand-500"
              />
              <button
                type="submit"
                disabled={isInspecting || !storageIdInput}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-100 rounded-lg text-xs font-semibold border border-slate-700 transition-colors disabled:opacity-50"
              >
                {isInspecting ? <LoadingSpinner size="sm" /> : <Search className="w-4 h-4" />}
              </button>
            </div>
          </form>

          {storageMeta && (
            <div className="p-4 bg-slate-950 border border-slate-800 rounded-lg space-y-3 text-xs animate-in fade-in">
              <div className="flex items-center justify-between text-slate-300">
                <span className="font-semibold text-emerald-400 flex items-center gap-1.5">
                  <CheckCircle2 className="w-4 h-4" />
                  <span>Metadata Located</span>
                </span>
                <span className="font-mono text-slate-500">Envelope v{storageMeta.envelope_version}</span>
              </div>

              <div className="space-y-2 font-mono text-[11px] text-slate-300">
                <div>Document Digest: <HashBadge hash={storageMeta.document_digest} truncate={false} /></div>
                <div>Content Type: {storageMeta.content_type} ({storageMeta.byte_size} bytes)</div>
                <div>Created: {formatDate(storageMeta.created_at)}</div>
              </div>
            </div>
          )}
        </div>

        {/* Card 3: RFC 8785 Canonicalizer */}
        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-6 space-y-5">
          <div className="flex items-center gap-2 border-b border-slate-800 pb-3">
            <Binary className="w-5 h-5 text-brand-400" />
            <h2 className="text-base font-semibold text-slate-100">RFC 8785 Metadata Canonicalization Tool</h2>
          </div>

          <p className="text-xs text-slate-400 leading-relaxed">
            Test JSON canonicalization under RFC 8785. The engine validates that no duplicate keys exist,
            sorts dictionary keys by UTF-16 code units, and computes the Keccak-256 metadata digest.
          </p>

          {canonicalError && <AlertBanner error={canonicalError} onDismiss={() => setCanonicalError(null)} />}

          <div className="space-y-3">
            <JsonEditor value={metaInput} onChange={setMetaInput} rows={6} />

            <div className="flex justify-end">
              <button
                type="button"
                disabled={isCanonicalizing}
                onClick={handleRunCanonicalize}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-brand-300 rounded-lg text-xs font-semibold border border-slate-700 flex items-center gap-2 transition-colors disabled:opacity-50"
              >
                {isCanonicalizing ? <LoadingSpinner size="sm" /> : <Sparkles className="w-3.5 h-3.5 text-brand-400" />}
                <span>Compute Canonical Digest</span>
              </button>
            </div>

            {canonicalResult && (
              <div className="p-4 bg-slate-950 border border-emerald-800/80 rounded-lg space-y-2 text-xs animate-in fade-in">
                <span className="text-emerald-400 font-semibold flex items-center gap-1.5">
                  <CheckCircle2 className="w-4 h-4" />
                  <span>Canonical Keccak-256 Digest:</span>
                </span>
                <div className="font-mono text-xs text-slate-200 break-all select-all p-2 bg-slate-900 rounded border border-slate-800">
                  {canonicalResult.metadata_digest}
                </div>
                <div className="font-mono text-[10px] text-slate-500">
                  Canonical length: {canonicalResult.canonical_bytes_length} UTF-8 bytes
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Card 4: Domain-Separated Merkle Proof Verifier */}
        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-6 space-y-5">
          <div className="flex items-center gap-2 border-b border-slate-800 pb-3">
            <Layers className="w-5 h-5 text-brand-400" />
            <h2 className="text-base font-semibold text-slate-100">Domain-Separated Merkle Proof Verifier</h2>
          </div>

          <p className="text-xs text-slate-400 leading-relaxed">
            Verify arbitrary Merkle sibling proofs against target root digests matching <code>DomainSeparatedMerkle.sol</code>.
          </p>

          {proofError && <AlertBanner error={proofError} onDismiss={() => setProofError(null)} />}

          <form onSubmit={handleVerifyMerkleProof} className="space-y-3">
            <FormField label="Target Merkle Root (32-byte Hex)">
              <Bytes32Input value={proofRoot} onChange={setProofRoot} placeholder="0x... Merkle root" />
            </FormField>

            <FormField label="Leaf Hash (0x00 Domain Separated)">
              <Bytes32Input value={proofLeaf} onChange={setProofLeaf} placeholder="0x... Target leaf hash" />
            </FormField>

            <FormField label="Sibling Proof Path (JSON array or lines)">
              <textarea
                rows={3}
                value={proofPath}
                onChange={(e) => setProofPath(e.target.value)}
                placeholder='["0x1111...", "0x2222..."]'
                className="w-full bg-slate-900 border border-slate-700 rounded-lg p-2.5 text-xs font-mono text-slate-100 placeholder-slate-600 focus:outline-none focus:ring-1 focus:ring-brand-500"
              />
            </FormField>

            <div className="flex justify-between items-center pt-2">
              {proofVerified !== null && (
                <div
                  className={`text-xs font-semibold px-3 py-1.5 rounded-lg border ${
                    proofVerified
                      ? 'bg-emerald-950/80 border-emerald-800 text-emerald-300'
                      : 'bg-rose-950/80 border-rose-800 text-rose-300'
                  }`}
                >
                  {proofVerified ? 'Merkle Proof VALID' : 'Merkle Proof INVALID'}
                </div>
              )}

              <button
                type="submit"
                disabled={isVerifyingProof || !proofRoot || !proofLeaf}
                className="ml-auto px-4 py-2 bg-brand-600 hover:bg-brand-500 text-white rounded-lg text-xs font-semibold tracking-wide transition-colors disabled:opacity-50"
              >
                {isVerifyingProof ? <LoadingSpinner size="sm" /> : 'Verify Merkle Proof'}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
};
