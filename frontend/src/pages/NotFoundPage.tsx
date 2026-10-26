import React from 'react';
import { Link } from 'react-router-dom';
import { ShieldAlert, Home } from 'lucide-react';

export const NotFoundPage: React.FC = () => {
  return (
    <div className="min-h-[70vh] flex flex-col items-center justify-center text-center p-6 space-y-5 animate-in fade-in">
      <div className="p-4 bg-slate-900 border border-slate-800 rounded-2xl text-rose-400">
        <ShieldAlert className="w-12 h-12" />
      </div>

      <div className="space-y-2">
        <h1 className="text-3xl font-bold tracking-tight text-slate-100">404: Endpoint Route Not Found</h1>
        <p className="text-sm text-slate-400 max-w-md leading-relaxed">
          The requested path does not map to any active credential workflow or administrative portal.
        </p>
      </div>

      <div className="flex gap-3 pt-2">
        <Link
          to="/"
          className="px-5 py-2.5 bg-brand-600 hover:bg-brand-500 text-white rounded-lg text-xs font-semibold tracking-wide transition-colors flex items-center gap-2 shadow-lg shadow-brand-950"
        >
          <Home className="w-4 h-4" />
          <span>Return to Dashboard</span>
        </Link>
      </div>
    </div>
  );
};
