import React from 'react';

interface FormFieldProps {
  label: string;
  htmlFor?: string;
  description?: string;
  error?: string;
  required?: boolean;
  children: React.ReactNode;
  className?: string;
}

export const FormField: React.FC<FormFieldProps> = ({
  label,
  htmlFor,
  description,
  error,
  required = false,
  children,
  className = '',
}) => {
  return (
    <div className={`space-y-1.5 ${className}`}>
      <div className="flex items-center justify-between">
        <label
          htmlFor={htmlFor}
          className="block text-xs font-semibold uppercase tracking-wider text-slate-300"
        >
          {label} {required && <span className="text-rose-400">*</span>}
        </label>
      </div>

      {description && <p className="text-xs text-slate-400">{description}</p>}

      {children}

      {error && (
        <p className="text-xs text-rose-400 font-medium flex items-center gap-1">
          <span>{error}</span>
        </p>
      )}
    </div>
  );
};
