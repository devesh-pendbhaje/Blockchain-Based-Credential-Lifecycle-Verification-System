import React, { useState } from 'react';
import {
  EyeOff,
  KeyRound,
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
} from 'lucide-react';
import { PageHeader } from '@/components/layout/PageHeader';
import { Tabs, TabOption } from '@/components/navigation/Tabs';
import { FormField } from '@/components/forms/FormField';
import { HashBadge } from '@/components/status/HashBadge';
import { StatusBadge } from '@/components/status/StatusBadge';
import { AlertBanner } from '@/components/feedback/AlertBanner';
import { LoadingSpinner } from '@/components/feedback/LoadingSpinner';
import { challengeApi } from '@/services/challengeApi';
import { presentationApi } from '@/services/presentationApi';
import { merkleApi } from '@/services/merkleApi';
import { ChallengeCreateResponse } from '@/types/challenge';
import { PresentationResponse, PresentationVerifyResponse } from '@/types/presentation';
import { AppError } from '@/types/api';
import { formatDate } from '@/utils/date';

export const SelectiveDisclosurePage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<string>('challenge');

  // Shared state across the 3 steps
  // 1. Verifier Challenge State
  const [verifierSessionId, setVerifierSessionId] = useState<string>('session-hr-auditor-2026');
  const [challengeExpirySec, setChallengeExpirySec] = useState<number>(300);
  const [isIssuingChallenge, setIsIssuingChallenge] = useState<boolean>(false);
  const [activeChallenge, setActiveChallenge] = useState<ChallengeCreateResponse | null>(null);
  const [challengeError, setChallengeError] = useState<AppError | null>(null);

  // 2. Holder Claims & Tree State
  const credentialId = '0x1234000000000000000000000000000000000000000000000000000000000001';
  const issuerId = '0x9876000000000000000000000000000000000000000000000000000000000002';
  const version = 1;
  const docDigest = '0xaaaa000000000000000000000000000000000000000000000000000000000003';
  const metaDigest = '0xbbbb000000000000000000000000000000000000000000000000000000000004';

  const rawAttributes = {
    fullName: 'Jane Doe',
    degree: 'B.S. Computer Science',
    graduationYear: '2026',
    gpa: '3.94',
    socialSecurityNumber: 'XXX-XX-9876', // Sensitive claim to keep concealed!
  };

  const [salts, setSalts] = useState<Record<string, string>>({});
  const [selectedDisclosedKeys, setSelectedDisclosedKeys] = useState<string[]>(['degree', 'graduationYear']);

  const [isGeneratingPresentation, setIsGeneratingPresentation] = useState<boolean>(false);
  const [presentation, setPresentation] = useState<PresentationResponse | null>(null);
  const [presentationError, setPresentationError] = useState<AppError | null>(null);

  // 3. Verifier Presentation Verification State
  const [isVerifyingPresentation, setIsVerifyingPresentation] = useState<boolean>(false);
  const [verifyOutcome, setVerifyOutcome] = useState<PresentationVerifyResponse | null>(null);
  const [verifyError, setVerifyError] = useState<AppError | null>(null);

  // Initialize salts for holder claims if not yet built
  const prepareHolderMerkleTree = async () => {
    try {
      const resp = await merkleApi.buildTree({ attributes: rawAttributes });
      setSalts(resp.salts);
    } catch (err) {
      console.error('Failed to prepare Merkle tree', err);
    }
  };

  React.useEffect(() => {
    prepareHolderMerkleTree();
  }, []);

  // Step 1: Issue Challenge
  const handleIssueChallenge = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsIssuingChallenge(true);
    setChallengeError(null);

    try {
      const resp = await challengeApi.createChallenge({
        verifier_session_id: verifierSessionId,
        expiry_seconds: challengeExpirySec,
      });
      setActiveChallenge(resp);
      // Auto advance to presentation generation tab
      setActiveTab('generate');
    } catch (err) {
      setChallengeError(err as AppError);
    } finally {
      setIsIssuingChallenge(false);
    }
  };

  // Step 2: Toggle Disclosed Attribute Key
  const toggleKey = (key: string) => {
    setSelectedDisclosedKeys((prev) =>
      prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]
    );
  };

  // Step 2: Generate Presentation
  const handleGeneratePresentation = async () => {
    if (selectedDisclosedKeys.length === 0) {
      setPresentationError({
        type: 'VALIDATION_ERROR',
        errorCode: 'NO_CLAIMS_SELECTED',
        message: 'You must select at least one attribute to disclose.',
      });
      return;
    }

    setIsGeneratingPresentation(true);
    setPresentationError(null);

    try {
      // Ensure salts exist
      let currentSalts = salts;
      if (Object.keys(currentSalts).length === 0) {
        const tree = await merkleApi.buildTree({ attributes: rawAttributes });
        currentSalts = tree.salts;
        setSalts(tree.salts);
      }

      const resp = await presentationApi.generatePresentation({
        credential_id: credentialId,
        version,
        attributes: rawAttributes,
        salts: currentSalts,
        disclosed_keys: selectedDisclosedKeys,
        document_digest: docDigest,
        metadata_digest: metaDigest,
        issuer_id: issuerId,
        challenge_id: activeChallenge?.challenge_id,
        challenge_nonce: activeChallenge?.challenge_nonce,
      });

      setPresentation(resp);
      // Advance to verification tab
      setActiveTab('verify');
    } catch (err) {
      setPresentationError(err as AppError);
    } finally {
      setIsGeneratingPresentation(false);
    }
  };

  // Step 3: Verify Presentation
  const handleVerifyPresentation = async () => {
    if (!presentation) {
      setVerifyError({
        type: 'VALIDATION_ERROR',
        errorCode: 'MISSING_PRESENTATION',
        message: 'No presentation is available to verify. Please generate one in Step 2.',
      });
      return;
    }

    setIsVerifyingPresentation(true);
    setVerifyError(null);

    try {
      const resp = await presentationApi.verifyPresentation({
        presentation: presentation as unknown as Record<string, unknown>,
        verifier_session_id: verifierSessionId,
        require_current_version: false,
      });

      setVerifyOutcome(resp);
    } catch (err) {
      setVerifyError(err as AppError);
    } finally {
      setIsVerifyingPresentation(false);
    }
  };

  const tabs: TabOption[] = [
    { id: 'challenge', label: '1. Issue Verifier Challenge', icon: <KeyRound className="w-4 h-4" /> },
    { id: 'generate', label: '2. Generate Disclosure Presentation', icon: <EyeOff className="w-4 h-4" /> },
    { id: 'verify', label: '3. Verify Presentation & Nonce', icon: <ShieldCheck className="w-4 h-4" /> },
  ];

  return (
    <div className="space-y-8 animate-in fade-in">
      <PageHeader
        title="Privacy-Preserving Selective Disclosure"
        description="Prove individual claims (e.g. degree or graduation year) with 256-bit salted Merkle sub-tree proofs while concealing sensitive attributes (e.g. SSN or grades). Bound to verifier single-use challenges."
        breadcrumbs={[{ label: 'Selective Disclosure' }]}
      />

      <Tabs tabs={tabs} activeTab={activeTab} onChange={setActiveTab} />

      {/* Tab 1: Verifier Nonce Challenge */}
      {activeTab === 'challenge' && (
        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-6 space-y-6 animate-in fade-in max-w-3xl">
          <div className="flex items-center gap-2 border-b border-slate-800 pb-3">
            <KeyRound className="w-5 h-5 text-brand-400" />
            <h2 className="text-base font-semibold text-slate-100">Step 1: Request Verifier Nonce Challenge</h2>
          </div>

          <p className="text-xs text-slate-400 leading-relaxed">
            The verifier issues a dynamic, 256-bit cryptographically secure random nonce bound to their session.
            The backend stores only the SHA-256 hash in PostgreSQL to prevent database compromise.
            Presentations must consume this nonce to protect against presentation replay attacks.
          </p>

          {challengeError && <AlertBanner error={challengeError} onDismiss={() => setChallengeError(null)} />}

          {activeChallenge && (
            <div className="p-4 bg-slate-950 border border-emerald-800/80 rounded-lg space-y-3 text-xs animate-in fade-in">
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-2 text-emerald-400 font-semibold">
                  <CheckCircle2 className="w-4 h-4" />
                  <span>Challenge Issued & Ready</span>
                </span>
                <span className="font-mono text-[11px] text-slate-400">
                  Status: {activeChallenge.status}
                </span>
              </div>

              <div className="space-y-1 font-mono text-[11px]">
                <div className="text-slate-400">Challenge UUID: {activeChallenge.challenge_id}</div>
                <div className="text-slate-300 break-all select-all p-2 bg-slate-900 rounded border border-slate-800">
                  Nonce: {activeChallenge.challenge_nonce}
                </div>
                <div className="text-slate-500">Expires at: {formatDate(activeChallenge.expires_at)}</div>
              </div>
            </div>
          )}

          <form onSubmit={handleIssueChallenge} className="space-y-4">
            <FormField
              label="Verifier Session Identifier"
              required
              description="Unique session ID of the auditing entity or relying party."
            >
              <input
                type="text"
                value={verifierSessionId}
                onChange={(e) => setVerifierSessionId(e.target.value)}
                className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-100 focus:outline-none focus:ring-2 focus:ring-brand-500 font-mono"
              />
            </FormField>

            <FormField
              label="Challenge Validity Window (Seconds)"
              description="Lifespan before challenge expiration (10 to 3600 seconds; default 300s)."
            >
              <input
                type="number"
                min={10}
                max={3600}
                value={challengeExpirySec}
                onChange={(e) => setChallengeExpirySec(Number(e.target.value))}
                className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-100 focus:outline-none focus:ring-2 focus:ring-brand-500 font-mono"
              />
            </FormField>

            <button
              type="submit"
              disabled={isIssuingChallenge || !verifierSessionId}
              className="px-6 py-2.5 bg-brand-600 hover:bg-brand-500 text-white rounded-lg text-xs font-semibold tracking-wide transition-colors flex items-center gap-2 disabled:opacity-50"
            >
              {isIssuingChallenge ? <LoadingSpinner size="sm" /> : <KeyRound className="w-4 h-4" />}
              <span>Issue Verifier Nonce Challenge</span>
            </button>
          </form>
        </div>
      )}

      {/* Tab 2: Generate Disclosure Presentation */}
      {activeTab === 'generate' && (
        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-6 space-y-6 animate-in fade-in">
          <div className="flex items-center gap-2 border-b border-slate-800 pb-3">
            <EyeOff className="w-5 h-5 text-brand-400" />
            <h2 className="text-base font-semibold text-slate-100">Step 2: Holder Selective Disclosure Presentation</h2>
          </div>

          <p className="text-xs text-slate-400 leading-relaxed">
            Choose which attributes to disclose to the verifier. Disclosed attributes will be packaged with their
            256-bit blinding salts and sibling Merkle proofs ascending to the on-chain Merkle root.
            <strong className="text-emerald-400"> Undisclosed attributes are completely excluded from the payload</strong>,
            preventing rainbow-table and dictionary preimage attacks.
          </p>

          {presentationError && <AlertBanner error={presentationError} onDismiss={() => setPresentationError(null)} />}

          {/* Bound Challenge Indicator */}
          <div className="p-3 bg-slate-950/80 rounded-lg border border-slate-800 flex items-center justify-between text-xs">
            <span className="text-slate-400">Attached Challenge:</span>
            {activeChallenge ? (
              <span className="font-mono text-emerald-400 flex items-center gap-1.5">
                <CheckCircle2 className="w-3.5 h-3.5" />
                <span>Bound ({activeChallenge.challenge_id.substring(0, 8)}…)</span>
              </span>
            ) : (
              <span className="text-amber-400 font-medium">None (Warning: Replay protection recommended)</span>
            )}
          </div>

          {/* Attribute Selection Table */}
          <div className="space-y-3">
            <div className="text-xs font-semibold uppercase tracking-wider text-slate-300">
              Select Attributes to Disclose (Concealed Claims Remain Strictly Private)
            </div>

            <div className="border border-slate-800 rounded-lg overflow-hidden divide-y divide-slate-800 bg-slate-950">
              {Object.entries(rawAttributes).map(([k, v]) => {
                const isSelected = selectedDisclosedKeys.includes(k);
                const isSensitive = k.toLowerCase().includes('ssn') || k.toLowerCase().includes('social');
                return (
                  <div
                    key={k}
                    onClick={() => toggleKey(k)}
                    className={`p-3.5 flex items-center justify-between gap-4 cursor-pointer transition-colors ${
                      isSelected
                        ? 'bg-brand-950/40 text-slate-100'
                        : 'bg-slate-950/40 text-slate-400 hover:bg-slate-900/50'
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={() => {}} // Controlled by div click
                        className="w-4 h-4 rounded text-brand-600 focus:ring-brand-500 bg-slate-800 border-slate-700"
                      />
                      <div>
                        <div className="text-xs font-mono font-semibold flex items-center gap-2">
                          <span>{k}</span>
                          {isSensitive && (
                            <span className="text-[10px] bg-rose-950 text-rose-300 border border-rose-800 px-1.5 py-0.2 rounded font-sans">
                              Sensitive PII
                            </span>
                          )}
                        </div>
                        <div className="text-[11px] text-slate-400 font-mono mt-0.5">{v}</div>
                      </div>
                    </div>

                    <div className="text-right shrink-0">
                      <span
                        className={`text-[11px] font-semibold px-2 py-0.5 rounded ${
                          isSelected
                            ? 'bg-emerald-950 text-emerald-300 border border-emerald-800'
                            : 'bg-slate-800 text-slate-400'
                        }`}
                      >
                        {isSelected ? 'DISCLOSE' : 'CONCEAL'}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Resulting Presentation Preview */}
          {presentation && (
            <div className="p-4 bg-slate-950 border border-emerald-800/80 rounded-lg space-y-3 text-xs animate-in fade-in">
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-2 text-emerald-400 font-semibold">
                  <CheckCircle2 className="w-4 h-4" />
                  <span>Presentation Generated Successfully</span>
                </span>
                <span className="text-slate-400 font-mono">
                  {presentation.disclosed_claims.length} claims disclosed
                </span>
              </div>

              <div className="space-y-2 text-[11px] font-mono text-slate-300">
                <div>Fingerprint: <HashBadge hash={presentation.credential_fingerprint} /></div>
                <div>Merkle Root: <HashBadge hash={presentation.merkle_root} /></div>
                <div className="p-2 bg-slate-900 rounded border border-slate-800 text-emerald-300">
                  Revealed Claims: {presentation.disclosed_claims.map((c) => `${c.key}="${c.value}"`).join(', ')}
                </div>
              </div>
            </div>
          )}

          <div className="flex justify-end gap-3 pt-4">
            <button
              type="button"
              disabled={isGeneratingPresentation}
              onClick={handleGeneratePresentation}
              className="px-6 py-2.5 bg-brand-600 hover:bg-brand-500 text-white rounded-lg text-xs font-semibold tracking-wide transition-colors flex items-center gap-2 disabled:opacity-50"
            >
              {isGeneratingPresentation ? <LoadingSpinner size="sm" /> : <EyeOff className="w-4 h-4" />}
              <span>Generate Selective Disclosure Presentation</span>
            </button>
          </div>
        </div>
      )}

      {/* Tab 3: Verify Presentation & Challenge */}
      {activeTab === 'verify' && (
        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-6 space-y-6 animate-in fade-in">
          <div className="flex items-center gap-2 border-b border-slate-800 pb-3">
            <ShieldCheck className="w-5 h-5 text-brand-400" />
            <h2 className="text-base font-semibold text-slate-100">Step 3: Verifier Presentation & Challenge Verification</h2>
          </div>

          <p className="text-xs text-slate-400 leading-relaxed">
            The verifier submits the presentation payload along with their session ID. The backend executes:
            1) Merkle proof verification for each disclosed leaf;
            2) Atomic compare-and-set consumption of the challenge nonce (single-use replay rejection);
            3) 6-component composite fingerprint reconstruction;
            4) Authoritative database & smart contract query.
          </p>

          {verifyError && <AlertBanner error={verifyError} onDismiss={() => setVerifyError(null)} />}

          {/* Presentation payload info */}
          <div className="p-4 bg-slate-950 rounded-lg border border-slate-800 space-y-2 text-xs">
            <div className="flex items-center justify-between text-slate-300">
              <span className="font-semibold uppercase tracking-wider text-[11px] text-slate-400">
                Ready Presentation Payload
              </span>
              <span className="font-mono text-emerald-400">
                {presentation ? 'Presentation Loaded' : 'No Presentation'}
              </span>
            </div>

            {presentation ? (
              <div className="font-mono text-[11px] text-slate-400 space-y-1">
                <div>Credential ID: {presentation.credential_id}</div>
                <div>Disclosed Claims: {presentation.disclosed_claims.map((c) => c.key).join(', ')}</div>
                <div>Bound Nonce: {presentation.challenge_nonce || 'None'}</div>
              </div>
            ) : (
              <p className="text-amber-400">
                Please generate a disclosure presentation in Step 2 before executing verification.
              </p>
            )}
          </div>

          <div className="flex justify-between items-center pt-2">
            <div className="text-xs text-slate-500 font-mono">
              Verifier Session: {verifierSessionId}
            </div>

            <button
              type="button"
              disabled={isVerifyingPresentation || !presentation}
              onClick={handleVerifyPresentation}
              className="px-6 py-2.5 bg-brand-600 hover:bg-brand-500 text-white rounded-lg text-xs font-semibold tracking-wide transition-colors flex items-center gap-2 disabled:opacity-50 shadow-lg shadow-brand-950"
            >
              {isVerifyingPresentation ? <LoadingSpinner size="sm" /> : <ShieldCheck className="w-4 h-4" />}
              <span>Verify Presentation & Consume Challenge</span>
            </button>
          </div>

          {/* Verification Outcome */}
          {verifyOutcome && (
            <div className="space-y-4 pt-4 border-t border-slate-800 animate-in fade-in">
              <div
                className={`p-5 rounded-xl border flex items-center justify-between gap-4 ${
                  verifyOutcome.overall_valid
                    ? 'bg-emerald-950/40 border-emerald-800/80 text-emerald-100'
                    : 'bg-rose-950/40 border-rose-800/80 text-rose-100'
                }`}
              >
                <div className="flex items-center gap-3">
                  <div
                    className={`p-2 rounded-lg ${
                      verifyOutcome.overall_valid
                        ? 'bg-emerald-900/60 text-emerald-300'
                        : 'bg-rose-900/60 text-rose-300'
                    }`}
                  >
                    {verifyOutcome.overall_valid ? (
                      <CheckCircle2 className="w-6 h-6" />
                    ) : (
                      <AlertTriangle className="w-6 h-6" />
                    )}
                  </div>
                  <div>
                    <h3 className="text-base font-bold">
                      {verifyOutcome.overall_valid
                        ? 'Presentation Verified Valid'
                        : 'Presentation Verification Failed'}
                    </h3>
                    <p className="text-xs opacity-90 mt-0.5">
                      Merkle proofs and challenge nonce authenticated.
                    </p>
                  </div>
                </div>

                <StatusBadge status={verifyOutcome.overall_valid ? 'VALID' : 'INVALID'} size="md" />
              </div>

              {/* Verified Disclosed Attributes Card */}
              <div className="p-4 bg-slate-950 rounded-xl border border-slate-800 space-y-3">
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-300">
                  Cryptographically Verified Disclosed Claims
                </span>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                  {Object.entries(verifyOutcome.disclosed_attributes).map(([k, v]) => (
                    <div key={k} className="p-3 bg-slate-900 rounded-lg border border-slate-800">
                      <span className="text-slate-500 font-mono text-[11px] block">{k}:</span>
                      <span className="text-emerald-300 font-semibold font-mono text-sm">{v}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* 4-Gate Check Summary */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                <div className="p-3 bg-slate-950 rounded border border-slate-800 space-y-1">
                  <span className="text-slate-500 block">Merkle Proofs</span>
                  <StatusBadge
                    status={verifyOutcome.selective_disclosure_valid ? 'VALID' : 'INVALID'}
                    size="sm"
                  />
                </div>
                <div className="p-3 bg-slate-950 rounded border border-slate-800 space-y-1">
                  <span className="text-slate-500 block">Challenge Consumed</span>
                  <StatusBadge
                    status={verifyOutcome.challenge_verified ? 'VALID' : 'INVALID'}
                    size="sm"
                  />
                </div>
                <div className="p-3 bg-slate-950 rounded border border-slate-800 space-y-1">
                  <span className="text-slate-500 block">Fingerprint Binding</span>
                  <StatusBadge
                    status={verifyOutcome.fingerprint_verified ? 'VALID' : 'INVALID'}
                    size="sm"
                  />
                </div>
                <div className="p-3 bg-slate-950 rounded border border-slate-800 space-y-1">
                  <span className="text-slate-500 block">Database Status</span>
                  <span className="font-mono text-slate-200">{verifyOutcome.database_status}</span>
                </div>
              </div>

              {/* Privacy Notice from Server */}
              <div className="p-3.5 bg-slate-950/80 rounded border border-slate-800 text-[11px] text-slate-400 leading-relaxed">
                <strong>Privacy & Linkability Notice:</strong> {verifyOutcome.privacy_notice}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
