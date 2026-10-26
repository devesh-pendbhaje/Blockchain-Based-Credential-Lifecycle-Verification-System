import React from 'react';
import { Link } from 'react-router-dom';
import {
  ShieldCheck,
  Building2,
  FilePlus,
  EyeOff,
  Database,
  ArrowRight,
  Lock,
  Layers,
  Cpu,
  CheckCircle2,
} from 'lucide-react';
import { PageHeader } from '@/components/layout/PageHeader';
import { SystemHealthIndicator } from '@/components/status/SystemHealthIndicator';

export const DashboardPage: React.FC = () => {

  const workflowCards = [
    {
      title: 'Issuer Management',
      description: 'Register and inspect accredited institutions, signing addresses, and on-chain lifecycle standing.',
      icon: Building2,
      to: '/issuers',
      cta: 'Manage Issuers',
      color: 'border-blue-800/40 hover:border-blue-600/60',
      badge: 'Registry',
    },
    {
      title: 'Guided Credential Issuance',
      description: 'Upload certificate, canonicalize metadata (RFC 8785), generate salted Merkle trees, and compute composite fingerprints.',
      icon: FilePlus,
      to: '/credentials/issue',
      cta: 'Issue Credential',
      color: 'border-indigo-800/40 hover:border-indigo-600/60',
      badge: 'Issuance',
    },
    {
      title: 'Authoritative Verification',
      description: 'Zero-trust verification query evaluating database records, live blockchain state, dynamic expiration, and digest integrity.',
      icon: ShieldCheck,
      to: '/verify',
      cta: 'Verify Fingerprint',
      color: 'border-emerald-800/40 hover:border-emerald-600/60',
      badge: 'Zero-Trust',
    },
    {
      title: 'Selective Disclosure & Challenge',
      description: 'Issue replay-protected verifier nonce challenges and generate verifiable presentations disclosing only selected claims.',
      icon: EyeOff,
      to: '/presentations',
      cta: 'Disclose & Verify',
      color: 'border-purple-800/40 hover:border-purple-600/60',
      badge: 'Privacy (GDPR)',
    },
    {
      title: 'Encrypted Certificate Storage',
      description: 'AES-256-GCM envelope encryption at rest, UUID object isolation, and RFC 8785 canonical metadata digests.',
      icon: Database,
      to: '/documents',
      cta: 'Inspect Storage',
      color: 'border-slate-800 hover:border-slate-600',
      badge: 'Storage',
    },
  ];

  return (
    <div className="space-y-8 animate-in fade-in">
      <PageHeader
        title="Decentralized Credential Lifecycle Platform"
        description="Enterprise-grade credential anchoring and privacy-preserving verification system. Cryptographically anchored on EVM ledgers without public disclosure of Personal Identifiable Information (Zero-PII)."
      />

      {/* Live Infrastructure Connectivity Panel */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-300 flex items-center gap-2">
            <Cpu className="w-4 h-4 text-brand-400" />
            <span>Infrastructure Connectivity</span>
          </h2>
          <span className="text-xs font-mono text-slate-500">FastAPI + PostgreSQL + Hardhat Node</span>
        </div>

        <SystemHealthIndicator />
      </div>

      {/* Primary Workflows Grid */}
      <div className="space-y-4">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-300 flex items-center gap-2">
          <Layers className="w-4 h-4 text-brand-400" />
          <span>Operational Workflows</span>
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {workflowCards.map((card) => {
            const Icon = card.icon;
            return (
              <div
                key={card.to}
                className={`bg-slate-900/60 border rounded-xl p-5 flex flex-col justify-between transition-all duration-200 hover:shadow-xl ${card.color}`}
              >
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="p-2.5 bg-slate-800/80 rounded-lg text-brand-300">
                      <Icon className="w-5 h-5" />
                    </div>
                    <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-slate-800 text-slate-400">
                      {card.badge}
                    </span>
                  </div>

                  <h3 className="text-base font-semibold text-slate-100">{card.title}</h3>
                  <p className="text-xs text-slate-400 leading-relaxed">{card.description}</p>
                </div>

                <div className="pt-5 mt-auto">
                  <Link
                    to={card.to}
                    className="inline-flex items-center gap-1.5 text-xs font-semibold text-brand-400 hover:text-brand-300 transition-colors group"
                  >
                    <span>{card.cta}</span>
                    <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-1 transition-transform" />
                  </Link>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Cryptographic Specification & Security Guarantees */}
      <div className="bg-slate-900/40 border border-slate-800 rounded-xl p-6 space-y-5">
        <div className="flex items-center gap-2 text-slate-200">
          <Lock className="w-5 h-5 text-emerald-400" />
          <h2 className="text-base font-semibold">Authoritative Cryptographic Invariants</h2>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
          <div className="p-4 bg-slate-950/70 border border-slate-800/80 rounded-lg space-y-2">
            <div className="font-semibold text-slate-200 flex items-center gap-1.5">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
              <span>Zero-PII On-Chain</span>
            </div>
            <p className="text-slate-400 leading-relaxed">
              No certificate documents, student names, or plaintext attributes are stored on Ethereum.
              Only the 32-byte Merkle root and composite fingerprint exist on-chain.
            </p>
          </div>

          <div className="p-4 bg-slate-950/70 border border-slate-800/80 rounded-lg space-y-2">
            <div className="font-semibold text-slate-200 flex items-center gap-1.5">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
              <span>Salted Merkle Tree</span>
            </div>
            <p className="text-slate-400 leading-relaxed">
              Each attribute claim is blinded by a 256-bit cryptographically secure salt. Domain separators
              prevent second-preimage attacks and odd-leaf promotion preserves tree parity.
            </p>
          </div>

          <div className="p-4 bg-slate-950/70 border border-slate-800/80 rounded-lg space-y-2">
            <div className="font-semibold text-slate-200 flex items-center gap-1.5">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
              <span>Durable Replay Protection</span>
            </div>
            <p className="text-slate-400 leading-relaxed">
              Presentation verification requires consuming a dynamic, single-use 256-bit random nonce challenge
              bound to the verifier session, preventing credential presentation replay attacks.
            </p>
          </div>
        </div>

        {/* Mathematical Composite Fingerprint Equation */}
        <div className="p-4 bg-slate-950 border border-slate-800 rounded-lg space-y-2">
          <div className="text-[11px] font-mono uppercase tracking-wider text-slate-500 font-semibold">
            Authoritative Solidity Invariant (CredentialRegistry.sol)
          </div>
          <div className="font-mono text-xs text-brand-300 overflow-x-auto p-2 bg-slate-900 rounded border border-slate-800">
            fingerprint = keccak256(abi.encode(documentDigest, metadataDigest, merkleRoot, issuerId, credentialId, version))
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2 text-[11px] text-slate-400 font-mono pt-1">
            <div>1. docDigest (SHA-256)</div>
            <div>2. metaDigest (RFC 8785)</div>
            <div>3. merkleRoot (32 bytes)</div>
            <div>4. issuerId (bytes32)</div>
            <div>5. credId (bytes32)</div>
            <div>6. version (uint32)</div>
          </div>
        </div>
      </div>
    </div>
  );
};
