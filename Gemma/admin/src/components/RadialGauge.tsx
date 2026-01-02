/**
 * RadialGauge - Circular progress gauge for data-dense dashboards
 * SVG-based with smooth animations
 */

import { useMemo } from 'react';

interface RadialGaugeProps {
  value: number;
  max: number;
  label?: string;
  sublabel?: string;
  size?: 'xs' | 'sm' | 'md' | 'lg' | 'xl';
  color?: 'primary' | 'success' | 'warning' | 'danger' | 'cyan';
  showPercent?: boolean;
  thickness?: number;
  className?: string;
}

const sizeConfig = {
  xs: { size: 48, fontSize: 12, sublabelSize: 8, labelSize: 7 },
  sm: { size: 64, fontSize: 14, sublabelSize: 9, labelSize: 8 },
  md: { size: 96, fontSize: 20, sublabelSize: 11, labelSize: 10 },
  lg: { size: 128, fontSize: 28, sublabelSize: 12, labelSize: 11 },
  xl: { size: 160, fontSize: 36, sublabelSize: 14, labelSize: 12 },
};

const colorConfig = {
  primary: { stroke: '#a855f7', bg: 'rgba(168, 85, 247, 0.15)' },
  success: { stroke: '#10b981', bg: 'rgba(16, 185, 129, 0.15)' },
  warning: { stroke: '#f59e0b', bg: 'rgba(245, 158, 11, 0.15)' },
  danger: { stroke: '#ef4444', bg: 'rgba(239, 68, 68, 0.15)' },
  cyan: { stroke: '#00C7FD', bg: 'rgba(0, 199, 253, 0.15)' },
};

export function RadialGauge({
  value,
  max,
  label,
  sublabel,
  size = 'md',
  color = 'primary',
  showPercent = true,
  thickness = 8,
  className = '',
}: RadialGaugeProps) {
  const config = sizeConfig[size];
  const colors = colorConfig[color];

  const { circumference, offset, displayValue } = useMemo(() => {
    const radius = (config.size - thickness) / 2;
    const circ = 2 * Math.PI * radius;
    const percent = Math.min(Math.max(value / max, 0), 1);
    const off = circ - (percent * circ);
    const display = showPercent
      ? Math.round(percent * 100)
      : value;

    return { circumference: circ, offset: off, displayValue: display };
  }, [value, max, config.size, thickness, showPercent]);

  const radius = (config.size - thickness) / 2;
  const center = config.size / 2;

  return (
    <div className={`relative inline-flex flex-col items-center ${className}`}>
      <svg
        width={config.size}
        height={config.size}
        className="transform -rotate-90"
      >
        {/* Background circle */}
        <circle
          cx={center}
          cy={center}
          r={radius}
          fill="none"
          stroke={colors.bg}
          strokeWidth={thickness}
        />

        {/* Progress circle */}
        <circle
          cx={center}
          cy={center}
          r={radius}
          fill="none"
          stroke={colors.stroke}
          strokeWidth={thickness}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          className="transition-all duration-700 ease-out"
          style={{
            filter: `drop-shadow(0 0 6px ${colors.stroke}40)`,
          }}
        />
      </svg>

      {/* Center content */}
      <div
        className="absolute inset-0 flex flex-col items-center justify-center"
        style={{ top: 0, left: 0, width: config.size, height: config.size }}
      >
        <span
          className="font-numbers font-bold text-text-primary"
          style={{ fontSize: config.fontSize }}
        >
          {displayValue}{showPercent && '%'}
        </span>
        {label && (
          <span
            className="text-text-muted uppercase tracking-wide font-medium"
            style={{ fontSize: config.labelSize }}
          >
            {label}
          </span>
        )}
      </div>

      {/* Sublabel below gauge */}
      {sublabel && (
        <span
          className="text-text-muted mt-1 text-center"
          style={{ fontSize: config.sublabelSize }}
        >
          {sublabel}
        </span>
      )}
    </div>
  );
}

/**
 * MiniGauge - Extra compact gauge for inline use
 */
interface MiniGaugeProps {
  value: number;
  max: number;
  color?: 'primary' | 'success' | 'warning' | 'danger' | 'cyan';
  size?: number;
}

export function MiniGauge({
  value,
  max,
  color = 'primary',
  size = 24,
}: MiniGaugeProps) {
  const colors = colorConfig[color];
  const thickness = 3;
  const radius = (size - thickness) / 2;
  const center = size / 2;
  const circumference = 2 * Math.PI * radius;
  const percent = Math.min(Math.max(value / max, 0), 1);
  const offset = circumference - (percent * circumference);

  return (
    <svg
      width={size}
      height={size}
      className="transform -rotate-90"
    >
      <circle
        cx={center}
        cy={center}
        r={radius}
        fill="none"
        stroke={colors.bg}
        strokeWidth={thickness}
      />
      <circle
        cx={center}
        cy={center}
        r={radius}
        fill="none"
        stroke={colors.stroke}
        strokeWidth={thickness}
        strokeLinecap="round"
        strokeDasharray={circumference}
        strokeDashoffset={offset}
        className="transition-all duration-500 ease-out"
      />
    </svg>
  );
}
