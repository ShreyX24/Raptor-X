/**
 * MultiSUTPanel - Multi-SUT parallel campaign monitoring
 * Shows per-SUT progress cards with account lock indicators
 */

import { useMemo } from 'react';
import { MiniGauge } from './RadialGauge';
import type {
  MultiSUTCampaign,
  SUTWorkStatus,
  AccountLockStatus,
  AccountStatusResponse,
} from '../api';

interface MultiSUTPanelProps {
  campaigns: MultiSUTCampaign[];
  accountStatus?: AccountStatusResponse | null;
  onStopCampaign?: (campaignId: string) => void;
  maxHeight?: string;
  className?: string;
}

export function MultiSUTPanel({
  campaigns,
  accountStatus,
  onStopCampaign,
  maxHeight = '400px',
  className = '',
}: MultiSUTPanelProps) {
  const activeCampaigns = useMemo(() =>
    campaigns.filter(c => c.status === 'running' || c.status === 'queued'),
    [campaigns]
  );

  const hasActive = activeCampaigns.length > 0;

  return (
    <div className={`bg-surface border border-border rounded-lg overflow-hidden ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 bg-gradient-to-r from-primary/10 to-brand-cyan/10 border-b border-border">
        <h3 className="text-xs font-semibold text-text-secondary uppercase tracking-wide flex items-center gap-2">
          <svg className="w-4 h-4 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 17V7m0 10a2 2 0 01-2 2H5a2 2 0 01-2-2V7a2 2 0 012-2h2a2 2 0 012 2m0 10a2 2 0 002 2h2a2 2 0 002-2M9 7a2 2 0 012-2h2a2 2 0 012 2m0 10V7m0 10a2 2 0 002 2h2a2 2 0 002-2V7a2 2 0 00-2-2h-2a2 2 0 00-2 2" />
          </svg>
          Multi-SUT Campaigns
        </h3>
        {hasActive && (
          <span className="flex items-center gap-1 text-xs font-numbers">
            <span className="w-1.5 h-1.5 rounded-full bg-success animate-pulse" />
            <span className="text-success">{activeCampaigns.length} active</span>
          </span>
        )}
      </div>

      {/* Account Status Bar */}
      {accountStatus && (
        <AccountStatusBar af={accountStatus.af} gz={accountStatus.gz} />
      )}

      {/* Content */}
      <div className="overflow-y-auto p-2 space-y-3" style={{ maxHeight }}>
        {activeCampaigns.length === 0 ? (
          <div className="text-center py-8 text-text-muted text-xs">
            <svg className="w-8 h-8 mx-auto mb-2 opacity-30" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
            </svg>
            No active multi-SUT campaigns
          </div>
        ) : (
          activeCampaigns.map((campaign) => (
            <MultiSUTCampaignCard
              key={campaign.campaign_id}
              campaign={campaign}
              onStop={() => onStopCampaign?.(campaign.campaign_id)}
            />
          ))
        )}
      </div>
    </div>
  );
}

/**
 * AccountStatusBar - Shows which SUT holds each Steam account
 */
interface AccountStatusBarProps {
  af: AccountLockStatus;
  gz: AccountLockStatus;
}

function AccountStatusBar({ af, gz }: AccountStatusBarProps) {
  return (
    <div className="flex items-center gap-4 px-3 py-2 bg-surface-elevated/30 border-b border-border">
      <AccountLockIndicator label="A-F" status={af} />
      <AccountLockIndicator label="G-Z" status={gz} />
    </div>
  );
}

function AccountLockIndicator({ label, status }: { label: string; status: AccountLockStatus }) {
  const isLocked = status.locked;

  return (
    <div className="flex items-center gap-2">
      <div className={`w-2 h-2 rounded-full ${isLocked ? 'bg-warning' : 'bg-success'}`} />
      <span className="text-[10px] font-medium text-text-secondary">{label}:</span>
      {isLocked ? (
        <div className="flex items-center gap-1">
          <span className="text-[10px] font-mono text-warning">{status.holder_sut}</span>
          {status.game_running && (
            <span className="text-[10px] text-text-muted">({status.game_running})</span>
          )}
        </div>
      ) : (
        <span className="text-[10px] text-success">Available</span>
      )}
    </div>
  );
}

/**
 * MultiSUTCampaignCard - Campaign with per-SUT progress cards
 */
interface MultiSUTCampaignCardProps {
  campaign: MultiSUTCampaign;
  onStop?: () => void;
}

function MultiSUTCampaignCard({ campaign, onStop }: MultiSUTCampaignCardProps) {
  const statusColor = {
    queued: 'text-warning',
    running: 'text-success',
    completed: 'text-primary',
    failed: 'text-danger',
    stopped: 'text-text-muted',
    partially_completed: 'text-warning',
  }[campaign.status] || 'text-text-muted';

  return (
    <div className="bg-surface-elevated rounded-lg border border-primary/30 overflow-hidden">
      {/* Campaign Header */}
      <div className="flex items-center justify-between px-3 py-2 bg-gradient-to-r from-primary/10 to-brand-cyan/10">
        <div className="flex items-center gap-2">
          <span className="px-1.5 py-0.5 text-[9px] bg-primary/20 text-primary rounded font-medium">
            MULTI-SUT
          </span>
          <span className="text-xs font-medium text-text-primary">
            {campaign.name || `Campaign ${campaign.campaign_id.slice(0, 8)}`}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className={`text-[10px] font-medium uppercase ${statusColor}`}>
            {campaign.status.replace('_', ' ')}
          </span>
          {onStop && campaign.status === 'running' && (
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
      </div>

      {/* Overall Progress */}
      <div className="px-3 py-2 border-b border-border/50">
        <div className="flex items-center gap-2 mb-1">
          <div className="flex-1 h-1.5 bg-surface rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-primary to-brand-cyan transition-all duration-300"
              style={{ width: `${campaign.progress_percent}%` }}
            />
          </div>
          <span className="text-[10px] font-numbers text-text-muted">
            {campaign.completed_games}/{campaign.total_games} games
          </span>
        </div>
        {campaign.failed_games > 0 && (
          <span className="text-[10px] text-danger">
            {campaign.failed_games} failed
          </span>
        )}
      </div>

      {/* Per-SUT Progress Cards */}
      <div className="p-2 space-y-2">
        {Object.entries(campaign.sut_status).map(([sutIp, work]) => (
          <SUTWorkCard key={sutIp} sutIp={sutIp} work={work} />
        ))}
      </div>
    </div>
  );
}

/**
 * SUTWorkCard - Individual SUT progress within a multi-SUT campaign
 */
interface SUTWorkCardProps {
  sutIp: string;
  work: SUTWorkStatus;
}

function SUTWorkCard({ sutIp, work }: SUTWorkCardProps) {
  const totalGames = work.pending_count + work.completed_count + work.failed_count;
  const completedCount = work.completed_count;
  const progressPercent = totalGames > 0 ? Math.round((completedCount / totalGames) * 100) : 0;

  const isRunning = !!work.current_game;
  const pendingCount = work.pending_count;
  const isWaiting = !isRunning && pendingCount > 0;
  const isDone = pendingCount === 0 && !work.current_game;

  // Determine account type for current game
  const currentAccountType = work.current_account
    ? (work.current_account === 'af' ? 'A-F' : 'G-Z')
    : null;

  return (
    <div className={`flex items-center gap-3 p-2 rounded-lg border ${
      isRunning ? 'bg-surface border-success/30' :
      isWaiting ? 'bg-surface-elevated/50 border-warning/30' :
      isDone ? 'bg-surface-elevated/30 border-border' :
      'bg-surface-elevated/50 border-border'
    }`}>
      {/* Progress Gauge */}
      <div className="relative flex-shrink-0">
        <MiniGauge
          value={progressPercent}
          max={100}
          color={isRunning ? 'success' : isDone ? 'primary' : 'warning'}
          size={32}
        />
        <span className="absolute inset-0 flex items-center justify-center text-[8px] font-numbers font-bold text-text-primary">
          {progressPercent}%
        </span>
      </div>

      {/* SUT Info */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-mono font-medium text-text-primary">
            {sutIp}
          </span>
          {isRunning && (
            <span className="w-1.5 h-1.5 rounded-full bg-success animate-pulse" />
          )}
          {isWaiting && (
            <span className="px-1 py-0.5 text-[8px] bg-warning/20 text-warning rounded">
              WAITING
            </span>
          )}
          {isDone && (
            <span className="px-1 py-0.5 text-[8px] bg-success/20 text-success rounded">
              DONE
            </span>
          )}
        </div>

        {/* Current game or status */}
        {work.current_game ? (
          <div className="flex items-center gap-2 mt-0.5">
            <span className="text-[10px] text-text-secondary truncate">
              {work.current_game}
            </span>
            {currentAccountType && (
              <span className="px-1 py-0.5 text-[8px] bg-primary/20 text-primary rounded">
                {currentAccountType}
              </span>
            )}
          </div>
        ) : isWaiting ? (
          <div className="text-[10px] text-text-muted mt-0.5">
            {pendingCount} game{pendingCount > 1 ? 's' : ''} pending
          </div>
        ) : (
          <div className="text-[10px] text-success mt-0.5">
            {completedCount} game{completedCount !== 1 ? 's' : ''} completed
          </div>
        )}
      </div>

      {/* Stats */}
      <div className="flex-shrink-0 text-right">
        <div className="text-[10px] font-numbers text-text-muted">
          {completedCount}/{totalGames}
        </div>
        {work.failed_count > 0 && (
          <div className="text-[9px] text-danger">
            {work.failed_count} failed
          </div>
        )}
      </div>
    </div>
  );
}

export default MultiSUTPanel;
