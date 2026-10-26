import React from 'react';
import { Plus, Trash2 } from 'lucide-react';

export interface AttributeEntry {
  id: string;
  key: string;
  value: string;
}

interface AttributeMapInputProps {
  entries: AttributeEntry[];
  onChange: (entries: AttributeEntry[]) => void;
  disabled?: boolean;
  className?: string;
}

export const AttributeMapInput: React.FC<AttributeMapInputProps> = ({
  entries,
  onChange,
  disabled = false,
  className = '',
}) => {
  const handleAdd = () => {
    const newEntry: AttributeEntry = {
      id: Math.random().toString(36).substring(2, 9),
      key: '',
      value: '',
    };
    onChange([...entries, newEntry]);
  };

  const handleRemove = (id: string) => {
    onChange(entries.filter((e) => e.id !== id));
  };

  const handleUpdate = (id: string, field: 'key' | 'value', val: string) => {
    onChange(
      entries.map((e) => (e.id === id ? { ...e, [field]: val } : e))
    );
  };

  return (
    <div className={`space-y-3 ${className}`}>
      <div className="space-y-2">
        {entries.map((entry, index) => (
          <div key={entry.id} className="flex items-center gap-2">
            <span className="text-[10px] font-mono text-slate-500 w-5 text-right shrink-0">
              #{index + 1}
            </span>
            <input
              type="text"
              placeholder="Attribute Key (e.g. degree)"
              value={entry.key}
              disabled={disabled}
              onChange={(e) => handleUpdate(entry.id, 'key', e.target.value)}
              className="flex-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-slate-100 placeholder-slate-600 focus:outline-none focus:ring-1 focus:ring-brand-500 font-mono"
            />
            <span className="text-slate-600 text-xs">:</span>
            <input
              type="text"
              placeholder="Attribute Claim Value (e.g. Computer Science)"
              value={entry.value}
              disabled={disabled}
              onChange={(e) => handleUpdate(entry.id, 'value', e.target.value)}
              className="flex-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-slate-100 placeholder-slate-600 focus:outline-none focus:ring-1 focus:ring-brand-500 font-mono"
            />
            <button
              type="button"
              disabled={disabled || entries.length <= 1}
              onClick={() => handleRemove(entry.id)}
              className="p-1.5 text-slate-500 hover:text-rose-400 rounded hover:bg-slate-800 transition-colors disabled:opacity-30 disabled:hover:text-slate-500"
              title="Remove attribute"
            >
              <Trash2 className="w-4 h-4" />
            </button>
          </div>
        ))}
      </div>

      <button
        type="button"
        disabled={disabled}
        onClick={handleAdd}
        className="inline-flex items-center gap-1.5 text-xs font-medium text-brand-400 hover:text-brand-300 py-1.5 px-3 rounded-lg border border-dashed border-brand-800/60 hover:bg-brand-950/40 transition-colors"
      >
        <Plus className="w-3.5 h-3.5" />
        <span>Add Credential Claim Attribute</span>
      </button>
    </div>
  );
};
