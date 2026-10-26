import React from 'react';
import { ShieldCheck, Server, Menu } from 'lucide-react';
import { SystemHealthIndicator } from '../status/SystemHealthIndicator';
import { AuthIndicator } from '../auth/AuthIndicator';

interface HeaderProps {
  onToggleSidebar?: () => void;
}

export const Header: React.FC<HeaderProps> = ({ onToggleSidebar }) => {
  const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

  return (
    <header className="h-16 bg-slate-900/90 backdrop-blur border-b border-slate-800 px-4 md:px-6 flex items-center justify-between sticky top-0 z-30">
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={onToggleSidebar}
          className="md:hidden p-2 text-slate-400 hover:text-slate-100 rounded-lg hover:bg-slate-800 transition-colors"
          aria-label="Toggle navigation menu"
        >
          <Menu className="w-5 h-5" />
        </button>

        <div className="flex items-center gap-2.5">
          <div className="p-2 bg-brand-950 border border-brand-800/80 rounded-lg text-brand-400">
            <ShieldCheck className="w-5 h-5" />
          </div>
          <div>
            <span className="font-bold tracking-tight text-slate-100 text-sm hidden sm:inline-block">
              Blockchain Credential Lifecycle
            </span>
            <div className="text-[10px] font-mono text-slate-400 flex items-center gap-1.5">
              <span>EVM + RFC 8785 + Salted Merkle</span>
            </div>
          </div>
        </div>
      </div>

      <div className="flex items-center gap-4">
        {/* API connection target badge */}
        <div className="hidden lg:flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-slate-850 border border-slate-750 text-[11px] font-mono text-slate-400">
          <Server className="w-3.5 h-3.5 text-slate-500" />
          <span>API:</span>
          <span className="text-slate-300">{apiBaseUrl}</span>
        </div>

        {/* Live health probe status */}
        <SystemHealthIndicator minimal />

        {/* Authentication identity status */}
        <AuthIndicator />
      </div>
    </header>
  );
};
