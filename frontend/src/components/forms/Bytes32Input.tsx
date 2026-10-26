import React from 'react';
import { Dices, Check, AlertCircle } from 'lucide-react';
import { isValidBytes32Hex, generateRandomBytes32 } from '@/utils/cryptoFormat';

interface Bytes32InputProps {
  id?: string;
  value: string;
  onChange: (val: string) => void;
  placeholder?: string;
  disabled?: boolean;
  allowGenerate?: boolean;
  className?: string;
}

export const Bytes32Input: React.FC<Bytes32InputProps> = ({
  id,
  value,
  onChange,
  placeholder = '0x1234... (64 hex digits)',
  disabled = false,
  allowGenerate = false,
  className = '',
}) => {
  const isValid = isValidBytes32Hex(value);
  const charCount = value ? value.length : 0;

  const handleGenerate = () => {
    const randomHex = generateRandomBytes32();
    onChange(randomHex);
  };

  return (
    <div className={`space-y-1 ${className}`}>
      <div className="relative flex items-center">
        <input
          id={id}
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value.trim())}
          placeholder={placeholder}
          disabled={disabled}
          spellCheck={false}
          className={`w-full bg-slate-900 border rounded-lg px-3 py-2 text-xs font-mono text-slate-100 placeholder-slate-600 focus:outline-none focus:ring-2 transition-colors ${
            value && !isValid
              ? 'border-rose-700/80 focus:ring-rose-500'
              : isValid
              ? 'border-emerald-700/80 focus:ring-emerald-500'
              : 'border-slate-700 focus:ring-brand-500'
          } ${allowGenerate ? 'pr-20' : 'pr-8'}`}
        />

        <div className="absolute right-2 flex items-center gap-1.5 text-slate-400">
          {value && (
            isValid ? (
              <Check className="w-4 h-4 text-emerald-400" />
            ) : (
              <AlertCircle className="w-4 h-4 text-rose-400" />
            )
          )}

          {allowGenerate && (
            <button
              type="button"
              disabled={disabled}
              onClick={handleGenerate}
              title="Generate random 32-byte hex (256-bit entropy)"
              className="px-1.5 py-1 text-[10px] font-sans font-medium bg-slate-800 hover:bg-slate-700 text-brand-300 rounded border border-slate-600 flex items-center gap-1 transition-colors"
            >
              <Dices className="w-3 h-3" />
              <span>Random</span>
            </button>
          )}
        </div>
      </div>

      <div className="flex justify-between items-center text-[10px] text-slate-500 font-mono">
        <span>Required: 0x + 64 hex characters (32 bytes)</span>
        <span className={charCount === 66 ? 'text-emerald-400' : 'text-slate-400'}>
          {charCount}/66 chars
        </span>
      </div>
    </div>
  );
};
