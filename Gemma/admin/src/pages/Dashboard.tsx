/**
 * Dashboard - Information-dense control center
 * Shows all services, metrics, and quick actions in a compact layout
 */

import { useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { useSystemStatus, useDevices, useGames, useRuns, useQueueStats } from '../hooks';
import {
  MetricCard,
  MetricGrid,
  QueueDepthChart,
  StatusDot,
  RunCard,
  RecentRunsTable,
} from '../components';
import type { SUT, GameConfig, SUTSystemInfo } from '../types';
import { formatCpuDisplay, formatGpuDisplay, formatRamDisplay } from '../utils/cpuCodenames';

// Compact SUT Card for dashboard
function CompactSUTCard({
  sut,
  isSelected,
  onClick,
}: {
  sut: SUT;
  isSelected: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`
        w-full p-2.5 rounded-lg border text-left transition-all
        ${isSelected
          ? 'bg-primary/20 border-primary glow'
          : 'bg-surface border-border hover:border-border-hover hover:bg-surface-hover'
        }
      `}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <StatusDot status={sut.status === 'online' ? 'online' : 'offline'} />
          <span className="text-sm font-medium text-text-primary truncate max-w-[100px]">
            {sut.hostname || sut.ip}
          </span>
        </div>
        <div className="flex items-center gap-2 text-xs text-text-muted">
          {sut.current_task && (
            <span className="text-warning" title="Running task">
              ...
            </span>
          )}
          {sut.success_rate !== undefined && sut.success_rate > 0 && (
            <span className="font-numbers tabular-nums">
              {Math.round(sut.success_rate * 100)}%
            </span>
          )}
        </div>
      </div>
    </button>
  );
}

// Quick action button
function ActionButton({
  label,
  onClick,
  disabled,
  variant = 'default',
}: {
  label: string;
  onClick: () => void;
  disabled?: boolean;
  variant?: 'default' | 'primary' | 'danger';
}) {
  const variants = {
    default: 'bg-surface-elevated hover:bg-surface-hover text-text-secondary border border-border',
    primary: 'bg-primary hover:bg-primary-dark text-white',
    danger: 'bg-danger/80 hover:bg-danger text-white',
  };

  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`
        px-3 py-1.5 rounded-lg text-sm font-medium transition-all
        ${variants[variant]}
        ${disabled ? 'opacity-50 cursor-not-allowed' : ''}
      `}
    >
      {label}
    </button>
  );
}

