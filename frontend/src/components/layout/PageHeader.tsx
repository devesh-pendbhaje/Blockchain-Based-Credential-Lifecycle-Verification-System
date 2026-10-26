import React from 'react';
import { Breadcrumb, BreadcrumbItem } from '../navigation/Breadcrumb';

interface PageHeaderProps {
  title: string;
  description?: string;
  badge?: React.ReactNode;
  actions?: React.ReactNode;
  breadcrumbs?: BreadcrumbItem[];
  className?: string;
}

export const PageHeader: React.FC<PageHeaderProps> = ({
  title,
  description,
  badge,
  actions,
  breadcrumbs,
  className = '',
}) => {
  return (
    <div className={`space-y-3 pb-6 border-b border-slate-800/80 ${className}`}>
      {breadcrumbs && <Breadcrumb items={breadcrumbs} />}

      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="space-y-1">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold tracking-tight text-slate-100">{title}</h1>
            {badge}
          </div>
          {description && (
            <p className="text-sm text-slate-400 max-w-3xl leading-relaxed">{description}</p>
          )}
        </div>

        {actions && <div className="flex items-center gap-3 shrink-0">{actions}</div>}
      </div>
    </div>
  );
};
