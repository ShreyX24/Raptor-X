/**
 * ActiveRunsPanel - Live monitoring of active automation runs
 * Shows compact run cards with radial progress gauges
 */

import { useMemo } from 'react';
import { MiniGauge } from './RadialGauge';
import type { AutomationRun, RunProgress, Campaign } from '../types';

interface ActiveRunsPanelProps {
  runs: AutomationRun[];
  campaigns?: Campaign[];
  onStopRun?: (runId: string, killGame?: boolean) => void;
  onStopCampaign?: (campaignId: string) => void;
  onViewRun?: (runId: string) => void;
  maxHeight?: string;
  className?: string;
}

// Helper to calculate progress percentage
function getProgressPercent(progress: number | RunProgress): number {
  if (typeof progress === 'number') {
    return progress;
  }
  const { current_iteration, current_step, total_iterations, total_steps } = progress;
  if (total_iterations === 0 || total_steps === 0) return 0;

  const stepsPerIteration = total_steps;
  const completedSteps = ((current_iteration - 1) * stepsPerIteration) + current_step;
  const totalStepsAll = total_iterations * stepsPerIteration;

  return Math.round((completedSteps / totalStepsAll) * 100);
}

// Get current step info
function getStepInfo(progress: number | RunProgress): string {
  if (typeof progress === 'number') {
    return `${progress}%`;
  }
  return `Step ${progress.current_step}/${progress.total_steps}`;
}

