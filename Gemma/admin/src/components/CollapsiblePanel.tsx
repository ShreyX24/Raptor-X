/**
 * CollapsiblePanel - Collapsible panel wrapper for dashboard sections
 */

import { useState, ReactNode } from 'react';

interface CollapsiblePanelProps {
  title: string;
  icon?: ReactNode;
  children: ReactNode;
  defaultCollapsed?: boolean;
  headerActions?: ReactNode;
  badge?: string | number;
  badgeColor?: 'primary' | 'success' | 'warning' | 'danger';
  className?: string;
  contentClassName?: string;
  noPadding?: boolean;
}

const badgeColors = {
  primary: 'bg-primary/20 text-primary',
  success: 'bg-success/20 text-success',
  warning: 'bg-warning/20 text-warning',
  danger: 'bg-danger/20 text-danger',
};

export function CollapsiblePanel({
  title,
  icon,
  children,
  defaultCollapsed = false,
  headerActions,
  badge,
  badgeColor = 'primary',
  className = '',
  contentClassName = '',
  noPadding = false,
}: CollapsiblePanelProps) {
  const [collapsed, setCollapsed] = useState(defaultCollapsed);

  return (
    <div className={`bg-surface border border-border rounded-lg overflow-hidden ${className}`}>
      {/* Header */}
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="w-full flex items-center justify-between px-3 py-2 bg-surface-elevated/50 hover:bg-surface-elevated transition-colors"
      >
        <div className="flex items-center gap-2">
          {/* Collapse indicator */}
          <svg
            className={`w-3.5 h-3.5 text-text-muted transition-transform duration-200 ${
              collapsed ? '' : 'rotate-90'
            }`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>

          {/* Icon */}
          {icon && <span className="text-text-muted">{icon}</span>}

          {/* Title */}
          <span className="text-xs font-semibold text-text-secondary uppercase tracking-wide">
            {title}
          </span>

          {/* Badge */}
          {badge !== undefined && (
            <span className={`px-1.5 py-0.5 text-xs font-numbers font-medium rounded ${badgeColors[badgeColor]}`}>
              {badge}
            </span>
          )}
        </div>

        {/* Header Actions */}
        {headerActions && (
          <div
            className="flex items-center gap-2"
            onClick={(e) => e.stopPropagation()}
          >
            {headerActions}
          </div>
        )}
      </button>

      {/* Content */}
      <div
        className={`transition-all duration-200 ease-out overflow-hidden ${
          collapsed ? 'max-h-0' : 'max-h-[2000px]'
        }`}
      >
        <div className={`${noPadding ? '' : 'p-3'} ${contentClassName}`}>
          {children}
        </div>
      </div>
    </div>
  );
}

/**
 * Panel - Simple non-collapsible panel
 */
interface PanelProps {
  title?: string;
  icon?: ReactNode;
  children: ReactNode;
  headerActions?: ReactNode;
  badge?: string | number;
  badgeColor?: 'primary' | 'success' | 'warning' | 'danger';
  className?: string;
  contentClassName?: string;
  noPadding?: boolean;
}

export function Panel({
  title,
  icon,
  children,
  headerActions,
  badge,
  badgeColor = 'primary',
  className = '',
  contentClassName = '',
  noPadding = false,
}: PanelProps) {
  return (
    <div className={`bg-surface border border-border rounded-lg overflow-hidden ${className}`}>
      {/* Header */}
      {title && (
        <div className="flex items-center justify-between px-3 py-2 bg-surface-elevated/50 border-b border-border">
          <div className="flex items-center gap-2">
            {icon && <span className="text-text-muted">{icon}</span>}
            <span className="text-xs font-semibold text-text-secondary uppercase tracking-wide">
              {title}
            </span>
            {badge !== undefined && (
              <span className={`px-1.5 py-0.5 text-xs font-numbers font-medium rounded ${badgeColors[badgeColor]}`}>
                {badge}
              </span>
            )}
          </div>
          {headerActions && (
            <div className="flex items-center gap-2">
              {headerActions}
            </div>
          )}
        </div>
      )}

      {/* Content */}
      <div className={`${noPadding ? '' : 'p-3'} ${contentClassName}`}>
        {children}
      </div>
    </div>
  );
}
