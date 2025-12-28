/**
 * SparklineChart - Tiny inline chart for showing trends
 * Uses SVG for lightweight rendering
 */

import { useMemo } from 'react';

interface SparklineChartProps {
  data: number[];
  width?: number;
  height?: number;
  color?: string;
  fillColor?: string;
  strokeWidth?: number;
  showDots?: boolean;
  showArea?: boolean;
  className?: string;
}

export function SparklineChart({
  data,
  width = 100,
  height = 30,
  color = '#00C7FD', // brand-cyan
  fillColor,
  strokeWidth = 1.5,
  showDots = false,
  showArea = true,
  className = '',
}: SparklineChartProps) {
  const path = useMemo(() => {
    if (data.length < 2) return '';

    const min = Math.min(...data);
    const max = Math.max(...data);
    const range = max - min || 1;

    // Padding to prevent clipping
    const padding = 2;
    const chartWidth = width - padding * 2;
    const chartHeight = height - padding * 2;

    const points = data.map((value, index) => {
      const x = padding + (index / (data.length - 1)) * chartWidth;
      const y = padding + chartHeight - ((value - min) / range) * chartHeight;
      return { x, y };
    });

    // Create SVG path
    const linePath = points
      .map((point, i) => `${i === 0 ? 'M' : 'L'} ${point.x} ${point.y}`)
      .join(' ');

    return { linePath, points };
  }, [data, width, height]);

  const areaPath = useMemo(() => {
    if (!path || typeof path === 'string' || !showArea) return '';

    const { points } = path;
    const padding = 2;

    return `
      ${points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x} ${p.y}`).join(' ')}
      L ${points[points.length - 1].x} ${height - padding}
      L ${points[0].x} ${height - padding}
      Z
    `;
  }, [path, showArea, height]);

  if (data.length < 2) {
    return (
      <svg width={width} height={height} className={className}>
        <text
          x={width / 2}
          y={height / 2}
          textAnchor="middle"
          dominantBaseline="middle"
          fill="rgba(255,255,255,0.5)"
          fontSize="8"
        >
          No data
        </text>
      </svg>
    );
  }

  const { linePath, points } = path as { linePath: string; points: { x: number; y: number }[] };

  return (
    <svg width={width} height={height} className={className}>
      {/* Area fill */}
      {showArea && areaPath && (
        <path
          d={areaPath}
          fill={fillColor || `${color}20`}
        />
      )}

      {/* Line */}
      <path
        d={linePath}
        fill="none"
        stroke={color}
        strokeWidth={strokeWidth}
        strokeLinecap="round"
        strokeLinejoin="round"
      />

      {/* Dots */}
      {showDots && points.map((point, i) => (
        <circle
          key={i}
          cx={point.x}
          cy={point.y}
          r={2}
          fill={color}
        />
      ))}

      {/* Highlight last point */}
      <circle
        cx={points[points.length - 1].x}
        cy={points[points.length - 1].y}
        r={3}
        fill={color}
      />
    </svg>
  );
}

/**
 * QueueDepthChart - Larger chart specifically for queue depth display
 */
interface QueueDepthChartProps {
  data: Array<{ timestamp: string; depth: number }>;
  height?: number;
  className?: string;
}

export function QueueDepthChart({
  data,
  height = 150,
  className = '',
}: QueueDepthChartProps) {
  const depths = data.map(d => d.depth);
  const maxDepth = Math.max(...depths, 1);
  const currentDepth = depths[depths.length - 1] || 0;

  // Color based on depth (green -> yellow -> red)
  const color = currentDepth < 5
    ? '#10b981' // success
    : currentDepth < 15
      ? '#f59e0b' // warning
      : '#ef4444'; // danger

  return (
    <div className={`card p-4 ${className}`}>
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs text-text-muted font-semibold uppercase tracking-wide">
          Queue Depth
        </span>
        <div className="flex items-baseline gap-2">
          <span className="text-lg font-bold font-numbers" style={{ color }}>
            {currentDepth}
          </span>
          <span className="text-xs text-text-muted font-numbers">
            max: {maxDepth}
          </span>
        </div>
      </div>

      <div className="w-full">
        <SparklineChart
          data={depths}
          width={400}
          height={height - 50}
          color={color}
          strokeWidth={2}
          showArea={true}
        />
      </div>

      {/* X-axis labels */}
      <div className="flex justify-between text-xs text-text-muted mt-2">
        <span className="font-numbers">
          {data[0]?.timestamp
            ? new Date(data[0].timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
            : ''
          }
        </span>
        <span>Now</span>
      </div>
    </div>
  );
}
