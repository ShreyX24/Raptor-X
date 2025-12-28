import { useState, useMemo, Fragment } from 'react';
import type { AutomationRun, SUTSystemInfo } from '../types';
import { formatCpuDisplay, formatGpuDisplay, formatRamDisplay } from '../utils/cpuCodenames';
import { RunTimeline } from './RunTimeline';

interface RecentRunsTableProps {
  runs: AutomationRun[];
  maxRows?: number;
  onRerun?: (sutIp: string, gameName: string, iterations: number) => void;
}

type SortColumn = 'game' | 'sut' | 'status' | 'duration' | 'when';
type SortDirection = 'asc' | 'desc';

// Format duration from timestamps
function formatDuration(startedAt: string | null, completedAt: string | null): string {
  if (!startedAt) return '-';
  const start = new Date(startedAt);
  const end = completedAt ? new Date(completedAt) : new Date();
  const seconds = Math.floor((end.getTime() - start.getTime()) / 1000);

  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;
  if (minutes < 60) return `${minutes}m ${remainingSeconds}s`;
  const hours = Math.floor(minutes / 60);
  return `${hours}h ${minutes % 60}m`;
}

// Get duration in seconds for sorting
function getDurationSeconds(startedAt: string | null, completedAt: string | null): number {
  if (!startedAt) return 0;
  const start = new Date(startedAt);
  const end = completedAt ? new Date(completedAt) : new Date();
  return Math.floor((end.getTime() - start.getTime()) / 1000);
}

// Format relative time (e.g., "5 mins ago")
function formatRelativeTime(timestamp: string | null): string {
  if (!timestamp) return '-';
  const date = new Date(timestamp);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);

  if (diffMins < 1) return 'just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.floor(diffHours / 24);
  return `${diffDays}d ago`;
}

// Status badge colors (dark theme with design system)
const statusColors: Record<string, { bg: string; text: string }> = {
  completed: { bg: 'bg-success/20', text: 'text-success' },
  failed: { bg: 'bg-danger/20', text: 'text-danger' },
  cancelled: { bg: 'bg-warning/20', text: 'text-warning' },
  running: { bg: 'bg-primary/20', text: 'text-primary' },
  queued: { bg: 'bg-surface-elevated', text: 'text-text-muted' },
};

// Sort indicator component
function SortIndicator({ column, sortColumn, sortDirection }: {
  column: SortColumn;
  sortColumn: SortColumn;
  sortDirection: SortDirection;
}) {
  if (column !== sortColumn) {
    return <span className="ml-1 text-text-muted/50">⇅</span>;
  }
  return (
    <span className="ml-1 text-primary">
      {sortDirection === 'asc' ? '▲' : '▼'}
    </span>
  );
}

