import { useState, useCallback } from 'react';
import { useRuns } from '../hooks';
import { RunCard, LogViewer, RunTimeline } from '../components';
import type { AutomationRun, LogEntry } from '../types';

export function Runs() {
  const { activeRunsList, history, loading, stop } = useRuns();
  const [selectedRun, setSelectedRun] = useState<AutomationRun | null>(null);
  const [showLogs, setShowLogs] = useState(false);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [logsLoading, setLogsLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<'timeline' | 'logs'>('timeline');

  const fetchLogs = useCallback(async (runId: string) => {
    setLogsLoading(true);
    try {
      const response = await fetch(`/api/runs/${runId}/logs`);
      if (response.ok) {
        const data = await response.json();
        setLogs(data.logs || []);
      } else {
        setLogs([]);
      }
    } catch (error) {
      console.error('Failed to fetch logs:', error);
      setLogs([]);
    } finally {
      setLogsLoading(false);
    }
  }, []);

  const handleViewLogs = (runId: string) => {
    const run = [...activeRunsList, ...history].find(r => r.run_id === runId);
    if (run) {
      setSelectedRun(run);
      setShowLogs(true);
      fetchLogs(runId);
    }
  };

  const stats = {
    active: activeRunsList.length,
    completed: history.filter(r => r.status === 'completed').length,
    failed: history.filter(r => r.status === 'failed').length,
  };

  return (
    <div className="space-y-6 p-4 lg:p-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-text-primary">Automation Runs</h1>
        <p className="text-text-muted">Monitor active and past automation runs</p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="card p-4">
          <p className="text-sm text-text-muted">Active Runs</p>
          <p className="text-2xl font-bold text-primary">{stats.active}</p>
        </div>
        <div className="card p-4">
          <p className="text-sm text-text-muted">Completed</p>
          <p className="text-2xl font-bold text-success">{stats.completed}</p>
        </div>
        <div className="card p-4">
          <p className="text-sm text-text-muted">Failed</p>
          <p className="text-2xl font-bold text-danger">{stats.failed}</p>
        </div>
      </div>

      {/* Active Runs */}
      <div>
        <h2 className="text-lg font-semibold text-text-primary mb-4">
          Active Runs ({activeRunsList.length})
        </h2>
        {activeRunsList.length === 0 ? (
          <div className="card p-8 text-center text-text-muted">
            No active runs
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {activeRunsList.map((run) => (
              <RunCard
                key={run.run_id}
                run={run}
                onStop={(id, killGame) => stop(id, killGame).catch(console.error)}
                onViewLogs={handleViewLogs}
              />
            ))}
          </div>
        )}
      </div>

      {/* Run History */}
      <div>
        <h2 className="text-lg font-semibold text-text-primary mb-4">
          History ({history.length})
        </h2>
        {loading ? (
          <div className="space-y-4">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="card p-4 animate-pulse">
                <div className="h-4 bg-surface-elevated rounded w-1/3 mb-2"></div>
                <div className="h-3 bg-surface-elevated rounded w-1/4"></div>
              </div>
            ))}
          </div>
        ) : history.length === 0 ? (
          <div className="card p-8 text-center text-text-muted">
            No run history
          </div>
        ) : (
          <div className="card overflow-hidden">
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-border">
                <thead className="bg-surface-elevated">
                  <tr>
                    <th className="px-4 sm:px-6 py-3 text-left text-xs font-medium text-text-muted uppercase tracking-wider">
                      Game
                    </th>
                    <th className="px-4 sm:px-6 py-3 text-left text-xs font-medium text-text-muted uppercase tracking-wider hidden sm:table-cell">
                      SUT
                    </th>
                    <th className="px-4 sm:px-6 py-3 text-left text-xs font-medium text-text-muted uppercase tracking-wider">
                      Status
                    </th>
                    <th className="px-4 sm:px-6 py-3 text-left text-xs font-medium text-text-muted uppercase tracking-wider hidden md:table-cell">
                      Started
                    </th>
                    <th className="px-4 sm:px-6 py-3 text-left text-xs font-medium text-text-muted uppercase tracking-wider">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {history.slice(0, 20).map((run) => (
                    <tr key={run.run_id} className="hover:bg-surface-hover transition-colors">
                      <td className="px-4 sm:px-6 py-4 whitespace-nowrap text-sm font-medium text-text-primary">
                        {run.game_name}
                      </td>
                      <td className="px-4 sm:px-6 py-4 whitespace-nowrap text-sm text-text-muted hidden sm:table-cell">
                        {run.sut_ip}
                      </td>
                      <td className="px-4 sm:px-6 py-4 whitespace-nowrap">
                        <span
                          className={`inline-flex px-2 py-1 text-xs font-medium rounded-full ${
                            run.status === 'completed'
                              ? 'bg-success/20 text-success'
                              : run.status === 'failed'
                              ? 'bg-danger/20 text-danger'
                              : 'bg-surface-elevated text-text-muted'
                          }`}
                        >
                          {run.status}
                        </span>
                      </td>
                      <td className="px-4 sm:px-6 py-4 whitespace-nowrap text-sm text-text-muted hidden md:table-cell">
                        {run.started_at
                          ? new Date(run.started_at).toLocaleString()
                          : '-'}
                      </td>
                      <td className="px-4 sm:px-6 py-4 whitespace-nowrap text-sm">
                        <button
                          onClick={() => handleViewLogs(run.run_id)}
                          className="text-primary hover:text-primary/80 transition-colors"
                        >
                          View Logs
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>

      {/* Run Detail Modal - Full screen on mobile, large on desktop */}
      {showLogs && selectedRun && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-2 sm:p-4">
          <div className="bg-surface rounded-xl p-4 sm:p-6 w-full max-w-7xl max-h-[95vh] sm:max-h-[90vh] overflow-hidden flex flex-col border border-border shadow-2xl">
            {/* Header */}
            <div className="flex items-center justify-between mb-4">
              <div>
                <h2 className="text-lg sm:text-xl font-bold text-text-primary">
                  Run Details
                </h2>
                <p className="text-sm text-text-muted">
                  {selectedRun.game_name} on {selectedRun.sut_ip}
                  <span className={`ml-2 inline-flex px-2 py-0.5 text-xs font-medium rounded-full ${
                    selectedRun.status === 'completed' ? 'bg-success/20 text-success' :
                    selectedRun.status === 'failed' ? 'bg-danger/20 text-danger' :
                    selectedRun.status === 'running' ? 'bg-primary/20 text-primary' :
                    'bg-surface-elevated text-text-muted'
                  }`}>
                    {selectedRun.status}
                  </span>
                </p>
              </div>
              <button
                onClick={() => {
                  setShowLogs(false);
                  setSelectedRun(null);
                  setLogs([]);
                  setActiveTab('timeline');
                }}
                className="p-2 rounded-lg text-text-muted hover:text-text-primary hover:bg-surface-hover transition-colors"
              >
                <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {/* Tabs */}
            <div className="flex gap-1 mb-4 border-b border-border">
              <button
                onClick={() => setActiveTab('timeline')}
                className={`px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px ${
                  activeTab === 'timeline'
                    ? 'text-primary border-primary'
                    : 'text-text-muted border-transparent hover:text-text-secondary'
                }`}
              >
                Timeline
              </button>
              <button
                onClick={() => setActiveTab('logs')}
                className={`px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px ${
                  activeTab === 'logs'
                    ? 'text-primary border-primary'
                    : 'text-text-muted border-transparent hover:text-text-secondary'
                }`}
              >
                Logs
              </button>
            </div>

            {/* Tab Content */}
            <div className="flex-1 overflow-hidden min-h-0">
              {activeTab === 'timeline' ? (
                <div className="h-full overflow-auto rounded-lg bg-surface-elevated border border-border p-4">
                  <RunTimeline runId={selectedRun.run_id} pollInterval={selectedRun.status === 'running' ? 2000 : 0} />
                </div>
              ) : (
                logsLoading ? (
                  <div className="rounded-lg bg-background p-4 font-mono text-sm text-text-muted flex items-center justify-center h-full">
                    <span className="animate-pulse">Loading logs...</span>
                  </div>
                ) : (
                  <LogViewer logs={logs} maxHeight="calc(90vh - 200px)" />
                )
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
