/**
 * MetricCard - Compact metric display with value, trend, and label
 * Designed for information-dense dashboard layouts
 */

import { ReactNode } from 'react';

interface MetricCardProps {
  label: string;
  value: string | number;
  sublabel?: string;
  trend?: 'up' | 'down' | 'stable';
  trendValue?: string;
  icon?: ReactNode;
  color?: 'default' | 'success' | 'warning' | 'error' | 'info';
  size?: 'sm' | 'md' | 'lg';
  onClick?: () => void;
}

const colorClasses = {
  default: 'bg-surface border-border',
  success: 'bg-success/10 border-success/30',
  warning: 'bg-warning/10 border-warning/30',
  error: 'bg-danger/10 border-danger/30',
  info: 'bg-primary/10 border-primary/30',
};

const valueColorClasses = {
  default: 'text-text-primary',
  success: 'text-success',
  warning: 'text-warning',
  error: 'text-danger',
  info: 'text-primary',
};

const trendIcons = {
  up: '↑',
  down: '↓',
  stable: '→',
};

const trendColors = {
  up: 'text-success',
  down: 'text-danger',
  stable: 'text-text-muted',
};

export function MetricCard({
  label,
  value,
  sublabel,
  trend,
  trendValue,
  icon,
  color = 'default',
  size = 'md',
  onClick,
}: MetricCardProps) {
  const sizeClasses = {
    sm: 'p-2',
    md: 'p-3',
    lg: 'p-4',
  };

  const valueSizeClasses = {
    sm: 'text-xl',
    md: 'text-2xl',
    lg: 'text-3xl',
  };

  return (
    <div
      className={`
        ${colorClasses[color]}
        ${sizeClasses[size]}
        ${onClick ? 'cursor-pointer hover:bg-surface-hover transition-all' : ''}
        rounded-xl border
      `}
      onClick={onClick}
    >
      {/* Header row with icon and label */}
      <div className="flex items-center gap-2 mb-1">
        {icon && <span className="text-text-muted text-sm">{icon}</span>}
        <span className="text-xs text-text-muted uppercase tracking-wide font-medium">
          {label}
        </span>
      </div>

      {/* Value row */}
      <div className="flex items-baseline gap-2">
        <span className={`${valueSizeClasses[size]} ${valueColorClasses[color]} font-bold font-numbers tabular-nums`}>
          {value}
        </span>

        {trend && (
          <span className={`text-sm ${trendColors[trend]} flex items-center gap-0.5`}>
            <span>{trendIcons[trend]}</span>
            {trendValue && <span className="font-numbers">{trendValue}</span>}
          </span>
        )}
      </div>

      {/* Sublabel */}
      {sublabel && (
        <span className="text-xs text-text-muted mt-0.5 block">
          {sublabel}
        </span>
      )}
    </div>
  );
}

/**
 * MetricGrid - Grid layout for MetricCards
 */
interface MetricGridProps {
  children: ReactNode;
  columns?: 2 | 3 | 4 | 6;
  gap?: 'sm' | 'md' | 'lg';
}

export function MetricGrid({
  children,
  columns = 3,
  gap = 'md',
}: MetricGridProps) {
  const columnClasses = {
    2: 'grid-cols-2',
    3: 'grid-cols-3',
    4: 'grid-cols-2 md:grid-cols-4',
    6: 'grid-cols-2 md:grid-cols-3 lg:grid-cols-6',
  };

  const gapClasses = {
    sm: 'gap-2',
    md: 'gap-3',
    lg: 'gap-4',
  };

  return (
    <div className={`grid ${columnClasses[columns]} ${gapClasses[gap]}`}>
      {children}
    </div>
  );
}
