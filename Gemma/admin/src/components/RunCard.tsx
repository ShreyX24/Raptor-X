import { useState } from 'react';
import type { AutomationRun, RunProgress, StepProgress } from '../types';
import { AutomationTimeline } from './AutomationTimeline';
import { RunTimeline } from './RunTimeline';

interface RunCardProps {
  run: AutomationRun;
  onStop?: (runId: string, killGame?: boolean) => void;
  onViewLogs?: (runId: string) => void;
  showTimeline?: boolean;
}

// Helper to calculate progress percentage from progress object
function getProgressPercent(progress: number | RunProgress): number {
  if (typeof progress === 'number') {
    return progress;
  }
  // Calculate percentage from object: (completed steps / total steps) * 100
  const { current_iteration, current_step, total_iterations, total_steps } = progress;
  if (total_iterations === 0 || total_steps === 0) return 0;

  const stepsPerIteration = total_steps;
  const completedSteps = ((current_iteration - 1) * stepsPerIteration) + current_step;
  const totalStepsAll = total_iterations * stepsPerIteration;

  return Math.round((completedSteps / totalStepsAll) * 100);
}

// Helper to get progress details string
function getProgressDetails(progress: number | RunProgress): string {
  if (typeof progress === 'number') {
    return `${progress}%`;
  }
  const { current_step, total_steps } = progress;
  return `Step ${current_step}/${total_steps}`;
}

// Helper to get steps from progress object
function getSteps(progress: number | RunProgress): StepProgress[] {
  if (typeof progress === 'object' && progress.steps) {
    return progress.steps;
  }
  return [];
}

export function RunCard({ run, onStop, onViewLogs, showTimeline = true }: RunCardProps) {
  const [isTimelineExpanded, setIsTimelineExpanded] = useState(true);
  const statusColors: Record<string, { bg: string; text: string }> = {
    queued: { bg: 'bg-surface-elevated', text: 'text-text-muted' },
    running: { bg: 'bg-primary/20', text: 'text-primary' },
    completed: { bg: 'bg-success/20', text: 'text-success' },
    failed: { bg: 'bg-danger/20', text: 'text-danger' },
    cancelled: { bg: 'bg-warning/20', text: 'text-warning' },
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
    <div className="card p-4">
      <div className="flex items-start justify-between">
        <div>
          <h3 className="font-semibold text-text-primary">{run.game_name}</h3>
          <p className="text-sm text-text-muted font-mono">{run.sut_ip}</p>
        </div>
        <span className={`badge ${status.bg} ${status.text}`}>
          {run.status === 'running' && (
            <span className="w-1.5 h-1.5 bg-primary rounded-full mr-1.5 animate-pulse" />
          )}
          {run.status}
        </span>
      </div>

      {run.status === 'running' && (
        <div className="mt-4">
          <div className="flex justify-between text-sm text-text-secondary mb-1">
            <span>Progress</span>
            <span className="font-numbers">{getProgressDetails(run.progress)}</span>
          </div>
          <div className="h-2 w-full rounded-full bg-surface-elevated">
            <div
              className="h-2 rounded-full bg-primary transition-all"
              style={{ width: `${getProgressPercent(run.progress)}%` }}
            />
          </div>
          <p className="mt-1 text-xs text-text-muted font-numbers">
            Iteration {typeof run.progress === 'object' ? run.progress.current_iteration : run.current_iteration} of {run.iterations}
          </p>

          {/* Run Timeline - shows full run lifecycle */}
          {showTimeline && (
            <div className="mt-3">
              <button
                onClick={() => setIsTimelineExpanded(!isTimelineExpanded)}
                className="flex items-center gap-1 text-xs text-primary hover:text-primary/80 transition-colors"
              >
                <svg
                  className={`w-3 h-3 transition-transform ${isTimelineExpanded ? 'rotate-90' : ''}`}
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
                {isTimelineExpanded ? 'Hide Timeline' : 'Show Timeline'}
              </button>

              {isTimelineExpanded ? (
                <div className="mt-3 p-3 rounded-lg bg-surface-elevated border border-border">
                  <RunTimeline runId={run.run_id} pollInterval={2000} />
                </div>
              ) : (
                <div className="mt-2">
                  <RunTimeline runId={run.run_id} pollInterval={2000} compact />
                </div>
              )}
            </div>
          )}

          {/* Step Timeline - shows automation steps (legacy) */}
          {showTimeline && getSteps(run.progress).length > 0 && (
            <div className="mt-2">
              <AutomationTimeline
                steps={getSteps(run.progress)}
                currentStep={typeof run.progress === 'object' ? run.progress.current_step : undefined}
                compact
              />
            </div>
          )}
        </div>
      )}

      <div className="mt-4 grid grid-cols-2 gap-2 text-sm">
        <div>
          <span className="text-text-muted">Started:</span>
          <span className="ml-2 text-text-secondary">{formatTime(run.started_at)}</span>
        </div>
        <div>
          <span className="text-text-muted">Duration:</span>
          <span className="ml-2 text-text-secondary font-numbers">{getDuration()}</span>
        </div>
      </div>

      {run.error_message && (
        <div className="mt-3 rounded-lg bg-danger/10 border border-danger/30 p-2 text-sm text-danger">
          {run.error_message}
        </div>
      )}

      <div className="mt-4 flex gap-2">
        {run.status === 'running' ? (
          <>
            <button
              onClick={() => onStop?.(run.run_id, false)}
              className="flex-1 btn bg-warning/80 hover:bg-warning text-black text-sm"
              title="Stop automation but leave game running"
            >
              Stop Run
            </button>
            <button
              onClick={() => onStop?.(run.run_id, true)}
              className="flex-1 btn bg-danger/80 hover:bg-danger text-white text-sm"
              title="Stop automation and kill game on SUT"
            >
              Stop & Kill
            </button>
          </>
        ) : (
          <button
            onClick={() => onViewLogs?.(run.run_id)}
            className="flex-1 btn btn-secondary text-sm"
          >
            View Details
          </button>
        )}
      </div>
    </div>
  );
}
