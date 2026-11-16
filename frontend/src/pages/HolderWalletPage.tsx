import React, { useEffect, useState, useSyncExternalStore } from 'react';
import { useNavigate } from 'react-router-dom';
import { PageHeader } from '@/components/layout/PageHeader';
import { HashBadge } from '@/components/status/HashBadge';
import { VerificationBreakdown } from '@/components/status/VerificationBreakdown';
import { CredentialQrModal } from '@/components/qr/CredentialQrModal';
import { holderPackages, decryptPackage } from '@/services/holderPackages';
import { credentialApi } from '@/services/credentialApi';
import { tokenStore } from '@/services/tokenStore';
import { CredentialPackage, VerificationResponse } from '@/types/credential';

export const HolderWalletPage: React.FC = () => {
  const navigate = useNavigate();
  const packages = useSyncExternalStore(holderPackages.subscribe, holderPackages.getSnapshot);
  const [passphrase, setPassphrase] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [results, setResults] = useState<Record<string, VerificationResponse>>({});
  const [qr, setQr] = useState<CredentialPackage | null>(null);
  useEffect(() => tokenStore.subscribe(() => {
    setQr(null); setPassphrase(''); setFile(null); setResults({}); setError('');
  }), []);
  const importPackage = async (e: React.FormEvent) => {
    e.preventDefault(); setError(''); setBusy(true);
    const identity = tokenStore.getToken();
    try {
      if (!file || file.size > 1000000) throw new Error('Select an encrypted package smaller than 1 MB.');
      const pkg = await decryptPackage(await file.text(), passphrase);
      if (identity !== tokenStore.getToken()) return;
      holderPackages.add(pkg);
      setPassphrase(''); setFile(null);
    } catch (e) { setError(e instanceof Error ? e.message : 'Import failed'); }
    finally { setBusy(false); }
  };
  const verify = async (pkg: CredentialPackage) => {
    setError('');
    try { const result = await credentialApi.verifyCredential(pkg.fingerprint); setResults(prev => ({...prev, [pkg.fingerprint]: result})); }
    catch { setError('Verification is unavailable. Try again when the service is reachable.'); }
  };
  return <div className="space-y-6">
    <PageHeader title="Holder Verifiable Credential Wallet" description="Unlock your encrypted package to verify or disclose selected claims. Packages stay in memory and are cleared when you sign out or change identity." />
    <div className="rounded-xl border border-slate-700 bg-slate-900 p-5 space-y-4">
      <p>Total Held: <strong>{packages.length}</strong></p>
      <form onSubmit={importPackage} className="space-y-3">
        <label className="block text-sm">Encrypted holder package
          <input aria-label="Encrypted holder package" type="file" accept=".json,.credential" className="block mt-2" onChange={e => setFile(e.target.files?.[0] || null)} />
        </label>
        <label className="block text-sm">Package passphrase
          <input aria-label="Package passphrase" type="password" autoComplete="off" value={passphrase} onChange={e => setPassphrase(e.target.value)} className="block mt-2 p-2 bg-slate-950 border border-slate-700 rounded" />
        </label>
        <button disabled={busy || !file} className="px-4 py-2 bg-brand-600 rounded disabled:opacity-50">{busy ? 'Unlocking…' : 'Unlock and import'}</button>
      </form>
      {error && <p role="alert" className="text-rose-300">{error}</p>}
      {!packages.length && <p className="text-slate-400 text-sm">Import the encrypted file received from your issuer. Sign in as Holder before importing to create a presentation.</p>}
    </div>
    {packages.map(pkg => <div key={pkg.fingerprint} className="rounded-xl border border-slate-700 bg-slate-900 p-5 space-y-4">
      <h2 className="font-semibold">Credential v{pkg.version}</h2>
      <HashBadge hash={pkg.credential_id} label="Credential ID" />
      <HashBadge hash={pkg.fingerprint} label="Fingerprint" />
      <p className="text-sm text-slate-400">Package imported. Live verification establishes its current status.</p>
      <div className="flex gap-3">
        <button className="px-3 py-2 bg-brand-600 rounded" onClick={() => verify(pkg)}>Verify now</button>
        <button className="px-3 py-2 bg-purple-800 rounded" onClick={() => {holderPackages.select(pkg.fingerprint); navigate('/presentations');}}>Present selected claims</button>
        <button className="px-3 py-2 bg-slate-700 rounded" onClick={() => setQr(pkg)}>QR Pass</button>
      </div>
      {results[pkg.fingerprint] && <VerificationBreakdown result={results[pkg.fingerprint]} />}
    </div>)}
    {qr && <CredentialQrModal isOpen onClose={() => setQr(null)} fingerprint={qr.fingerprint} credentialId={qr.credential_id} version={qr.version} />}
  </div>;
};
