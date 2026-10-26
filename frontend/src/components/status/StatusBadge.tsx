import React from 'react';

export type DisplayStatus =
  | 'ACTIVE'
  | 'SUSPENDED'
  | 'REVOKED'
  | 'SUPERSEDED'
  | 'EXPIRED'
  | 'PENDING_CONFIRMATION'
  | 'ISSUED'
  | 'VALID'
  | 'INVALID'
  | 'UNAVAILABLE'
  | 'CONNECTED'
  | 'DISCONNECTED'
  | string;

interface StatusBadgeProps {
  status: DisplayStatus | null | undefined;
  size?: 'sm' | 'md';
  className?: string;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({
  status,
  size = 'md',
  className = '',
}) => {
  const norm = (status || 'UNKNOWN').toUpperCase();

  const config: Record<string, { bg: string; text: string; dot: string; label: string }> = {
    ACTIVE: {
      bg: 'bg-emerald-950/60 border-emerald-800/60',
      text: 'text-emerald-300',
      dot: 'bg-emerald-400',
      label: 'Active',
    },
    VALID: {
      bg: 'bg-emerald-950/60 border-emerald-800/60',
      text: 'text-emerald-300',
      dot: 'bg-emerald-400',
      label: 'Verified Valid',
    },
    CONNECTED: {
      bg: 'bg-emerald-950/60 border-emerald-800/60',
      text: 'text-emerald-300',
      dot: 'bg-emerald-400',
      label: 'Connected',
    },
    ISSUED: {
      bg: 'bg-blue-950/60 border-blue-800/60',
      text: 'text-blue-300',
      dot: 'bg-blue-400',
      label: 'Issued',
    },
    SUSPENDED: {
      bg: 'bg-amber-950/60 border-amber-800/60',
      text: 'text-amber-300',
      dot: 'bg-amber-400',
      label: 'Suspended',
    },
    EXPIRED: {
      bg: 'bg-amber-950/60 border-amber-800/60',
      text: 'text-amber-300',
      dot: 'bg-amber-400',
      label: 'Expired',
    },
    PENDING_CONFIRMATION: {
      bg: 'bg-purple-950/60 border-purple-800/60',
      text: 'text-purple-300',
      dot: 'bg-purple-400',
      label: 'Pending Confirmation',
    },
    SUPERSEDED: {
      bg: 'bg-slate-800/60 border-slate-700/60',
      text: 'text-slate-400',
      dot: 'bg-slate-400',
      label: 'Superseded',
    },
    REVOKED: {
      bg: 'bg-rose-950/60 border-rose-800/60',
      text: 'text-rose-300',
      dot: 'bg-rose-400',
      label: 'Revoked',
    },
    INVALID: {
      bg: 'bg-rose-950/60 border-rose-800/60',
      text: 'text-rose-300',
      dot: 'bg-rose-400',
      label: 'Invalid',
    },
    DISCONNECTED: {
      bg: 'bg-rose-950/60 border-rose-800/60',
      text: 'text-rose-300',
      dot: 'bg-rose-400',
      label: 'Disconnected',
    },
    UNAVAILABLE: {
      bg: 'bg-slate-800/60 border-slate-700/60',
      text: 'text-slate-400',
      dot: 'bg-slate-500',
      label: 'Unavailable',
    },
  };

  const style = config[norm] || {
    bg: 'bg-slate-800/60 border-slate-700/60',
    text: 'text-slate-300',
    dot: 'bg-slate-400',
    label: norm,
  };

  const sizeClasses = size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-1 text-xs';

  return (
    <span
      className={`inline-flex items-center gap-1.5 font-medium rounded-full border ${style.bg} ${style.text} ${sizeClasses} ${className}`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${style.dot}`} />
      <span>{style.label}</span>
    </span>
  );
};
