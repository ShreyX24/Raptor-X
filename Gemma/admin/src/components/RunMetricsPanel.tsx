/**
 * RunMetricsPanel - Statistics display with gauges and sparklines
 * Shows success rate, utilization, and run trends
 */

import { useMemo } from 'react';
import { Link } from 'react-router-dom';
import { RadialGauge } from './RadialGauge';
import { SparklineChart } from './SparklineChart';
import type { AutomationRun, RunsStats } from '../types';

// Games to exclude from metrics (reference configs, not real games)
const EXCLUDED_GAMES = ['ui_flow', 'UI_Flow', 'uiflow'];

interface RunMetricsPanelProps {
  runs: AutomationRun[];
  stats?: RunsStats;
  className?: string;
  expanded?: boolean; // Show more recent runs when expanded
  onRerun?: (gameName: string, sutIp: string) => void;
}

// Filter out excluded games
function filterRuns(runs: AutomationRun[]): AutomationRun[] {
  return runs.filter(r => !EXCLUDED_GAMES.includes(r.game_name));
}

// Calculate success rate from recent runs
function calculateSuccessRate(runs: AutomationRun[]): number {
  const filteredRuns = filterRuns(runs);
  const completedRuns = filteredRuns.filter(r => r.status === 'completed' || r.status === 'failed');
  if (completedRuns.length === 0) return 0;

  const successful = completedRuns.filter(r => r.status === 'completed').length;
  return Math.round((successful / completedRuns.length) * 100);
}

// Get runs per day for sparkline
function getRunsPerDay(runs: AutomationRun[], days: number = 7): number[] {
  const filteredRuns = filterRuns(runs);
  const now = new Date();
  const dayBuckets: number[] = Array(days).fill(0);

  filteredRuns.forEach(run => {
    if (!run.started_at) return;
    const runDate = new Date(run.started_at);
    const daysAgo = Math.floor((now.getTime() - runDate.getTime()) / (1000 * 60 * 60 * 24));
    if (daysAgo >= 0 && daysAgo < days) {
      dayBuckets[days - 1 - daysAgo]++;
    }
  });

  return dayBuckets;
}

// Get recent completed runs (sorted by date descending)
function getRecentRuns(runs: AutomationRun[], limit: number = 5): AutomationRun[] {
  return filterRuns(runs)
    .filter(r => r.status === 'completed' || r.status === 'failed')
    .sort((a, b) => {
      // Sort by started_at descending (most recent first)
      const aTime = a.started_at ? new Date(a.started_at).getTime() : 0;
      const bTime = b.started_at ? new Date(b.started_at).getTime() : 0;
      return bTime - aTime;
    })
    .slice(0, limit);
}

