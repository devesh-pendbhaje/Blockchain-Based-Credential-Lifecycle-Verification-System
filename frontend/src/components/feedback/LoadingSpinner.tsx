import React from 'react';
import { Loader2 } from 'lucide-react';

interface LoadingSpinnerProps {
  size?: 'sm' | 'md' | 'lg';
  label?: string;
  className?: string;
}

export const LoadingSpinner: React.FC<LoadingSpinnerProps> = ({
  size = 'md',
  label,
  className = '',
}) => {
  const sizeMap = {
    sm: 'w-4 h-4',
    md: 'w-6 h-6',
    lg: 'w-10 h-10',
  };

  return (
    <div className={`flex flex-col items-center justify-center gap-2 p-4 text-slate-400 ${className}`}>
      <Loader2 className={`${sizeMap[size]} animate-spin text-brand-500`} />
      {label && <span className="text-sm font-medium text-slate-400">{label}</span>}
    </div>
  );
};
