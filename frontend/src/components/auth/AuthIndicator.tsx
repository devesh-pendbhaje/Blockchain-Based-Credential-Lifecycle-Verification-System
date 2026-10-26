import React, { useState } from 'react';
import { useAuth } from '@/context/AuthContext';
import { ShieldAlert, LogIn, LogOut, ChevronDown } from 'lucide-react';
import { AuthModal } from './AuthModal';

export const AuthIndicator: React.FC = () => {
  const { user, isAuthenticated, status, logout } = useAuth();
  const [isModalOpen, setIsModalOpen] = useState(false);

  return (
    <>
      <div className="flex items-center gap-2">
        {isAuthenticated && user ? (
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setIsModalOpen(true)}
              className="flex items-center gap-2 px-2.5 py-1.5 rounded-lg bg-slate-850 hover:bg-slate-800 border border-slate-750 transition-colors text-xs font-medium text-slate-200"
              title={`Logged in as ${user.sub}`}
            >
              <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              <div className="flex flex-col text-left">
                <span className="font-semibold text-slate-200 uppercase tracking-wider text-[10px]">
                  {user.roles[0] || 'Authenticated'}
                </span>
                <span className="text-[10px] text-slate-400 font-mono truncate max-w-[90px]">
                  {user.sub}
                </span>
              </div>
              <ChevronDown className="w-3.5 h-3.5 text-slate-400 ml-0.5" />
            </button>

            <button
              type="button"
              onClick={logout}
              className="p-1.5 rounded-lg text-slate-400 hover:text-rose-400 hover:bg-slate-800 transition-colors"
              title="Sign Out"
              aria-label="Sign Out"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        ) : status === 'expired' ? (
          <button
            type="button"
            onClick={() => setIsModalOpen(true)}
            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-amber-950/80 hover:bg-amber-900/80 border border-amber-700 text-amber-300 transition-colors text-xs font-medium"
          >
            <ShieldAlert className="w-3.5 h-3.5 text-amber-400" />
            <span>Session Expired</span>
          </button>
        ) : (
          <button
            type="button"
            id="sign-in-btn"
            data-testid="sign-in-btn"
            onClick={() => setIsModalOpen(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-brand-600 hover:bg-brand-500 text-white transition-colors text-xs font-semibold shadow-sm shadow-brand-950 border border-brand-500/80 cursor-pointer"
          >
            <LogIn className="w-3.5 h-3.5 text-white" />
            <span>Sign In</span>
          </button>
        )}
      </div>

      <AuthModal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} />
    </>
  );
};
