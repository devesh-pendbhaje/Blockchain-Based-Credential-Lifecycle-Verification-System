import React from 'react';
import { AlertCircle, CheckCircle2, Info, AlertTriangle, X } from 'lucide-react';
import { AppError } from '@/types/api';

export type AlertType = 'info' | 'success' | 'warning' | 'error';

interface AlertBannerProps {
  type?: AlertType;
  title?: string;
  message?: string;
  error?: AppError | null;
  onDismiss?: () => void;
  className?: string;
}

export const AlertBanner: React.FC<AlertBannerProps> = ({
  type = 'info',
  title,
  message,
  error,
  onDismiss,
  className = '',
}) => {
  // If error is passed, determine styling and messages from AppError
  const effectiveType: AlertType = error ? 'error' : type;
  const effectiveTitle = title || (error ? (error.errorCode || 'Request Failed') : undefined);
  const effectiveMessage = message || (error ? error.message : undefined);

  const styles = {
    info: {
      bg: 'bg-blue-950/40 border-blue-800/60 text-blue-200',
      icon: <Info className="w-5 h-5 text-blue-400 shrink-0 mt-0.5" />,
    },
    success: {
      bg: 'bg-emerald-950/40 border-emerald-800/60 text-emerald-200',
      icon: <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0 mt-0.5" />,
    },
    warning: {
      bg: 'bg-amber-950/40 border-amber-800/60 text-amber-200',
      icon: <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />,
    },
    error: {
      bg: 'bg-rose-950/40 border-rose-800/60 text-rose-200',
      icon: <AlertCircle className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />,
    },
  }[effectiveType];

  return (
    <div
      role="alert"
      className={`border rounded-lg p-4 flex gap-3 text-sm transition-all duration-200 ${styles.bg} ${className}`}
    >
      {styles.icon}
      <div className="flex-1 space-y-1">
        {effectiveTitle && (
          <h4 className="font-semibold text-slate-100 tracking-wide">{effectiveTitle}</h4>
        )}
        {effectiveMessage && <p className="leading-relaxed opacity-95">{effectiveMessage}</p>}
        {error?.details && error.details.length > 0 && (
          <ul className="list-disc list-inside mt-2 space-y-1 text-xs opacity-85 font-mono">
            {error.details.map((detail, idx) => (
              <li key={idx}>
                {detail.loc ? `${detail.loc.join('.')}: ` : ''}
                {detail.msg}
              </li>
            ))}
          </ul>
        )}
      </div>
      {onDismiss && (
        <button
          onClick={onDismiss}
          className="text-slate-400 hover:text-slate-100 shrink-0 p-1 -mr-1 -mt-1 rounded focus:outline-none focus:ring-1 focus:ring-slate-400"
          aria-label="Dismiss alert"
        >
          <X className="w-4 h-4" />
        </button>
      )}
    </div>
  );
};