export function RunMetricsPanel({ runs, stats, className = '', expanded = false, onRerun }: RunMetricsPanelProps) {
  const successRate = useMemo(() => calculateSuccessRate(runs), [runs]);
  const runsPerDay = useMemo(() => getRunsPerDay(runs, 7), [runs]);
  // Show more recent runs when expanded (no active runs, panel takes full height)
  const recentRunsLimit = expanded ? 15 : 5;
  const recentRuns = useMemo(() => getRecentRuns(runs, recentRunsLimit), [runs, recentRunsLimit]);

  const activeCount = stats?.active_runs ?? runs.filter(r => r.status === 'running').length;
  const queuedCount = stats?.queued_runs ?? runs.filter(r => r.status === 'queued').length;
  const totalCompleted = stats?.completed_runs ?? runs.filter(r => r.status === 'completed').length;
  const totalFailed = stats?.failed_runs ?? runs.filter(r => r.status === 'failed').length;

  // Determine success rate color
  const successColor = successRate >= 80 ? 'success' : successRate >= 50 ? 'warning' : 'danger';

  return (
    <div className={`bg-surface border border-border rounded-lg overflow-hidden ${expanded ? 'flex flex-col' : ''} ${className}`}>
      {/* Header */}
      <div className="px-3 py-2 bg-surface-elevated/50 border-b border-border flex-shrink-0">
        <h3 className="text-sm font-semibold text-text-secondary uppercase tracking-wide">
          Run Metrics
        </h3>
      </div>

      <div className={`p-3 space-y-4 ${expanded ? 'flex-1 flex flex-col min-h-0 overflow-hidden' : ''}`}>
        {/* Gauges Row */}
        <div className="flex items-center justify-around">
          {/* Success Rate Gauge */}
          <RadialGauge
            value={successRate}
            max={100}
            label="SUCCESS"
            size="sm"
            color={successColor}
            showPercent={true}
          />

          {/* Utilization / Active Gauge */}
          <RadialGauge
            value={activeCount}
            max={Math.max(activeCount + queuedCount, 5)}
            label="ACTIVE"
            size="sm"
            color="cyan"
            showPercent={false}
          />
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-4 gap-2">
          <StatBox label="Active" value={activeCount} color="primary" />
          <StatBox label="Queued" value={queuedCount} color="warning" />
          <StatBox label="Done" value={totalCompleted} color="success" />
          <StatBox label="Failed" value={totalFailed} color="danger" />
        </div>

        {/* Runs Trend Sparkline */}
        <div>
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs text-text-muted uppercase">Last 7 Days</span>
            <span className="text-xs text-text-muted font-numbers">
              {runsPerDay.reduce((a, b) => a + b, 0)} runs
            </span>
          </div>
          <SparklineChart
            data={runsPerDay}
            height={32}
            color="cyan"
            showArea={true}
          />
        </div>

        {/* Recent Runs Mini-List */}
        {recentRuns.length > 0 && (
          <div className={expanded ? 'flex-1 flex flex-col min-h-0' : ''}>
            <div className="text-xs text-text-muted uppercase mb-1.5">Recent</div>
            {/* Column Headers */}
            <div className="flex items-center gap-2 px-2 py-1 text-[9px] text-text-muted uppercase tracking-wider border-b border-border/50 mb-1">
              <span className="w-2" /> {/* Status dot spacer */}
              <span className="flex-1">Game</span>
              <span className="w-14 text-center">Preset</span>
              <span className="w-8 text-center">Iter</span>
              <span className="w-10 text-center">SUT</span>
              <span className="w-8 text-right">Age</span>
              <span className="w-8 text-center">Action</span>
            </div>
            <div className={`space-y-1 ${expanded ? 'flex-1 overflow-y-auto' : ''}`}>
              {recentRuns.map((run) => (
                <MiniRunItem key={run.run_id} run={run} onRerun={onRerun} />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * StatBox - Compact stat display
 */
interface StatBoxProps {
  label: string;
  value: number;
  color: 'primary' | 'success' | 'warning' | 'danger';
}

const colorClasses = {
  primary: 'text-primary',
  success: 'text-success',
  warning: 'text-warning',
  danger: 'text-danger',
};

function StatBox({ label, value, color }: StatBoxProps) {
  return (
    <div className="text-center p-1.5 bg-surface-elevated rounded">
      <div className={`text-sm font-bold font-numbers ${colorClasses[color]}`}>
        {value}
      </div>
      <div className="text-[9px] text-text-muted uppercase">{label}</div>
    </div>
  );
}

/**
 * MiniRunItem - Compact run entry with game, preset, IP, and re-run button
 */
function MiniRunItem({ run, onRerun }: { run: AutomationRun; onRerun?: (gameName: string, sutIp: string) => void }) {
  const isSuccess = run.status === 'completed';
  const timeAgo = run.started_at ? getTimeAgo(new Date(run.started_at)) : '';
  const ipShort = run.sut_ip ? run.sut_ip.split('.').slice(-1)[0] : '';

  // Format preset as "quality@res" e.g. "high@1080p"
  const presetShort = run.quality && run.resolution
    ? `${run.quality[0]}@${run.resolution.replace('p', '')}`  // "h@1080"
    : null;

  return (
    <div className="flex items-center gap-2 py-1.5 px-2 rounded bg-surface-elevated/50 group">
      {/* Status dot */}
      <span className={`w-2 h-2 rounded-full flex-shrink-0 ${isSuccess ? 'bg-success' : 'bg-danger'}`} />

      {/* Game name */}
      <span className="text-xs text-text-secondary truncate flex-1 min-w-0">
        {run.game_name}
      </span>

      {/* Preset badge */}
      <span className="w-14 text-center flex-shrink-0">
        {presetShort ? (
          <span
            className="text-[9px] px-1 py-0.5 bg-surface-elevated text-text-muted rounded font-mono"
            title={`${run.quality} @ ${run.resolution}`}
          >
            {presetShort}
          </span>
        ) : (
          <span className="text-[9px] text-text-muted">-</span>
        )}
      </span>

      {/* Iterations */}
      <span className="w-8 text-center flex-shrink-0 text-[10px] text-text-muted font-mono">
        {run.iterations > 1 ? `×${run.iterations}` : '-'}
      </span>

      {/* SUT IP */}
      <span className="w-10 text-center flex-shrink-0">
        {ipShort ? (
          <span className="text-[10px] text-text-muted font-mono">.{ipShort}</span>
        ) : (
          <span className="text-[9px] text-text-muted">-</span>
        )}
      </span>

      {/* Time ago */}
      <span className="text-xs text-text-muted font-numbers flex-shrink-0 w-8 text-right">
        {timeAgo}
      </span>

      {/* Actions: View + Re-run */}
      <div className="w-8 flex items-center justify-center gap-0.5 flex-shrink-0">
        <Link
          to={`/runs?run=${run.run_id}`}
          className="p-0.5 text-text-muted hover:text-primary transition-colors"
          title="View details"
        >
          <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
          </svg>
        </Link>
        {onRerun && run.sut_ip && (
          <button
            onClick={() => onRerun(run.game_name, run.sut_ip)}
            className="p-0.5 text-text-muted hover:text-success transition-colors"
            title="Re-run this benchmark"
          >
            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
          </button>
        )}
      </div>
    </div>
  );
}

/**
 * Get human-readable time ago string
 */
function getTimeAgo(date: Date): string {
  const seconds = Math.floor((Date.now() - date.getTime()) / 1000);

  if (seconds < 60) return 'now';
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h`;
  return `${Math.floor(seconds / 86400)}d`;
}

/**
 * CompactMetricsRow - Horizontal layout for tight spaces
 */
export function CompactMetricsRow({ runs, stats }: { runs: AutomationRun[]; stats?: RunsStats }) {
  const successRate = useMemo(() => calculateSuccessRate(runs), [runs]);
  const activeCount = stats?.active_runs ?? runs.filter(r => r.status === 'running').length;
  const completedCount = stats?.completed_runs ?? runs.filter(r => r.status === 'completed').length;

  return (
    <div className="flex items-center gap-4 px-3 py-2 bg-surface-elevated rounded-lg">
      {/* Success Rate */}
      <div className="flex items-center gap-2">
        <RadialGauge
          value={successRate}
          max={100}
          size="xs"
          color={successRate >= 80 ? 'success' : successRate >= 50 ? 'warning' : 'danger'}
          showPercent={true}
        />
        <div className="text-[10px]">
          <div className="text-text-muted">Success</div>
          <div className="font-numbers font-medium text-text-primary">{successRate}%</div>
        </div>
      </div>

      <div className="h-6 w-px bg-border" />

      {/* Counts */}
      <div className="flex items-center gap-3 text-[10px]">
        <div>
          <span className="text-text-muted">Active: </span>
          <span className="font-numbers font-medium text-primary">{activeCount}</span>
        </div>
        <div>
          <span className="text-text-muted">Total: </span>
          <span className="font-numbers font-medium text-text-primary">{completedCount}</span>
        </div>
      </div>
    </div>
  );
}
