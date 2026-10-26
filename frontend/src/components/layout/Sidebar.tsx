import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  Building2,
  FilePlus,
  ShieldCheck,
  EyeOff,
  Database,
  Search,
  BookOpen,
  Wallet,
} from 'lucide-react';

interface SidebarProps {
  isOpen?: boolean;
  onClose?: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ isOpen = false, onClose }) => {
  const navItems = [
    {
      to: '/',
      label: 'Overview Dashboard',
      icon: LayoutDashboard,
      description: 'Infrastructure & Protocol Status',
    },
    {
      to: '/wallet',
      label: 'Holder Wallet',
      icon: Wallet,
      description: 'Sovereign Credentials & QR Pass',
    },
    {
      to: '/issuers',
      label: 'Issuer Management',
      icon: Building2,
      description: 'Accredited Authorities Registry',
    },
    {
      to: '/credentials/issue',
      label: 'Credential Issuance',
      icon: FilePlus,
      description: 'Salted Merkle & Fingerprinting',
    },
    {
      to: '/credentials',
      label: 'Credential Lifecycle',
      icon: Search,
      description: 'Versions & Audit Explorer',
    },
    {
      to: '/verify',
      label: 'Public Verification',
      icon: ShieldCheck,
      description: 'Zero-Trust Fingerprint Query',
    },
    {
      to: '/presentations',
      label: 'Selective Disclosure',
      icon: EyeOff,
      description: 'Nonce Challenge & Claims',
    },
    {
      to: '/documents',
      label: 'Encrypted Documents',
      icon: Database,
      description: 'AES-256-GCM Storage & JCS',
    },
  ];

  return (
    <>
      {/* Mobile Backdrop */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/70 backdrop-blur-sm z-40 md:hidden"
          onClick={onClose}
        />
      )}

      {/* Sidebar container */}
      <aside
        className={`fixed md:sticky top-0 md:top-16 z-40 h-full md:h-[calc(100vh-4rem)] w-64 bg-slate-900 border-r border-slate-800 flex flex-col justify-between transition-transform duration-200 ease-in-out ${
          isOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'
        }`}
      >
        <div className="p-4 space-y-6 overflow-y-auto">
          <div className="space-y-1">
            <span className="text-[10px] font-mono uppercase tracking-wider text-slate-500 font-semibold px-3">
              Platform Workflows
            </span>
            <nav className="space-y-1 pt-1">
              {navItems.map((item) => {
                const Icon = item.icon;
                return (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    end={item.to === '/'}
                    onClick={onClose}
                    className={({ isActive }) =>
                      `flex items-start gap-3 px-3 py-2.5 rounded-lg text-xs transition-colors ${
                        isActive
                          ? 'bg-brand-950/70 border border-brand-800/80 text-brand-300 font-semibold'
                          : 'text-slate-400 hover:text-slate-100 hover:bg-slate-800/60'
                      }`
                    }
                  >
                    <Icon className="w-4 h-4 shrink-0 mt-0.5" />
                    <div>
                      <div className="leading-snug">{item.label}</div>
                      <div className="text-[10px] text-slate-500 font-normal leading-tight mt-0.5">
                        {item.description}
                      </div>
                    </div>
                  </NavLink>
                );
              })}
            </nav>
          </div>

          {/* Cryptographic Architecture Card */}
          <div className="p-3 bg-slate-950/60 border border-slate-800 rounded-lg space-y-2">
            <div className="flex items-center gap-1.5 text-[11px] font-semibold text-slate-300">
              <BookOpen className="w-3.5 h-3.5 text-brand-400" />
              <span>Core Invariant</span>
            </div>
            <p className="text-[11px] text-slate-400 leading-relaxed font-mono">
              6-Input Keccak-256 Composite Fingerprint
            </p>
            <div className="text-[10px] text-slate-500 leading-tight">
              Doc Digest (SHA-256) + Meta (Keccak-256) + Merkle Root + Issuer + CredID + Version.
            </div>
          </div>
        </div>

        <div className="p-4 border-t border-slate-800 text-[11px] text-slate-500 flex items-center justify-between">
          <span>Phase 4: Frontend Portal</span>
          <span className="font-mono text-[10px] text-emerald-400">Strict TypeScript</span>
        </div>
      </aside>
    </>
  );
};
