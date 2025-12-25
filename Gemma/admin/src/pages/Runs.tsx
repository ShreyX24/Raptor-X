import { useState } from 'react';
import { useRuns } from '../hooks';
import { RunCard, LogViewer } from '../components';
import type { AutomationRun } from '../types';

export function Runs() {
  const { activeRunsList, history, loading, stop } = useRuns();
  const [selectedRun, setSelectedRun] = useState<AutomationRun | null>(null);
  const [showLogs, setShowLogs] = useState(false);

  const handleViewLogs = (runId: string) => {
    const run = [...activeRunsList, ...history].find(r => r.run_id === runId);
    if (run) {
      setSelectedRun(run);
      setShowLogs(true);
    }
  };

  const stats = {
    active: activeRunsList.length,
    completed: history.filter(r => r.status === 'completed').length,
    failed: history.filter(r => r.status === 'failed').length,
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Automation Runs</h1>
        <p className="text-gray-500">Monitor active and past automation runs</p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <p className="text-sm text-gray-500">Active Runs</p>
          <p className="text-2xl font-bold text-blue-600">{stats.active}</p>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <p className="text-sm text-gray-500">Completed</p>
          <p className="text-2xl font-bold text-green-600">{stats.completed}</p>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <p className="text-sm text-gray-500">Failed</p>
          <p className="text-2xl font-bold text-red-600">{stats.failed}</p>
        </div>
      </div>

      {/* Active Runs */}
      <div>
        <h2 className="text-lg font-semibold text-gray-900 mb-4">
          Active Runs ({activeRunsList.length})
        </h2>
        {activeRunsList.length === 0 ? (
          <div className="bg-white rounded-lg border border-gray-200 p-8 text-center text-gray-500">
            No active runs
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {activeRunsList.map((run) => (
              <RunCard
                key={run.run_id}
                run={run}
                onStop={(id) => stop(id).catch(console.error)}
                onViewLogs={handleViewLogs}
              />
            ))}
          </div>
        )}
      </div>

      {/* Run History */}
      <div>
        <h2 className="text-lg font-semibold text-gray-900 mb-4">
          History ({history.length})
        </h2>
        {loading ? (
          <div className="space-y-4">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="bg-white rounded-lg border border-gray-200 p-4 animate-pulse">
                <div className="h-4 bg-gray-200 rounded w-1/3 mb-2"></div>
                <div className="h-3 bg-gray-200 rounded w-1/4"></div>
              </div>
            ))}
          </div>
        ) : history.length === 0 ? (
          <div className="bg-white rounded-lg border border-gray-200 p-8 text-center text-gray-500">
            No run history
          </div>
        ) : (
          <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Game
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    SUT
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Status
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Started
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {history.slice(0, 20).map((run) => (
                  <tr key={run.run_id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                      {run.game_name}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {run.sut_ip}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span
                        className={`inline-flex px-2 py-1 text-xs font-medium rounded-full ${
                          run.status === 'completed'
                            ? 'bg-green-100 text-green-700'
                            : run.status === 'failed'
                            ? 'bg-red-100 text-red-700'
                            : 'bg-gray-100 text-gray-700'
                        }`}
                      >
                        {run.status}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {run.started_at
                        ? new Date(run.started_at).toLocaleString()
                        : '-'}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm">
                      <button
                        onClick={() => handleViewLogs(run.run_id)}
                        className="text-blue-500 hover:text-blue-700"
                      >
                        View Logs
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Log Modal */}
      {showLogs && selectedRun && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-4xl w-full mx-4 max-h-[80vh] overflow-hidden flex flex-col">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-bold text-gray-900">
                Logs - {selectedRun.game_name}
              </h2>
              <button
                onClick={() => {
                  setShowLogs(false);
                  setSelectedRun(null);
                }}
                className="text-gray-400 hover:text-gray-600"
              >
                <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="flex-1 overflow-hidden">
              <LogViewer logs={selectedRun.logs || []} maxHeight="60vh" />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
