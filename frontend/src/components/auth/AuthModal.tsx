import React, { useState, useEffect } from 'react';
import { useAuth } from '@/context/AuthContext';
import { Shield, Key, UserCheck, Lock, AlertCircle, X, Loader2, CheckCircle2 } from 'lucide-react';
import { authApi } from '@/services/authApi';
import { AuthConfig } from '@/types/auth';

interface AuthModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const AuthModal: React.FC<AuthModalProps> = ({ isOpen, onClose }) => {
  const { user, isAuthenticated, login, logout, authError, clearError } = useAuth();
  const [customToken, setCustomToken] = useState('');
  const [tab, setTab] = useState<'personas' | 'token' | 'info'>('personas');
  const [isLoadingPersona, setIsLoadingPersona] = useState<string | null>(null);
  const [modalError, setModalError] = useState<string | null>(null);
  const [authConfig, setAuthConfig] = useState<AuthConfig | null>(null);

  useEffect(() => {
    if (isOpen) {
      setModalError(null);
      authApi.getAuthConfig()
        .then(setAuthConfig)
        .catch((err) => {
          console.warn('Could not retrieve auth config from backend:', err);
        });
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleSelectPersona = async (role: 'admin' | 'issuer' | 'verifier') => {
    setIsLoadingPersona(role);
    setModalError(null);
    clearError();

    try {
      const resp = await authApi.getDevToken({ persona: role });
      login(resp.access_token);
      onClose();
    } catch (err: unknown) {
      const errorMsg =
        (err as { message?: string })?.message ||
        'Failed to obtain dev token from backend. Ensure backend is running in development mode.';
      setModalError(errorMsg);
    } finally {
      setIsLoadingPersona(null);
    }
  };

  const handleCustomSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!customToken.trim()) return;
    setModalError(null);
    clearError();
    login(customToken.trim());
    if (!authError) {
      onClose();
    }
  };

  const activeError = modalError || authError;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
      <div className="bg-slate-900 border border-slate-750 rounded-xl max-w-lg w-full shadow-2xl overflow-hidden animate-fade-in">
        {/* Modal Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-slate-850/60">
          <div className="flex items-center gap-2.5">
            <div className="p-2 bg-brand-950 border border-brand-800 rounded-lg text-brand-400">
              <Shield className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-semibold text-slate-100">Institutional Identity & Authentication</h3>
              <p className="text-xs text-slate-400">OpenID Connect (OIDC) / OAuth 2.0 Security Boundary</p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-slate-400 hover:text-slate-200 p-1.5 rounded-lg hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Current Identity Banner */}
        <div className="px-6 py-3 bg-slate-950/50 border-b border-slate-800 flex items-center justify-between text-xs">
          <div className="flex items-center gap-2">
            <span className="text-slate-400">Current Status:</span>
            {isAuthenticated && user ? (
              <span className="px-2 py-0.5 rounded bg-emerald-950 border border-emerald-700 text-emerald-300 font-mono flex items-center gap-1.5">
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                <span>{user.roles.join(', ') || 'authenticated'} ({user.sub})</span>
              </span>
            ) : (
              <span className="px-2 py-0.5 rounded bg-amber-950 border border-amber-700 text-amber-300 font-mono">
                Unauthenticated
              </span>
            )}
          </div>
          {isAuthenticated && (
            <button
              type="button"
              onClick={logout}
              className="text-rose-400 hover:text-rose-300 hover:underline font-medium"
            >
              Sign Out
            </button>
          )}
        </div>

        {activeError && (
          <div className="m-4 p-3 rounded-lg bg-rose-950/80 border border-rose-800 text-rose-300 text-xs flex items-center justify-between">
            <div className="flex items-center gap-2">
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              <span>{activeError}</span>
            </div>
            <button
              type="button"
              onClick={() => {
                setModalError(null);
                clearError();
              }}
              className="text-rose-400 hover:text-rose-200 text-xs"
            >
              Dismiss
            </button>
          </div>
        )}

        {/* Tab Selection */}
        <div className="flex border-b border-slate-800 text-xs font-medium">
          <button
            type="button"
            onClick={() => setTab('personas')}
            className={`flex-1 py-2.5 text-center border-b-2 transition-colors ${
              tab === 'personas'
                ? 'border-brand-500 text-brand-400 bg-brand-950/20'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            Test Personas (Local)
          </button>
          <button
            type="button"
            onClick={() => setTab('token')}
            className={`flex-1 py-2.5 text-center border-b-2 transition-colors ${
              tab === 'token'
                ? 'border-brand-500 text-brand-400 bg-brand-950/20'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            Custom Bearer JWT
          </button>
          <button
            type="button"
            onClick={() => setTab('info')}
            className={`flex-1 py-2.5 text-center border-b-2 transition-colors ${
              tab === 'info'
                ? 'border-brand-500 text-brand-400 bg-brand-950/20'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            OIDC IdP Config
          </button>
        </div>

        {/* Tab Content */}
        <div className="p-6">
          {tab === 'personas' && (
            <div className="space-y-3">
              <p className="text-xs text-slate-400 leading-relaxed">
                Select an institutional persona. The backend issues a real RS256 JWT signed with its local development keypair and validates it cryptographically against full RBAC rules.
              </p>

              <div className="grid gap-2.5">
                <button
                  type="button"
                  disabled={isLoadingPersona !== null}
                  onClick={() => handleSelectPersona('admin')}
                  className="flex items-center justify-between p-3 rounded-lg border border-slate-800 bg-slate-800/40 hover:bg-slate-800 hover:border-brand-700 transition-all text-left disabled:opacity-60"
                >
                  <div className="flex items-center gap-3">
                    <div className="p-2 bg-purple-950/80 border border-purple-800 text-purple-300 rounded-md">
                      {isLoadingPersona === 'admin' ? <Loader2 className="w-4 h-4 animate-spin" /> : <Key className="w-4 h-4" />}
                    </div>
                    <div>
                      <div className="text-sm font-semibold text-slate-200">System Administrator</div>
                      <div className="text-xs text-slate-400">Roles: admin, issuer, verifier (Full platform access)</div>
                    </div>
                  </div>
                  <span className="text-xs px-2.5 py-1 rounded bg-purple-900/60 text-purple-200 border border-purple-700 font-medium">
                    {isLoadingPersona === 'admin' ? 'Signing...' : 'Sign In'}
                  </span>
                </button>

                <button
                  type="button"
                  disabled={isLoadingPersona !== null}
                  onClick={() => handleSelectPersona('issuer')}
                  className="flex items-center justify-between p-3 rounded-lg border border-slate-800 bg-slate-800/40 hover:bg-slate-800 hover:border-brand-700 transition-all text-left disabled:opacity-60"
                >
                  <div className="flex items-center gap-3">
                    <div className="p-2 bg-brand-950/80 border border-brand-800 text-brand-300 rounded-md">
                      {isLoadingPersona === 'issuer' ? <Loader2 className="w-4 h-4 animate-spin" /> : <UserCheck className="w-4 h-4" />}
                    </div>
                    <div>
                      <div className="text-sm font-semibold text-slate-200">Accredited Institutional Issuer</div>
                      <div className="text-xs text-slate-400">Role: issuer (Authorized for issuer authority records)</div>
                    </div>
                  </div>
                  <span className="text-xs px-2.5 py-1 rounded bg-brand-900/60 text-brand-200 border border-brand-700 font-medium">
                    {isLoadingPersona === 'issuer' ? 'Signing...' : 'Sign In'}
                  </span>
                </button>

                <button
                  type="button"
                  disabled={isLoadingPersona !== null}
                  onClick={() => handleSelectPersona('verifier')}
                  className="flex items-center justify-between p-3 rounded-lg border border-slate-800 bg-slate-800/40 hover:bg-slate-800 hover:border-brand-700 transition-all text-left disabled:opacity-60"
                >
                  <div className="flex items-center gap-3">
                    <div className="p-2 bg-emerald-950/80 border border-emerald-800 text-emerald-300 rounded-md">
                      {isLoadingPersona === 'verifier' ? <Loader2 className="w-4 h-4 animate-spin" /> : <Lock className="w-4 h-4" />}
                    </div>
                    <div>
                      <div className="text-sm font-semibold text-slate-200">Accredited Verifier / Auditor</div>
                      <div className="text-xs text-slate-400">Role: verifier (Issues & consumes cryptographic challenges)</div>
                    </div>
                  </div>
                  <span className="text-xs px-2.5 py-1 rounded bg-emerald-900/60 text-emerald-200 border border-emerald-700 font-medium">
                    {isLoadingPersona === 'verifier' ? 'Signing...' : 'Sign In'}
                  </span>
                </button>
              </div>
            </div>
          )}

          {tab === 'token' && (
            <form onSubmit={handleCustomSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                  Institutional JWT Access Token (Bearer)
                </label>
                <textarea
                  rows={4}
                  value={customToken}
                  onChange={(e) => setCustomToken(e.target.value)}
                  placeholder="eyJhbGciOiJSUzI1NiIs..."
                  className="w-full bg-slate-950 border border-slate-750 rounded-lg p-2.5 text-xs font-mono text-slate-200 focus:outline-none focus:border-brand-500"
                />
                <p className="text-[11px] text-slate-400 mt-1">
                  Token is kept in volatile browser memory only. No sensitive keys or tokens are stored in localStorage or sessionStorage.
                </p>
              </div>

              <div className="flex justify-end gap-2">
                <button
                  type="button"
                  onClick={onClose}
                  className="px-4 py-2 rounded-lg border border-slate-750 text-slate-300 hover:bg-slate-800 text-xs font-medium"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 rounded-lg bg-brand-600 hover:bg-brand-500 text-white text-xs font-medium shadow-md shadow-brand-900/40"
                >
                  Apply Token In-Memory
                </button>
              </div>
            </form>
          )}

          {tab === 'info' && (
            <div className="space-y-3 text-xs text-slate-300 leading-relaxed">
              <div className="p-3 bg-slate-950 border border-slate-800 rounded-lg space-y-2">
                <h4 className="font-semibold text-slate-200 flex items-center gap-1.5">
                  <Shield className="w-3.5 h-3.5 text-brand-400" /> Active Backend Configuration
                </h4>
                {authConfig ? (
                  <div className="space-y-1 font-mono text-[11px]">
                    <div className="text-slate-400">Environment: <span className="text-slate-200 font-semibold">{authConfig.environment}</span></div>
                    <div className="text-slate-400">Auth Mode: <span className="text-slate-200 font-semibold">{authConfig.auth_mode}</span></div>
                    <div className="text-slate-400 truncate">Issuer URL: <span className="text-slate-300">{authConfig.issuer_url}</span></div>
                    <div className="text-slate-400">Audience: <span className="text-slate-300">{authConfig.audience}</span></div>
                    <div className="text-slate-400">Allowed Algorithms: <span className="text-slate-300">{authConfig.allowed_algorithms.join(', ')}</span></div>
                  </div>
                ) : (
                  <div className="text-slate-400 text-[11px]">Loading configuration from API...</div>
                )}
              </div>

              <div className="p-3 bg-slate-950 border border-slate-800 rounded-lg">
                <h4 className="font-semibold text-slate-200 mb-1 flex items-center gap-1.5">
                  <Key className="w-3.5 h-3.5 text-amber-400" /> Production Identity Provider (IdP) Requirements
                </h4>
                <ul className="list-disc list-inside space-y-1 text-slate-400 text-[11px]">
                  <li>Institutional Identity Provider: Keycloak, Okta, PingFederate, or Auth0.</li>
                  <li>Set environment variables: <code className="text-slate-300">OIDC_ISSUER_URL</code> and <code className="text-slate-300">OIDC_AUDIENCE</code>.</li>
                  <li>Cryptographic verification via published JWKS endpoint (<code className="text-slate-300">/protocol/openid-connect/certs</code>).</li>
                  <li>In production (<code className="text-slate-300">ENVIRONMENT=production</code>), local dev personas are automatically disabled.</li>
                </ul>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
