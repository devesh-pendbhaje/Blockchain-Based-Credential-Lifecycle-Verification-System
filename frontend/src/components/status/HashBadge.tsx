import React, { useState } from 'react';
import { Copy, Check } from 'lucide-react';
import { formatHash, copyToClipboard } from '@/utils/cryptoFormat';

interface HashBadgeProps {
  hash: string | null | undefined;
  label?: string;
  truncate?: boolean;
  className?: string;
}

export const HashBadge: React.FC<HashBadgeProps> = ({
  hash,
  label,
  truncate = true,
  className = '',
}) => {
  const [copied, setCopied] = useState(false);

  if (!hash) {
    return <span className="text-slate-500 font-mono text-xs">—</span>;
  }

  const handleCopy = async (e: React.MouseEvent) => {
    e.stopPropagation();
    const success = await copyToClipboard(hash);
    if (success) {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const display = truncate ? formatHash(hash) : hash;

  return (
    <div className={`inline-flex items-center gap-1.5 bg-slate-900 border border-slate-700/60 rounded px-2 py-0.5 max-w-full font-mono text-xs text-slate-300 ${className}`}>
      {label && <span className="text-slate-500 font-sans text-[11px] uppercase tracking-wider">{label}:</span>}
      <span className="truncate select-all text-brand-300 hover:text-brand-200 transition-colors" title={hash}>
        {display}
      </span>
      <button
        type="button"
        onClick={handleCopy}
        aria-label="Copy hash to clipboard"
        className="text-slate-400 hover:text-slate-100 transition-colors p-0.5 rounded focus:outline-none focus:ring-1 focus:ring-brand-500"
      >
        {copied ? (
          <Check className="w-3.5 h-3.5 text-emerald-400" />
        ) : (
          <Copy className="w-3.5 h-3.5" />
        )}
      </button>
    </div>
  );
};
