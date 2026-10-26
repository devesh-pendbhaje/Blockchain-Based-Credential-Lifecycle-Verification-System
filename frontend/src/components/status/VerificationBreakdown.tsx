import React from 'react';
import {
  ShieldCheck,
  ShieldAlert,
  Database,
  Link,
  Clock,
  Fingerprint,
  AlertTriangle,
} from 'lucide-react';
import { VerificationResponse } from '@/types/credential';
import { StatusBadge } from './StatusBadge';
import { formatDate } from '@/utils/date';

interface VerificationBreakdownProps {
  result: VerificationResponse;
  className?: string;
}

export const VerificationBreakdown: React.FC<VerificationBreakdownProps> = ({
  result,
  className = '',
}) => {
  const {
    fingerprint,
    database_found,
    blockchain_available,
    is_valid,
    lifecycle_status,
    is_expired,
    digest_match,
    blockchain_code,
    details,
    checked_at,
  } = result;

  return (
    <div className={`space-y-4 ${className}`}>
      {/* Authoritative Overall Banner */}
      <div
        className={`p-5 rounded-xl border flex flex-col md:flex-row md:items-center justify-between gap-4 ${
          is_valid
            ? 'bg-emerald-950/40 border-emerald-800/80 text-emerald-100'
            : !blockchain_available
            ? 'bg-amber-950/40 border-amber-800/80 text-amber-100'
            : 'bg-rose-950/40 border-rose-800/80 text-rose-100'
        }`}
      >
        <div className="flex items-start gap-3.5">
          <div
            className={`p-2.5 rounded-lg shrink-0 ${
              is_valid
                ? 'bg-emerald-900/60 text-emerald-300'
                : !blockchain_available
                ? 'bg-amber-900/60 text-amber-300'
                : 'bg-rose-900/60 text-rose-300'
            }`}
          >
            {is_valid ? (
              <ShieldCheck className="w-7 h-7" />
            ) : !blockchain_available ? (
              <AlertTriangle className="w-7 h-7" />
            ) : (
              <ShieldAlert className="w-7 h-7" />
            )}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-lg font-bold tracking-tight">
                {is_valid
                  ? 'Authoritative Verification: VALID'
                  : !blockchain_available
                  ? 'Verification Incomplete: BLOCKCHAIN UNAVAILABLE'
                  : 'Authoritative Verification: INVALID'}
              </h3>
            </div>
            <p className="text-sm opacity-90 mt-1">{details}</p>
            <div className="text-xs opacity-75 mt-1 font-mono">
              Evaluated at: {formatDate(checked_at)}
            </div>
          </div>
        </div>

        <div className="shrink-0 flex items-center gap-2">
          <StatusBadge status={is_valid ? 'VALID' : !blockchain_available ? 'UNAVAILABLE' : 'INVALID'} size="md" />
        </div>
      </div>

      {/* Warning when database found but blockchain unavailable */}
      {!blockchain_available && database_found && (
        <div className="p-3.5 rounded-lg bg-amber-950/30 border border-amber-800/50 text-amber-200 text-xs leading-relaxed flex gap-2">
          <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5 text-amber-400" />
          <span>
            <strong>Honest Verification Notice:</strong> This credential was found in the off-chain database,
            but smart contract verification is currently unavailable. In accordance with zero-trust architectural principles,
            a credential <strong>cannot</strong> be certified as verified without live on-chain state confirmation.
          </span>
        </div>
      )}

      {/* Discrete 5-Gate Verification Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        {/* Gate 1: Database Record */}
        <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-3.5 space-y-2">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span className="flex items-center gap-1.5 font-medium">
              <Database className="w-3.5 h-3.5" />
              Off-Chain Record
            </span>
            <span
              className={`w-2 h-2 rounded-full ${
                database_found ? 'bg-emerald-400' : 'bg-slate-600'
              }`}
            />
          </div>
          <div className="text-sm font-semibold text-slate-200">
            {database_found ? 'Record Located' : 'Not Found'}
          </div>
          <div className="text-xs text-slate-400">
            Lifecycle Status:{' '}
            <span className="font-mono text-slate-300">{lifecycle_status || 'N/A'}</span>
          </div>
        </div>

        {/* Gate 2: Blockchain Node */}
        <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-3.5 space-y-2">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span className="flex items-center gap-1.5 font-medium">
              <Link className="w-3.5 h-3.5" />
              On-Chain Query
            </span>
            <span
              className={`w-2 h-2 rounded-full ${
                blockchain_available ? 'bg-emerald-400' : 'bg-amber-400'
              }`}
            />
          </div>
          <div className="text-sm font-semibold text-slate-200">
            {blockchain_available ? 'Connected' : 'Unavailable'}
          </div>
          <div className="text-xs text-slate-400">
            Solidity Return Code:{' '}
            <span className="font-mono text-slate-300">{blockchain_code || 'None'}</span>
          </div>
        </div>

        {/* Gate 3: Expiration Check */}
        <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-3.5 space-y-2">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span className="flex items-center gap-1.5 font-medium">
              <Clock className="w-3.5 h-3.5" />
              Validity Period
            </span>
            <span
              className={`w-2 h-2 rounded-full ${
                is_expired === false
                  ? 'bg-emerald-400'
                  : is_expired === true
                  ? 'bg-rose-400'
                  : 'bg-slate-600'
              }`}
            />
          </div>
          <div className="text-sm font-semibold text-slate-200">
            {is_expired === false
              ? 'Unexpired'
              : is_expired === true
              ? 'Expired'
              : 'Unknown'}
          </div>
          <div className="text-xs text-slate-400">Dynamic block timestamp check</div>
        </div>

        {/* Gate 4: Digest Parity */}
        <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-3.5 space-y-2">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span className="flex items-center gap-1.5 font-medium">
              <Fingerprint className="w-3.5 h-3.5" />
              Digest Parity
            </span>
            <span
              className={`w-2 h-2 rounded-full ${
                digest_match === true
                  ? 'bg-emerald-400'
                  : digest_match === false
                  ? 'bg-rose-400'
                  : 'bg-slate-600'
              }`}
            />
          </div>
          <div className="text-sm font-semibold text-slate-200">
            {digest_match === true
              ? 'Integrity Verified'
              : digest_match === false
              ? 'Hash Mismatch'
              : 'Unchecked'}
          </div>
          <div className="text-xs text-slate-400 font-mono truncate" title={fingerprint}>
            FP: {fingerprint.substring(0, 10)}…
          </div>
        </div>
      </div>
    </div>
  );
};