export function ActiveRunsPanel({
  runs,
  campaigns = [],
  onStopRun,
  onStopCampaign,
  onViewRun,
  maxHeight = '300px',
  className = '',
}: ActiveRunsPanelProps) {
  // Split runs by status
  const { activeRuns, queuedRuns } = useMemo(() => {
    const active = runs.filter(r => r.status === 'running');
    const queued = runs.filter(r => r.status === 'queued');
    return { activeRuns: active, queuedRuns: queued };
  }, [runs]);

  // Active campaigns
  const activeCampaigns = useMemo(() =>
    campaigns.filter(c => c.status === 'running' || c.status === 'queued'),
    [campaigns]
  );

  const totalActive = activeRuns.length + activeCampaigns.length;

  return (
    <div className={`bg-surface border border-border rounded-lg overflow-hidden ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 bg-surface-elevated/50 border-b border-border">
        <h3 className="text-xs font-semibold text-text-secondary uppercase tracking-wide">
          Active Runs
        </h3>
        <div className="flex items-center gap-2">
          {activeRuns.length > 0 && (
            <span className="flex items-center gap-1 text-xs font-numbers">
              <span className="w-1.5 h-1.5 rounded-full bg-success animate-pulse" />
              <span className="text-success">{activeRuns.length}</span>
            </span>
          )}
          {queuedRuns.length > 0 && (
            <span className="flex items-center gap-1 text-xs font-numbers text-text-muted">
              <span className="w-1.5 h-1.5 rounded-full bg-warning" />
              {queuedRuns.length} queued
            </span>
          )}
        </div>
      </div>

      {/* Content */}
      <div className="overflow-y-auto p-2 space-y-2" style={{ maxHeight }}>
        {totalActive === 0 && queuedRuns.length === 0 ? (
          <div className="text-center py-8 text-text-muted text-xs">
            <svg className="w-8 h-8 mx-auto mb-2 opacity-30" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            No active runs
          </div>
        ) : (
          <>
            {/* Active Campaigns */}
            {activeCampaigns.map((campaign) => (
              <CampaignCard
                key={campaign.campaign_id}
                campaign={campaign}
                onStop={() => onStopCampaign?.(campaign.campaign_id)}
              />
            ))}

            {/* Active Runs */}
            {activeRuns.map((run) => (
              <CompactRunCard
                key={run.run_id}
                run={run}
                onStop={() => onStopRun?.(run.run_id)}
                onStopKill={() => onStopRun?.(run.run_id, true)}
                onClick={() => onViewRun?.(run.run_id)}
              />
            ))}

            {/* Queued Runs */}
            {queuedRuns.map((run) => (
              <QueuedRunCard
                key={run.run_id}
                run={run}
                onClick={() => onViewRun?.(run.run_id)}
              />
            ))}
          </>
        )}
      </div>
    </div>
  );
}

/**
 * CompactRunCard - Minimal run card with radial progress
 */
interface CompactRunCardProps {
  run: AutomationRun;
  onStop?: () => void;
  onStopKill?: () => void;
  onClick?: () => void;
}

function CompactRunCard({ run, onStop, onStopKill, onClick }: CompactRunCardProps) {
  const progressPercent = getProgressPercent(run.progress);
  const stepInfo = getStepInfo(run.progress);
  const iterInfo = typeof run.progress === 'object'
    ? `${run.progress.current_iteration}/${run.progress.total_iterations}`
    : `${run.current_iteration}/${run.iterations}`;

  return (
    <div
      className="flex items-center gap-3 p-2.5 bg-surface-elevated rounded-lg border border-primary/30 cursor-pointer hover:border-primary transition-colors"
      onClick={onClick}
    >
      {/* Radial Progress */}
      <div className="relative flex-shrink-0">
        <MiniGauge
          value={progressPercent}
          max={100}
          color="primary"
          size={36}
        />
        <span className="absolute inset-0 flex items-center justify-center text-[9px] font-numbers font-bold text-text-primary">
          {progressPercent}%
        </span>
      </div>

      {/* Info */}
      <div className="flex-1 min-w-0 overflow-hidden">
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-text-primary truncate">
            {run.game_name}
          </span>
          <span className="w-1.5 h-1.5 rounded-full bg-success animate-pulse flex-shrink-0" />
        </div>
        <div className="flex items-center gap-2 text-[10px] text-text-muted truncate">
          <span className="font-mono">{run.sut_ip}</span>
          <span>|</span>
          <span className="font-numbers">{stepInfo}</span>
          <span>|</span>
          <span className="font-numbers whitespace-nowrap">Iter {iterInfo}</span>
        </div>
        {run.quality && run.resolution && (
          <div className="mt-0.5 text-[10px] text-primary truncate">
            {run.quality} @ {run.resolution}
          </div>
        )}
      </div>

      {/* Actions */}
      <div className="flex items-center gap-1 flex-shrink-0" onClick={e => e.stopPropagation()}>
        <button
          onClick={onStop}
          className="p-1.5 rounded hover:bg-warning/20 text-warning transition-colors"
          title="Stop run"
        >
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 9v6m4-6v6m7-3a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        </button>
        <button
          onClick={onStopKill}
          className="p-1.5 rounded hover:bg-danger/20 text-danger transition-colors"
          title="Stop & kill game"
        >
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>
    </div>
  );
}

/**
 * QueuedRunCard - Pending run in queue
 */
interface QueuedRunCardProps {
  run: AutomationRun;
  onClick?: () => void;
}

function QueuedRunCard({ run, onClick }: QueuedRunCardProps) {
  return (
    <div
      className="flex items-center gap-3 p-2.5 bg-surface-elevated/50 rounded-lg border border-border cursor-pointer hover:border-border-hover transition-colors opacity-70"
      onClick={onClick}
    >
      {/* Queue indicator */}
      <div className="w-9 h-9 rounded-full bg-surface border border-border flex items-center justify-center flex-shrink-0">
        <svg className="w-4 h-4 text-text-muted" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      </div>

      {/* Info */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-text-secondary truncate">
            {run.game_name}
          </span>
          <span className="px-1.5 py-0.5 text-[9px] bg-surface border border-border rounded text-text-muted">
            QUEUED
          </span>
        </div>
        <div className="text-[10px] text-text-muted font-mono">
          {run.sut_ip} | {run.iterations} iteration{run.iterations > 1 ? 's' : ''}
        </div>
      </div>
    </div>
  );
}

/**
 * CampaignCard - Multi-game campaign progress
 */
interface CampaignCardProps {
  campaign: Campaign;
  onStop?: () => void;
}

function CampaignCard({ campaign, onStop }: CampaignCardProps) {
  const progressPercent = campaign.progress.total_games > 0
    ? Math.round((campaign.progress.completed_games / campaign.progress.total_games) * 100)
    : 0;

  return (
    <div className="p-2.5 bg-gradient-to-r from-primary/10 to-brand-cyan/10 rounded-lg border border-primary/30">
      {/* Header */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="px-1.5 py-0.5 text-[9px] bg-primary/20 text-primary rounded font-medium">
            CAMPAIGN
          </span>
          <span className="text-xs font-medium text-text-primary truncate">
            {campaign.name}
          </span>
        </div>
        {onStop && (
          <button
            onClick={onStop}
            className="p-1 rounded hover:bg-danger/20 text-danger transition-colors"
            title="Stop campaign"
          >
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        )}
      </div>

      {/* Progress bar */}
      <div className="flex items-center gap-2">
        <div className="flex-1 h-1.5 bg-surface rounded-full overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-primary to-brand-cyan transition-all duration-300"
            style={{ width: `${progressPercent}%` }}
          />
        </div>
        <span className="text-[10px] font-numbers text-text-muted">
          {campaign.progress.completed_games}/{campaign.progress.total_games}
        </span>
      </div>

      {/* Current game */}
      {campaign.progress.current_game && (
        <div className="mt-1.5 flex items-center gap-2 text-[10px]">
          <span className="w-1.5 h-1.5 rounded-full bg-success animate-pulse" />
          <span className="text-text-secondary">{campaign.progress.current_game}</span>
        </div>
      )}

      {/* Failed games warning */}
      {campaign.progress.failed_games > 0 && (
        <div className="mt-1.5 text-[10px] text-danger">
          {campaign.progress.failed_games} game{campaign.progress.failed_games > 1 ? 's' : ''} failed
        </div>
      )}
    </div>
  );
}

/**
 * MiniRunIndicator - Ultra-compact run status dot
 */
export function MiniRunIndicator({ run }: { run: AutomationRun }) {
  const progressPercent = getProgressPercent(run.progress);

  return (
    <div
      className="relative w-4 h-4 cursor-pointer"
      title={`${run.game_name} - ${progressPercent}%`}
    >
      <MiniGauge
        value={progressPercent}
        max={100}
        color={run.status === 'running' ? 'primary' : 'warning'}
        size={16}
      />
    </div>
  );
}
