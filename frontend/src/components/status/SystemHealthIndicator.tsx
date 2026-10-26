import React from 'react';
import { Database, Link, RefreshCw } from 'lucide-react';
import { useSystemHealth } from '@/hooks/useSystemHealth';
import { StatusBadge } from './StatusBadge';

interface SystemHealthIndicatorProps {
  minimal?: boolean;
}

export const SystemHealthIndicator: React.FC<SystemHealthIndicatorProps> = ({ minimal = false }) => {
  const { readiness, isLoading, error, refresh } = useSystemHealth();

  if (minimal) {
    const isReady = readiness?.status === 'ready';
    return (
      <div className="flex items-center gap-2">
        <span
          className={`w-2.5 h-2.5 rounded-full ${
            isReady ? 'bg-emerald-500 animate-pulse' : error ? 'bg-rose-500' : 'bg-amber-500'
          }`}
          title={isReady ? 'Backend operational' : error ? 'Backend unreachable' : 'Connecting...'}
        />
        <span className="text-xs font-mono text-slate-400">
          {isReady ? 'API Ready' : error ? 'Offline' : 'Connecting'}
        </span>
      </div>
    );
  }

  return (
    <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-4 flex flex-wrap items-center justify-between gap-4">
      <div className="flex flex-wrap items-center gap-6">
        {/* Database indicator */}
        <div className="flex items-center gap-2.5">
          <div className="p-1.5 bg-slate-800 rounded-lg text-slate-300">
            <Database className="w-4 h-4" />
          </div>
          <div>
            <div className="text-xs text-slate-400 font-medium">PostgreSQL Persistence</div>
            <div className="mt-0.5">
              <StatusBadge
                status={readiness?.database === 'connected' ? 'CONNECTED' : 'DISCONNECTED'}
                size="sm"
              />
            </div>
          </div>
        </div>

        {/* Blockchain RPC indicator */}
        <div className="flex items-center gap-2.5">
          <div className="p-1.5 bg-slate-800 rounded-lg text-slate-300">
            <Link className="w-4 h-4" />
          </div>
          <div>
            <div className="text-xs text-slate-400 font-medium">EVM Node (Hardhat/RPC)</div>
            <div className="mt-0.5">
              <StatusBadge
                status={readiness?.blockchain_rpc === 'connected' ? 'CONNECTED' : 'UNAVAILABLE'}
                size="sm"
              />
            </div>
          </div>
        </div>
      </div>

      <div className="flex items-center gap-3">
        {error && (
          <span className="text-xs text-rose-400">Connection error: {error.message}</span>
        )}
        <button
          onClick={refresh}
          disabled={isLoading}
          className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-200 p-1.5 rounded-lg hover:bg-slate-800 transition-colors disabled:opacity-50"
          title="Refresh connection status"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
          <span>Refresh</span>
        </button>
      </div>
    </div>
  );
};
