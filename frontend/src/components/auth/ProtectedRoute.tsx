import React, { useState } from 'react';
import { useAuth } from '@/context/AuthContext';
import { ShieldAlert, Lock, LogIn } from 'lucide-react';
import { AuthModal } from './AuthModal';

interface ProtectedRouteProps {
  requiredRole?: string;
  children: React.ReactNode;
}

export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ requiredRole, children }) => {
  const { isAuthenticated, hasRole, user, status } = useAuth();
  const [isModalOpen, setIsModalOpen] = useState(false);

  // If unauthenticated or session expired:
  if (!isAuthenticated || status === 'expired') {
    return (
      <div className="max-w-2xl mx-auto my-12 p-8 bg-slate-900 border border-slate-800 rounded-xl text-center space-y-4 shadow-xl">
        <div className="w-12 h-12 mx-auto rounded-full bg-amber-950/80 border border-amber-700 flex items-center justify-center text-amber-400">
          <ShieldAlert className="w-6 h-6" />
        </div>
        <div>
          <h2 className="text-lg font-bold text-slate-100">
            {status === 'expired' ? 'Session Expired' : 'Authentication Required'}
          </h2>
          <p className="text-sm text-slate-400 mt-1 max-w-md mx-auto">
            This administrative route enforces institutional authentication. Please provide a valid OpenID Connect / OAuth 2.0 access token to proceed.
          </p>
        </div>

        <button
          type="button"
          onClick={() => setIsModalOpen(true)}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-brand-600 hover:bg-brand-500 text-white text-xs font-semibold shadow-md shadow-brand-950 transition-colors"
        >
          <LogIn className="w-4 h-4" />
          <span>Authenticate / Select Persona</span>
        </button>

        <AuthModal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} />
      </div>
    );
  }

  // If authenticated but missing required role:
  if (requiredRole && !hasRole(requiredRole)) {
    return (
      <div className="max-w-2xl mx-auto my-12 p-8 bg-slate-900 border border-slate-800 rounded-xl text-center space-y-4 shadow-xl">
        <div className="w-12 h-12 mx-auto rounded-full bg-rose-950/80 border border-rose-800 flex items-center justify-center text-rose-400">
          <Lock className="w-6 h-6" />
        </div>
        <div>
          <h2 className="text-lg font-bold text-slate-100">Insufficient Permissions (HTTP 403)</h2>
          <p className="text-sm text-slate-400 mt-1 max-w-md mx-auto">
            Your authenticated identity <code className="text-slate-300 font-mono">{user?.sub}</code> holds roles [
            <span className="text-slate-300 font-mono">{user?.roles.join(', ') || 'none'}</span>], but this view requires the <code className="text-brand-400 font-mono">{requiredRole}</code> role.
          </p>
        </div>

        <button
          type="button"
          onClick={() => setIsModalOpen(true)}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-750 border border-slate-700 text-slate-200 text-xs font-semibold transition-colors"
        >
          <LogIn className="w-4 h-4" />
          <span>Switch Institutional Persona</span>
        </button>

        <AuthModal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} />
      </div>
    );
  }

  return <>{children}</>;
};