// Expanded row details component
// Uses embedded sut_info from manifest - no live fetch for historical runs
function RunDetails({ run }: { run: AutomationRun }) {
  const systemInfo = run.sut_info as SUTSystemInfo | null;

  // Only show values if they're meaningful (non-empty strings, non-zero numbers)
  const cpuDisplay = systemInfo?.cpu?.brand_string ? formatCpuDisplay(systemInfo.cpu.brand_string) : null;
  const gpuDisplay = systemInfo?.gpu?.name ? formatGpuDisplay(systemInfo.gpu.name) : null;
  const ramDisplay = systemInfo?.ram?.total_gb && systemInfo.ram.total_gb > 0
    ? formatRamDisplay(systemInfo.ram.total_gb)
    : null;
  const hasResolution = systemInfo?.screen?.width && systemInfo?.screen?.height &&
    systemInfo.screen.width > 0 && systemInfo.screen.height > 0;

  return (
    <div className="px-4 py-3 bg-surface-elevated/50 border-t border-border animate-fade-in-up">
      {/* Timeline - shows run lifecycle events */}
      <div className="mb-3 px-3 py-2 bg-surface rounded-lg border border-border">
        <div className="text-xs text-text-muted mb-2 font-medium">Timeline</div>
        <RunTimeline
          runId={run.run_id}
          pollInterval={run.status === 'running' ? 2000 : 0}
          compact={false}
        />
      </div>

      {/* Hardware Summary Line - only show if we have data */}
      {(cpuDisplay || gpuDisplay || ramDisplay) && (
        <div className="mb-3 px-3 py-2 bg-surface rounded-lg border border-border">
          {cpuDisplay && <span className="text-brand-cyan font-medium">{cpuDisplay}</span>}
          {cpuDisplay && gpuDisplay && <span className="text-text-muted mx-2">•</span>}
          {gpuDisplay && <span className="text-success">{gpuDisplay}</span>}
          {(cpuDisplay || gpuDisplay) && ramDisplay && <span className="text-text-muted mx-2">•</span>}
          {ramDisplay && <span className="text-primary">{ramDisplay}</span>}
        </div>
      )}

      {/* Details Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
        <div>
          <span className="text-text-muted block mb-0.5">Duration</span>
          <span className="text-text-primary font-numbers">{formatDuration(run.started_at, run.completed_at)}</span>
        </div>
        <div>
          <span className="text-text-muted block mb-0.5">IP Address</span>
          <span className="text-text-primary font-mono">{run.sut_ip}</span>
        </div>
        <div>
          <span className="text-text-muted block mb-0.5">Status</span>
          <span className="text-text-primary">{run.status}</span>
        </div>
        <div>
          <span className="text-text-muted block mb-0.5">Iterations</span>
          <span className="text-text-primary font-numbers">{run.iterations}</span>
        </div>

        {/* Show extended info only if captured in manifest */}
        {systemInfo?.cpu?.brand_string && (
          <div>
            <span className="text-text-muted block mb-0.5">CPU</span>
            <span className="text-text-secondary text-[10px]">{systemInfo.cpu.brand_string}</span>
          </div>
        )}
        {systemInfo?.gpu?.name && (
          <div>
            <span className="text-text-muted block mb-0.5">GPU</span>
            <span className="text-text-secondary text-[10px]">{systemInfo.gpu.name}</span>
          </div>
        )}
        {systemInfo?.os?.name && (
          <div>
            <span className="text-text-muted block mb-0.5">OS</span>
            <span className="text-text-primary">{systemInfo.os.name} {systemInfo.os.release}</span>
          </div>
        )}
        {systemInfo?.os?.build && (
          <div>
            <span className="text-text-muted block mb-0.5">OS Build</span>
            <span className="text-text-secondary text-[10px] font-numbers">{systemInfo.os.build}</span>
          </div>
        )}
        {systemInfo?.bios?.name && (
          <div>
            <span className="text-text-muted block mb-0.5">BIOS</span>
            <span className="text-text-secondary text-[10px]">{systemInfo.bios.name}</span>
          </div>
        )}
        {hasResolution && (
          <div>
            <span className="text-text-muted block mb-0.5">Resolution</span>
            <span className="text-text-primary font-numbers">{systemInfo!.screen.width}x{systemInfo!.screen.height}</span>
          </div>
        )}
        {systemInfo?.hostname && (
          <div>
            <span className="text-text-muted block mb-0.5">Hostname</span>
            <span className="text-text-primary">{systemInfo.hostname}</span>
          </div>
        )}
        {ramDisplay && (
          <div>
            <span className="text-text-muted block mb-0.5">RAM</span>
            <span className="text-text-primary font-numbers">{ramDisplay}</span>
          </div>
        )}
      </div>

      {run.error_message && (
        <div className="mt-3 px-3 py-2 bg-danger/10 border border-danger/30 rounded-lg text-xs text-danger">
          {run.error_message}
        </div>
      )}
    </div>
  );
}

