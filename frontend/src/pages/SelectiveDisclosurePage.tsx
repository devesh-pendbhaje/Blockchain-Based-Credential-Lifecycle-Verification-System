import React, { useEffect, useState, useSyncExternalStore } from 'react';
import { Link } from 'react-router-dom';
import { PageHeader } from '@/components/layout/PageHeader';
import { Tabs } from '@/components/navigation/Tabs';
import { challengeApi } from '@/services/challengeApi';
import { presentationApi } from '@/services/presentationApi';
import { holderPackages, downloadText } from '@/services/holderPackages';
import { tokenStore } from '@/services/tokenStore';
import { ChallengeCreateResponse } from '@/types/challenge';
import { PresentationResponse, PresentationVerifyResponse } from '@/types/presentation';

export const SelectiveDisclosurePage: React.FC = () => {
  const packages = useSyncExternalStore(holderPackages.subscribe, holderPackages.getSnapshot);
  const [selected, setSelected] = useState(holderPackages.getSelected()?.fingerprint || '');
  const pkg = packages.find(p => p.fingerprint === selected);
  const [activeTab, setActiveTab] = useState('challenge');
  const [session, setSession] = useState(() => `session-${crypto.randomUUID()}`);
  const [challenge, setChallenge] = useState<ChallengeCreateResponse | null>(null);
  const [keys, setKeys] = useState<string[]>([]);
  const [presentation, setPresentation] = useState<PresentationResponse | null>(null);
  const [outcome, setOutcome] = useState<PresentationVerifyResponse | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => {setKeys([]); setPresentation(null); setOutcome(null);}, [selected]);
  useEffect(() => tokenStore.subscribe(() => {
    setChallenge(null); setPresentation(null); setOutcome(null); setKeys([]); setSelected('');
  }), []);
  const run = async (fn: () => Promise<void>) => {
    setError(''); setBusy(true);
    try {await fn();} catch (e: any) {setError(e.message || 'Operation failed');}
    finally {setBusy(false);}
  };
  const readJson = async (file: File | undefined) => {
    if (!file || file.size > 1000000) throw new Error('Choose a JSON file smaller than 1 MB.');
    return JSON.parse(await file.text());
  };
  const importChallenge = async (file: File | undefined) => {
    const value = await readJson(file);
    if (!value.challenge_id || !/^0x[0-9a-f]{64}$/i.test(value.challenge_nonce) || !value.verifier_session_id) throw new Error('Invalid challenge file.');
    setChallenge(value); setSession(value.verifier_session_id); setPresentation(null); setOutcome(null);
  };
  const generate = async () => {
    if (!pkg || !challenge || !keys.length) throw new Error('Select a package, import a verifier challenge, and choose at least one claim.');
    const result = await presentationApi.generatePresentation({credential_id:pkg.credential_id, issuer_id:pkg.issuer_id,
      version:pkg.version, attributes:pkg.attributes, salts:pkg.salts, disclosed_keys:keys,
      document_digest:pkg.document_digest, metadata_digest:pkg.metadata_digest,
      challenge_id:challenge.challenge_id, challenge_nonce:challenge.challenge_nonce});
    if (result.merkle_root.toLowerCase() !== pkg.merkle_root.toLowerCase() || result.credential_fingerprint.toLowerCase() !== pkg.fingerprint.toLowerCase()) throw new Error('Package does not reproduce the issued fingerprint and Merkle root.');
    setPresentation(result); setOutcome(null);
  };
  const unavailable = outcome && !outcome.overall_valid && outcome.selective_disclosure_valid &&
    outcome.fingerprint_verified && outcome.challenge_verified && outcome.database_status === 'ACTIVE' &&
    outcome.blockchain_verification.authoritative_verification_available === false;
  const button='px-4 py-2 bg-brand-600 rounded-lg disabled:opacity-50';
  return <div className="space-y-6">
    <PageHeader title="Privacy-Preserving Selective Disclosure" description="A verifier creates a challenge; the holder shares only selected claims; the same verifier checks the presentation once." />
    <Tabs tabs={[{id:'challenge',label:'1. Verifier challenge'},{id:'generate',label:'2. Holder presentation'},{id:'verify',label:'3. Verify presentation'}]} activeTab={activeTab} onChange={setActiveTab} />
    {error && <p role="alert" className="p-4 border border-rose-700 rounded text-rose-300">{error}</p>}
    {activeTab === 'challenge' && <section className="p-6 bg-slate-900 rounded-xl border border-slate-700 space-y-4">
      <h2 className="font-semibold">Request Verifier Nonce Challenge</h2>
      <p className="text-sm text-slate-400">Sign in as Verifier. Send the downloaded challenge to the holder. Keep the same verifier identity for the final check.</p>
      <label className="block">Verifier session ID <input aria-label="Verifier session ID" value={session} onChange={e=>setSession(e.target.value)} className="block p-2 bg-slate-950 border border-slate-700 w-full" /></label>
      <button disabled={busy} className={button} onClick={()=>run(async()=>{
        const ch=await challengeApi.createChallenge({verifier_session_id:session,expiry_seconds:300});setChallenge(ch);setOutcome(null);
      })}>Create challenge</button>
      {challenge && <div className="space-y-3"><p>Challenge expires: {challenge.expires_at}</p>
        <button className={button} onClick={()=>downloadText(JSON.stringify(challenge),'verifier-challenge.json')}>Download challenge</button>
      </div>}
    </section>}
    {activeTab === 'generate' && <section className="p-6 bg-slate-900 rounded-xl border border-slate-700 space-y-4">
      <h2 className="font-semibold">Select claims to disclose</h2>
      <p className="text-sm text-slate-400">Sign in as Holder, then unlock your encrypted package in the <Link className="text-brand-300 underline" to="/wallet">wallet</Link>. Import the verifier's challenge below.</p>
      <label className="block">Credential package <select aria-label="Credential package" value={selected} onChange={e=>setSelected(e.target.value)} className="block p-2 bg-slate-950 border border-slate-700 w-full">
        <option value="">Select an unlocked package</option>{packages.map(p=><option key={p.fingerprint} value={p.fingerprint}>{p.credential_id.slice(0,18)}… v{p.version}</option>)}
      </select></label>
      <label className="block">Verifier challenge file <input aria-label="Verifier challenge file" type="file" accept=".json" className="block mt-2" onChange={e=>run(()=>importChallenge(e.target.files?.[0]))} /></label>
      {challenge && <p className="text-sm text-emerald-300">Challenge loaded for {challenge.verifier_session_id}</p>}
      {pkg && Object.entries(pkg.attributes).map(([k,v])=><label key={k} className="flex items-start gap-3 p-3 bg-slate-950 rounded">
        <input type="checkbox" checked={keys.includes(k)} onChange={()=>setKeys(prev=>prev.includes(k)?prev.filter(x=>x!==k):[...prev,k])} />
        <span><strong>{k}</strong>: {v}</span>
      </label>)}
      <button disabled={busy||!pkg||!challenge||!keys.length} className={button} onClick={()=>run(generate)}>Generate presentation</button>
      {presentation && <div className="space-y-3"><p>Presentation prepared. It contains only the selected claim values and their proofs.</p>
        <button className={button} onClick={()=>downloadText(JSON.stringify({presentation,verifier_session_id:session}),'credential-presentation.json')}>Download presentation</button>
      </div>}
    </section>}
    {activeTab === 'verify' && <section className="p-6 bg-slate-900 rounded-xl border border-slate-700 space-y-4">
      <h2 className="font-semibold">Verify Presentation & Nonce</h2>
      <p className="text-sm text-slate-400">Sign in as the verifier who issued the challenge. Import the holder's presentation file. A used or expired challenge requires a fresh exchange.</p>
      <label className="block">Presentation file <input aria-label="Presentation file" type="file" accept=".json" className="block mt-2" onChange={e=>run(async()=>{
        const value=await readJson(e.target.files?.[0]);
        if(!value.presentation?.credential_fingerprint||!value.verifier_session_id)throw new Error('Invalid presentation file.');
        setPresentation(value.presentation);setSession(value.verifier_session_id);setOutcome(null);
      })} /></label>
      <button disabled={busy||!presentation} className={button} onClick={()=>run(async()=>{
        setOutcome(null);const result=await presentationApi.verifyPresentation({presentation:presentation as unknown as Record<string,unknown>,verifier_session_id:session,require_current_version:true});setOutcome(result);
      })}>Verify presentation</button>
      {outcome && <div role="status" className={`rounded-lg p-4 border ${outcome.overall_valid?'border-emerald-600 text-emerald-300':unavailable?'border-amber-600 text-amber-300':'border-rose-600 text-rose-300'}`}>
        <h3 className="font-bold">{outcome.overall_valid?'VALID':unavailable?'UNAVAILABLE':'INVALID'}</h3>
        <p>Merkle proof: {outcome.selective_disclosure_valid?'verified':'failed'} · Challenge: {outcome.challenge_verified?'verified':'failed'} · Blockchain: {outcome.blockchain_verification.code}</p>
        {Object.entries(outcome.disclosed_attributes).map(([k,v])=><p key={k}>{k}: {String(v)}</p>)}
      </div>}
    </section>}
  </div>;
};
