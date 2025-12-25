import type { AutomationRun } from '../types';

interface RunCardProps {
  run: AutomationRun;
  onStop?: (runId: string) => void;
  onViewLogs?: (runId: string) => void;
}

export function RunCard({ run, onStop, onViewLogs }: RunCardProps) {
  const statusColors: Record<string, { bg: string; text: string }> = {
    queued: { bg: 'bg-gray-100', text: 'text-gray-700' },
    running: { bg: 'bg-blue-100', text: 'text-blue-700' },
    completed: { bg: 'bg-green-100', text: 'text-green-700' },
    failed: { bg: 'bg-red-100', text: 'text-red-700' },
    cancelled: { bg: 'bg-yellow-100', text: 'text-yellow-700' },
  };

  const status = statusColors[run.status] || statusColors.queued;

  const formatTime = (isoString: string | null) => {
    if (!isoString) return '-';
    const date = new Date(isoString);
    return date.toLocaleTimeString();
  };

  const getDuration = () => {
    if (!run.started_at) return '-';
    const start = new Date(run.started_at);
    const end = run.completed_at ? new Date(run.completed_at) : new Date();
    const seconds = Math.floor((end.getTime() - start.getTime()) / 1000);
    if (seconds < 60) return `${seconds}s`;
    const minutes = Math.floor(seconds / 60);
    return `${minutes}m ${seconds % 60}s`;
  };

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4">
      <div className="flex items-start justify-between">
        <div>
          <h3 className="font-semibold text-gray-900">{run.game_name}</h3>
          <p className="text-sm text-gray-500">{run.sut_ip}</p>
        </div>
        <span className={`rounded-full px-2 py-1 text-xs font-medium ${status.bg} ${status.text}`}>
          {run.status}
        </span>
      </div>

      {run.status === 'running' && (
        <div className="mt-4">
          <div className="flex justify-between text-sm text-gray-600 mb-1">
            <span>Progress</span>
            <span>{run.progress}%</span>
          </div>
          <div className="h-2 w-full rounded-full bg-gray-200">
            <div
              className="h-2 rounded-full bg-blue-500 transition-all"
              style={{ width: `${run.progress}%` }}
            />
          </div>
          <p className="mt-1 text-xs text-gray-500">
            Iteration {run.current_iteration} of {run.iterations}
          </p>
        </div>
      )}

      <div className="mt-4 grid grid-cols-2 gap-2 text-sm">
        <div>
          <span className="text-gray-500">Started:</span>
          <span className="ml-2">{formatTime(run.started_at)}</span>
        </div>
        <div>
          <span className="text-gray-500">Duration:</span>
          <span className="ml-2">{getDuration()}</span>
        </div>
      </div>

      {run.error_message && (
        <div className="mt-3 rounded bg-red-50 p-2 text-sm text-red-700">
          {run.error_message}
        </div>
      )}

      <div className="mt-4 flex gap-2">
        {run.status === 'running' && (
          <button
            onClick={() => onStop?.(run.run_id)}
            className="flex-1 rounded bg-red-500 px-3 py-1.5 text-sm font-medium text-white hover:bg-red-600"
          >
            Stop
          </button>
        )}
        <button
          onClick={() => onViewLogs?.(run.run_id)}
          className="flex-1 rounded bg-gray-100 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-200"
        >
          View Logs
        </button>
      </div>
    </div>
  );
}