export function RecentRunsTable({ runs, maxRows = 10, onRerun }: RecentRunsTableProps) {
  const [sortColumn, setSortColumn] = useState<SortColumn>('when');
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc');
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedRunId, setExpandedRunId] = useState<string | null>(null);

  // Handle row click to expand/collapse
  // For historical runs, we ONLY use embedded sut_info from manifest - no live fetch
  const handleRowClick = (run: AutomationRun) => {
    if (expandedRunId === run.run_id) {
      setExpandedRunId(null);
    } else {
      setExpandedRunId(run.run_id);
    }
  };

  // Handle column header click
  const handleSort = (column: SortColumn) => {
    if (sortColumn === column) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortColumn(column);
      setSortDirection('desc');
    }
  };

  // Filter and sort runs
  const processedRuns = useMemo(() => {
    const indexed = runs.map((run, index) => ({ run, index }));

    let filtered = indexed;
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase();
      filtered = indexed.filter(({ run }) =>
        run.game_name.toLowerCase().includes(query) ||
        run.sut_ip.toLowerCase().includes(query) ||
        run.status.toLowerCase().includes(query)
      );
    }

    const sorted = [...filtered].sort((aItem, bItem) => {
      const a = aItem.run;
      const b = bItem.run;
      let comparison = 0;

      switch (sortColumn) {
        case 'game':
          comparison = a.game_name.localeCompare(b.game_name);
          break;
        case 'sut':
          comparison = a.sut_ip.localeCompare(b.sut_ip);
          break;
        case 'status':
          comparison = a.status.localeCompare(b.status);
          break;
        case 'duration':
          comparison = getDurationSeconds(a.started_at, a.completed_at) -
                       getDurationSeconds(b.started_at, b.completed_at);
          break;
        case 'when':
          const aTime = a.completed_at || a.started_at;
          const bTime = b.completed_at || b.started_at;
          if (aTime && bTime) {
            comparison = new Date(aTime).getTime() - new Date(bTime).getTime();
          } else {
            comparison = aItem.index - bItem.index;
          }
          break;
      }

      return sortDirection === 'asc' ? comparison : -comparison;
    });

    return sorted.slice(0, maxRows).map(item => item.run);
  }, [runs, sortColumn, sortDirection, searchQuery, maxRows]);

  // Column header component
  const ColumnHeader = ({ column, label, className = '' }: {
    column: SortColumn;
    label: string;
    className?: string;
  }) => (
    <th
      className={`pb-2 font-medium cursor-pointer hover:text-text-secondary select-none transition-colors ${className}`}
      onClick={() => handleSort(column)}
    >
      {label}
      <SortIndicator column={column} sortColumn={sortColumn} sortDirection={sortDirection} />
    </th>
  );

  return (
    <div className="flex flex-col h-full">
      {/* Search Bar */}
      <div className="mb-3 flex-shrink-0">
        <input
          type="text"
          placeholder="Search game, SUT, or status..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="input w-full text-xs py-1.5"
        />
      </div>

      {/* Table */}
      {processedRuns.length === 0 ? (
        <div className="text-center py-6 text-text-muted text-sm">
          {searchQuery ? 'No matching runs' : 'No recent runs'}
        </div>
      ) : (
        <div className="overflow-x-auto flex-1">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-text-muted text-xs uppercase tracking-wider border-b border-border">
                <th className="pb-2 w-4"></th>
                <ColumnHeader column="game" label="Game" />
                <ColumnHeader column="sut" label="SUT" />
                <ColumnHeader column="status" label="Status" />
                <ColumnHeader column="duration" label="Duration" />
                <ColumnHeader column="when" label="When" />
                {onRerun && <th className="pb-2 font-medium text-right">Action</th>}
              </tr>
            </thead>
            <tbody className="divide-y divide-border/50">
              {processedRuns.map((run) => {
                const status = statusColors[run.status] || statusColors.queued;
                const isRerunnable = run.status === 'completed' || run.status === 'failed' || run.status === 'cancelled';
                const isExpanded = expandedRunId === run.run_id;

                return (
                  <Fragment key={run.run_id}>
                    <tr
                      className={`hover:bg-surface-hover/50 cursor-pointer transition-colors ${isExpanded ? 'bg-surface-elevated/30' : ''}`}
                      onClick={() => handleRowClick(run)}
                    >
                      <td className="py-2.5 text-text-muted text-xs">
                        {isExpanded ? '▼' : '▶'}
                      </td>
                      <td className="py-2.5 text-text-primary font-medium truncate max-w-[120px]" title={run.game_name}>
                        {run.game_name}
                      </td>
                      <td className="py-2.5 text-text-secondary font-mono text-xs">
                        {run.sut_ip}
                      </td>
                      <td className="py-2.5">
                        <span className={`badge ${status.bg} ${status.text}`}>
                          {run.status === 'running' && (
                            <span className="w-1.5 h-1.5 bg-primary rounded-full mr-1.5 animate-pulse" />
                          )}
                          {run.status}
                        </span>
                      </td>
                      <td className="py-2.5 text-text-secondary font-numbers tabular-nums">
                        {formatDuration(run.started_at, run.completed_at)}
                      </td>
                      <td className="py-2.5 text-text-muted text-xs">
                        {formatRelativeTime(run.completed_at || run.started_at)}
                      </td>
                      {onRerun && (
                        <td className="py-2.5 text-right">
                          {isRerunnable && (
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                onRerun(run.sut_ip, run.game_name, run.iterations);
                              }}
                              className="btn btn-secondary text-xs py-1 px-2"
                              title={`Re-run ${run.game_name} on ${run.sut_ip} (${run.iterations}x)`}
                            >
                              Re-run
                            </button>
                          )}
                        </td>
                      )}
                    </tr>
                    {isExpanded && (
                      <tr>
                        <td colSpan={onRerun ? 7 : 6} className="p-0">
                          <RunDetails run={run} />
                        </td>
                      </tr>
                    )}
                  </Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