export function Dashboard() {
  // Core data hooks
  useSystemStatus();
  const { devices, onlineDevices } = useDevices();
  const { gamesList } = useGames();
  const { activeRunsList, history, start, stop } = useRuns();

  // New hooks for enhanced dashboard
  const { stats: queueStats, depthHistory, isAvailable: queueAvailable } = useQueueStats();

  // UI state
  const [selectedSut, setSelectedSut] = useState<SUT | null>(null);
  const [selectedGame, setSelectedGame] = useState<GameConfig | null>(null);
  const [iterations, setIterations] = useState(1);
  const [isStarting, setIsStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sutSystemInfo, setSutSystemInfo] = useState<SUTSystemInfo | null>(null);
  const [sutInfoLoading, setSutInfoLoading] = useState(false);

  // Fetch SUT system info when a SUT is selected
  const fetchSutSystemInfo = useCallback(async (sutIp: string) => {
    setSutInfoLoading(true);
    try {
      const response = await fetch(`/api/sut/by-ip/${sutIp}/system_info`, {
        signal: AbortSignal.timeout(10000),
      });
      if (response.ok) {
        const result = await response.json();
        setSutSystemInfo(result.data || null);
      } else {
        setSutSystemInfo(null);
      }
    } catch {
      setSutSystemInfo(null);
    } finally {
      setSutInfoLoading(false);
    }
  }, []);

  // Handle SUT selection
  const handleSelectSut = useCallback((sut: SUT | null) => {
    setSelectedSut(sut);
    if (sut) {
      fetchSutSystemInfo(sut.ip);
    } else {
      setSutSystemInfo(null);
    }
  }, [fetchSutSystemInfo]);

  // Handlers
  const handleStartRun = async () => {
    if (!selectedSut || !selectedGame) return;

    setIsStarting(true);
    setError(null);

    try {
      await start(selectedSut.ip, selectedGame.name, iterations);
      setSelectedSut(null);
      setSelectedGame(null);
      setIterations(1);
      setSutSystemInfo(null);  // Clear system info after starting
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start run');
    } finally {
      setIsStarting(false);
    }
  };

  const handleStopAll = async () => {
    for (const run of activeRunsList) {
      await stop(run.run_id).catch(console.error);
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-96px)] p-4 bg-background text-text-primary overflow-hidden">
      {/* Error Banner */}
      {error && (
        <div className="flex items-center justify-between bg-danger/20 border border-danger/50 rounded-lg px-4 py-2 mb-4 flex-shrink-0">
          <span className="text-danger text-sm">{error}</span>
          <button
            onClick={() => setError(null)}
            className="text-danger/70 hover:text-danger text-sm"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Main Grid - Fills remaining space */}
      <div className="grid grid-cols-12 gap-4 flex-1 min-h-0">
        {/* Left Panel (5 cols) - Metrics + SUTs + Quick Start + Recent Jobs */}
        <div className="col-span-12 lg:col-span-5 flex flex-col gap-4 min-h-0">
          {/* Metrics Grid */}
          <div className="flex-shrink-0">
            <MetricGrid columns={3} gap="sm">
              <MetricCard
                label="Online SUTs"
                value={onlineDevices.length}
                sublabel={`of ${devices.length} total`}
                color={onlineDevices.length > 0 ? 'success' : 'default'}
              />
              <MetricCard
                label="Active Runs"
                value={activeRunsList.length}
                color={activeRunsList.length > 0 ? 'info' : 'default'}
              />
              <MetricCard
                label="Queue"
                value={queueStats?.current_queue_size ?? '-'}
                sublabel={queueAvailable ? 'items' : 'unavailable'}
                color={
                  !queueAvailable ? 'error' :
                  (queueStats?.current_queue_size ?? 0) > 10 ? 'warning' : 'default'
                }
              />
              <MetricCard
                label="Games"
                value={gamesList.length}
              />
              <MetricCard
                label="Processed"
                value={queueStats?.total_requests ?? 0}
                sublabel="total jobs"
              />
              <MetricCard
                label="Avg Time"
                value={queueStats?.avg_processing_time
                  ? `${(queueStats.avg_processing_time).toFixed(1)}s`
                  : '-'
                }
                sublabel="per job"
              />
            </MetricGrid>
          </div>

          {/* Online SUTs Grid */}
          <div className="card p-4 flex-shrink-0">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold text-text-secondary">Online SUTs</h3>
              <Link to="/devices" className="text-xs text-primary hover:text-primary-dark transition-colors">
                View All
              </Link>
            </div>

            {onlineDevices.length === 0 ? (
              <div className="text-center py-4 text-text-muted text-sm">No online SUTs</div>
            ) : (
              <div className="grid grid-cols-2 gap-2">
                {onlineDevices.slice(0, 4).map((sut) => (
                  <CompactSUTCard
                    key={sut.device_id}
                    sut={sut}
                    isSelected={selectedSut?.device_id === sut.device_id}
                    onClick={() => handleSelectSut(sut)}
                  />
                ))}
              </div>
            )}

            {onlineDevices.length > 4 && (
              <div className="text-center mt-2">
                <Link to="/devices" className="text-xs text-text-muted hover:text-text-secondary transition-colors">
                  +{onlineDevices.length - 4} more
                </Link>
              </div>
            )}
          </div>

          {/* Quick Start Panel */}
          <div className="card p-4 flex-shrink-0">
            <h3 className="text-sm font-semibold text-text-secondary mb-3">Quick Start</h3>

            <div className="space-y-3">
              {/* Selected SUT */}
              <div className="flex items-center justify-between p-2.5 bg-surface-elevated rounded-lg text-sm">
                <span className="text-text-muted">SUT:</span>
                {selectedSut ? (
                  <div className="flex items-center gap-2">
                    <span className="text-text-primary font-medium">{selectedSut.hostname || selectedSut.ip}</span>
                    <button onClick={() => handleSelectSut(null)} className="text-text-muted hover:text-text-secondary">×</button>
                  </div>
                ) : (
                  <span className="text-text-muted italic">Select above</span>
                )}
              </div>

              {/* SUT System Info - shown when SUT is selected */}
              {selectedSut && (
                <div className="p-3 bg-surface-elevated/50 rounded-lg border border-border text-xs">
                  {sutInfoLoading ? (
                    <div className="text-text-muted animate-pulse">Loading system info...</div>
                  ) : sutSystemInfo ? (
                    <div className="space-y-1.5">
                      <div className="flex items-center gap-2">
                        <span className="text-brand-cyan font-medium">{formatCpuDisplay(sutSystemInfo.cpu.brand_string)}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-success">{formatGpuDisplay(sutSystemInfo.gpu.name)}</span>
                        <span className="text-text-muted">•</span>
                        <span className="text-primary">{formatRamDisplay(sutSystemInfo.ram.total_gb)}</span>
                      </div>
                      <div className="flex items-center gap-2 text-text-muted">
                        <span className="font-numbers">{sutSystemInfo.screen.width}x{sutSystemInfo.screen.height}</span>
                        <span>•</span>
                        <span>{sutSystemInfo.os.name} {sutSystemInfo.os.build && `(${sutSystemInfo.os.build})`}</span>
                      </div>
                      {sutSystemInfo.bios?.name && (
                        <div className="text-text-muted/70 text-[10px]">
                          BIOS: {sutSystemInfo.bios.name} {sutSystemInfo.bios.version && `v${sutSystemInfo.bios.version}`}
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="text-text-muted">System info unavailable</div>
                  )}
                </div>
              )}

              {/* Game Selection */}
              <div className="flex items-center justify-between p-2.5 bg-surface-elevated rounded-lg text-sm">
                <span className="text-text-muted">Game:</span>
                <select
                  value={selectedGame?.name || ''}
                  onChange={(e) => {
                    const game = gamesList.find(g => g.name === e.target.value);
                    setSelectedGame(game || null);
                  }}
                  disabled={!selectedSut}
                  className="input text-sm py-1 px-2 max-w-[180px] disabled:opacity-50"
                >
                  <option value="">Select game</option>
                  {gamesList.map((game) => (
                    <option key={game.name} value={game.name}>
                      {game.display_name || game.name}
                    </option>
                  ))}
                </select>
              </div>

              {/* Iterations Selection */}
              <div className="flex items-center justify-between p-2.5 bg-surface-elevated rounded-lg text-sm">
                <span className="text-text-muted">Iterations:</span>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setIterations(Math.max(1, iterations - 1))}
                    className="w-7 h-7 flex items-center justify-center bg-surface hover:bg-surface-hover border border-border rounded-lg text-text-secondary transition-colors"
                  >
                    -
                  </button>
                  <input
                    type="number"
                    min="1"
                    max="10"
                    value={iterations}
                    onChange={(e) => setIterations(Math.max(1, Math.min(10, parseInt(e.target.value) || 1)))}
                    className="w-12 text-center input py-1 font-numbers"
                  />
                  <button
                    onClick={() => setIterations(Math.min(10, iterations + 1))}
                    className="w-7 h-7 flex items-center justify-center bg-surface hover:bg-surface-hover border border-border rounded-lg text-text-secondary transition-colors"
                  >
                    +
                  </button>
                </div>
              </div>

              {/* Start Button */}
              <button
                onClick={handleStartRun}
                disabled={!selectedSut || !selectedGame || isStarting}
                className={`
                  w-full py-2.5 rounded-lg font-semibold text-sm transition-all
                  ${selectedSut && selectedGame
                    ? 'bg-success hover:bg-success/80 text-white glow-success'
                    : 'bg-surface-elevated text-text-muted cursor-not-allowed'
                  }
                `}
              >
                {isStarting ? 'Starting...' : `Start Automation${iterations > 1 ? ` (${iterations}x)` : ''}`}
              </button>
            </div>
          </div>

          {/* Recent Runs - Only show in left panel when active runs exist */}
          {activeRunsList.length > 0 && (
            <div className="card p-4 flex-1 min-h-0 flex flex-col">
              <div className="flex items-center justify-between mb-3 flex-shrink-0">
                <h3 className="text-sm font-semibold text-text-secondary">Recent Runs</h3>
                <Link to="/runs" className="text-xs text-primary hover:text-primary-dark transition-colors">
                  View All
                </Link>
              </div>
              <div className="flex-1 min-h-0 overflow-y-auto">
                <RecentRunsTable
                  runs={history}
                  maxRows={6}
                  onRerun={(sutIp, gameName, iterations) => {
                    start(sutIp, gameName, iterations).catch(console.error);
                  }}
                />
              </div>
            </div>
          )}
        </div>

        {/* Right Panel (7 cols) - Queue Depth + Active Runs + Actions */}
        <div className="col-span-12 lg:col-span-7 flex flex-col gap-4 min-h-0">
          {/* Queue Depth Chart */}
          <div className="flex-shrink-0">
            <QueueDepthChart
              data={depthHistory}
              height={140}
            />
          </div>

          {/* Active Runs - Collapses when empty, expands when has runs */}
          <div className={`card p-4 flex flex-col ${activeRunsList.length > 0 ? 'flex-1 min-h-0' : 'flex-shrink-0'}`}>
            <div className="flex items-center justify-between mb-3 flex-shrink-0">
              <h3 className="text-sm font-semibold text-text-secondary">
                Active Runs <span className="font-numbers text-primary">({activeRunsList.length})</span>
              </h3>
              {activeRunsList.length > 0 && (
                <ActionButton
                  label="Stop All"
                  variant="danger"
                  onClick={handleStopAll}
                />
              )}
            </div>

            {activeRunsList.length === 0 ? (
              <div className="text-center py-2 text-text-muted text-sm border border-dashed border-border rounded-lg">
                No active runs - start automation above
              </div>
            ) : (
              <div className="flex-1 min-h-0 overflow-y-auto">
                <div className="space-y-2">
                  {activeRunsList.map((run) => (
                    <RunCard
                      key={run.run_id}
                      run={run}
                      onStop={(id, killGame) => stop(id, killGame).catch(console.error)}
                    />
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Recent Runs Table - Expands when no active runs */}
          {activeRunsList.length === 0 && (
            <div className="card p-4 flex-1 min-h-0 flex flex-col">
              <div className="flex items-center justify-between mb-3 flex-shrink-0">
                <h3 className="text-sm font-semibold text-text-secondary">Recent Runs</h3>
                <Link to="/runs" className="text-xs text-primary hover:text-primary-dark transition-colors">
                  View All
                </Link>
              </div>
              <div className="flex-1 min-h-0 overflow-y-auto">
                <RecentRunsTable
                  runs={history}
                  maxRows={10}
                  onRerun={(sutIp, gameName, iterations) => {
                    start(sutIp, gameName, iterations).catch(console.error);
                  }}
                />
              </div>
            </div>
          )}

        </div>
      </div>
    </div>
  );
}
