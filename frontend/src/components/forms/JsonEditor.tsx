import React, { useState } from 'react';
import { Check, AlertCircle, Sparkles } from 'lucide-react';

interface JsonEditorProps {
  id?: string;
  value: string;
  onChange: (val: string) => void;
  placeholder?: string;
  disabled?: boolean;
  rows?: number;
  className?: string;
}

export const JsonEditor: React.FC<JsonEditorProps> = ({
  id,
  value,
  onChange,
  placeholder = '{\n  "degree": "B.S. Computer Science",\n  "institution": "State University"\n}',
  disabled = false,
  rows = 8,
  className = '',
}) => {
  const [parseError, setParseError] = useState<string | null>(null);

  const validateJson = (text: string) => {
    if (!text.trim()) {
      setParseError(null);
      return;
    }
    try {
      JSON.parse(text);
      setParseError(null);
    } catch (e) {
      setParseError((e as Error).message);
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const text = e.target.value;
    onChange(text);
    validateJson(text);
  };

  const handleFormat = () => {
    try {
      const parsed = JSON.parse(value);
      onChange(JSON.stringify(parsed, null, 2));
      setParseError(null);
    } catch (e) {
      setParseError((e as Error).message);
    }
  };

  return (
    <div className={`space-y-1.5 ${className}`}>
      <div className="relative">
        <textarea
          id={id}
          rows={rows}
          value={value}
          onChange={handleChange}
          placeholder={placeholder}
          disabled={disabled}
          spellCheck={false}
          className={`w-full bg-slate-900 border rounded-lg p-3 text-xs font-mono text-slate-100 placeholder-slate-600 focus:outline-none focus:ring-2 transition-colors ${
            parseError
              ? 'border-rose-700/80 focus:ring-rose-500'
              : value && !parseError
              ? 'border-emerald-700/80 focus:ring-emerald-500'
              : 'border-slate-700 focus:ring-brand-500'
          }`}
        />

        <div className="absolute top-2 right-2 flex items-center gap-2">
          {value && !parseError && (
            <button
              type="button"
              disabled={disabled}
              onClick={handleFormat}
              title="Prettify JSON"
              className="px-2 py-1 text-[10px] font-medium bg-slate-800 hover:bg-slate-700 text-slate-300 rounded border border-slate-600 flex items-center gap-1 transition-colors"
            >
              <Sparkles className="w-3 h-3 text-brand-400" />
              <span>Format</span>
            </button>
          )}
        </div>
      </div>

      <div className="flex justify-between items-center text-[11px]">
        {parseError ? (
          <span className="text-rose-400 flex items-center gap-1">
            <AlertCircle className="w-3.5 h-3.5" />
            <span>Invalid JSON: {parseError}</span>
          </span>
        ) : value ? (
          <span className="text-emerald-400 flex items-center gap-1">
            <Check className="w-3.5 h-3.5" />
            <span>Valid JSON Syntax</span>
          </span>
        ) : (
          <span className="text-slate-500">Provide structured JSON metadata</span>
        )}
      </div>
    </div>
  );
};
