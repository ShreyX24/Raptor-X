/**
 * SUTDetailPanel - Detailed view of a selected SUT showing hardware info, max resolution, and installed games
 */

import { useState, useEffect } from 'react';
import type { SUT } from '../types';
import {
  getSutSystemInfoByIp,
  getSutInstalledGames,
  type SUTSystemInfo,
  type InstalledGame,
} from '../api';
import { restartSut } from '../api/workflowBuilder';

interface SUTDetailPanelProps {
  sut: SUT | null;
  onClose?: () => void;
}

// Resolution mapping for display
const RESOLUTION_NAMES: Record<string, string> = {
  '1280x720': '720p HD',
  '1920x1080': '1080p Full HD',
  '2560x1440': '1440p 2K QHD',
  '3840x2160': '2160p 4K UHD',
  '3440x1440': '1440p Ultrawide',
  '5120x1440': '1440p Super Ultrawide',
};

function getResolutionName(width: number, height: number): string {
  const key = `${width}x${height}`;
  return RESOLUTION_NAMES[key] || `${width}x${height}`;
}

function getMaxPresetResolution(_width: number, height: number): string {
  // Determine what preset resolution category this SUT supports (based on vertical resolution)
  if (height >= 2160) return '2160p (4K)';
  if (height >= 1440) return '1440p (2K)';
  if (height >= 1080) return '1080p';
  return '720p';
}

// Icons
const GpuIcon = () => (
  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z" />
  </svg>
);

const CpuIcon = () => (
  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2z" />
  </svg>
);

const RamIcon = () => (
  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
  </svg>
);

const ScreenIcon = () => (
  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
  </svg>
);

const GameIcon = () => (
  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
  </svg>
);

const CloseIcon = () => (
  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
  </svg>
);

const RestartIcon = () => (
  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
  </svg>
);

const KeyIcon = () => (
  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
  </svg>
);

const CheckCircleIcon = () => (
  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
  </svg>
);

const XCircleIcon = () => (
  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" />
  </svg>
);

interface HardwareRowProps {
  icon: React.ReactNode;
  label: string;
  value: string;
  subValue?: string;
}

function HardwareRow({ icon, label, value, subValue }: HardwareRowProps) {
  return (
    <div className="flex items-start gap-3 py-2">
      <span className="text-text-muted mt-0.5">{icon}</span>
      <div className="flex-1 min-w-0">
        <p className="text-xs text-text-muted uppercase tracking-wide">{label}</p>
        <p className="text-sm font-medium text-text-primary truncate" title={value}>{value}</p>
        {subValue && <p className="text-xs text-text-secondary">{subValue}</p>}
      </div>
    </div>
  );
}

export function SUTDetailPanel({ sut, onClose }: SUTDetailPanelProps) {
  const [systemInfo, setSystemInfo] = useState<SUTSystemInfo | null>(null);
  const [installedGames, setInstalledGames] = useState<InstalledGame[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [restarting, setRestarting] = useState(false);
  const [restartMessage, setRestartMessage] = useState<string | null>(null);

  const handleRestart = async () => {
    if (!sut || sut.status !== 'online') return;
    if (!confirm(`Restart SUT client on ${sut.hostname || sut.ip}? The SUT will go offline briefly.`)) return;

    setRestarting(true);
    setRestartMessage(null);
    try {
      await restartSut(sut.device_id);
      setRestartMessage('Restart initiated');
    } catch (err) {
      setRestartMessage(err instanceof Error ? err.message : 'Restart failed');
    } finally {
      setRestarting(false);
    }
  };

  useEffect(() => {
    if (!sut || sut.status !== 'online') {
      setSystemInfo(null);
      setInstalledGames([]);
      return;
    }

    const sutIp = sut.ip;

    async function fetchDetails() {
      setLoading(true);
      setError(null);

      try {
        // Fetch system info and installed games in parallel
        const [sysInfoResult, gamesResult] = await Promise.allSettled([
          getSutSystemInfoByIp(sutIp),
          getSutInstalledGames(sutIp),
        ]);

        if (sysInfoResult.status === 'fulfilled' && sysInfoResult.value) {
          // API now returns SUTSystemInfo directly
          setSystemInfo(sysInfoResult.value);
        }

        if (gamesResult.status === 'fulfilled') {
          setInstalledGames(gamesResult.value.games || []);
        }

        // Check if both failed
        if (sysInfoResult.status === 'rejected' && gamesResult.status === 'rejected') {
          setError('Failed to fetch SUT details');
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to fetch details');
      } finally {
        setLoading(false);
      }
    }

    fetchDetails();
  }, [sut?.ip, sut?.status]);

  if (!sut) {
    return (
      <div className="card p-6 h-full flex items-center justify-center">
        <p className="text-text-muted text-sm">Select a SUT to view details</p>
      </div>
    );
  }

  const statusColors: Record<string, string> = {
    online: 'bg-success',
    offline: 'bg-text-muted',
    busy: 'bg-warning',
    error: 'bg-danger',
  };

  return (
    <div className="card p-4 h-full flex flex-col overflow-hidden">
      {/* Header */}
      <div className="flex items-start justify-between mb-4 pb-4 border-b border-border">
        <div className="flex items-center gap-3">
          <div className={`h-3 w-3 rounded-full ${statusColors[sut.status]}`} />
          <div>
            <h2 className="text-lg font-semibold text-text-primary">{sut.hostname || sut.ip}</h2>
            <p className="text-sm text-text-muted">{sut.ip}:{sut.port}</p>
          </div>
        </div>
        <div className="flex items-center gap-1">
          {sut.status === 'online' && (
            <button
              onClick={handleRestart}
              disabled={restarting}
              className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium rounded-lg border border-border bg-surface-elevated hover:bg-surface-hover text-text-secondary hover:text-text-primary transition-colors disabled:opacity-50"
              title="Restart SUT client"
            >
              <RestartIcon />
              {restarting ? 'Restarting...' : 'Restart'}
            </button>
          )}
          {onClose && (
            <button
              onClick={onClose}
              className="p-1 rounded hover:bg-surface-elevated transition-colors text-text-muted hover:text-text-primary"
            >
              <CloseIcon />
            </button>
          )}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto space-y-6">
        {/* Status badges */}
        <div className="flex flex-wrap gap-2">
          <span className={`px-2.5 py-1 rounded-full text-xs font-medium ${
            sut.status === 'online' ? 'bg-success/10 text-success' :
            sut.status === 'busy' ? 'bg-warning/10 text-warning' :
            sut.status === 'error' ? 'bg-danger/10 text-danger' :
            'bg-surface-elevated text-text-muted'
          }`}>
            {sut.status.charAt(0).toUpperCase() + sut.status.slice(1)}
          </span>
          {sut.is_paired && (
            <span className="px-2.5 py-1 rounded-full text-xs font-medium bg-primary/10 text-primary">
              Paired
            </span>
          )}
          {sut.master_key_installed && (
            <span className="px-2.5 py-1 rounded-full text-xs font-medium bg-success/10 text-success">
              SSH Ready
            </span>
          )}
          {sut.current_task && (
            <span className="px-2.5 py-1 rounded-full text-xs font-medium bg-warning/10 text-warning">
              Running: {sut.current_task}
            </span>
          )}
        </div>

        {/* Restart message */}
        {restartMessage && (
          <div className={`p-2 rounded-lg text-xs ${
            restartMessage === 'Restart initiated'
              ? 'bg-success/10 text-success border border-success/20'
              : 'bg-danger/10 text-danger border border-danger/20'
          }`}>
            {restartMessage}
          </div>
        )}

        {/* SSH Status */}
        {(sut.ssh_fingerprint || sut.master_key_installed !== undefined) && (
          <div>
            <h3 className="text-xs font-semibold text-text-muted uppercase tracking-wide mb-2 flex items-center gap-2">
              <KeyIcon />
              SSH Status
            </h3>
            <div className="bg-surface-elevated rounded-lg p-3 space-y-2">
              {/* Master -> SUT SSH */}
              <div className="flex items-center justify-between">
                <span className="text-sm text-text-secondary">Master → SUT</span>
                <span className={`flex items-center gap-1 text-sm ${sut.master_key_installed ? 'text-success' : 'text-text-muted'}`}>
                  {sut.master_key_installed ? <CheckCircleIcon /> : <XCircleIcon />}
                  {sut.master_key_installed ? 'Ready' : 'Not configured'}
                </span>
              </div>
              {/* SUT -> Master SSH */}
              <div className="flex items-center justify-between">
                <span className="text-sm text-text-secondary">SUT → Master</span>
                <span className={`flex items-center gap-1 text-sm ${sut.ssh_fingerprint ? 'text-success' : 'text-text-muted'}`}>
                  {sut.ssh_fingerprint ? <CheckCircleIcon /> : <XCircleIcon />}
                  {sut.ssh_fingerprint ? 'Registered' : 'Not registered'}
                </span>
              </div>
              {/* Fingerprint */}
              {sut.ssh_fingerprint && (
                <div className="pt-2 border-t border-border">
                  <p className="text-xs text-text-muted">SUT Key Fingerprint</p>
                  <p className="text-xs font-mono text-text-secondary truncate" title={sut.ssh_fingerprint}>
                    {sut.ssh_fingerprint}
                  </p>
                </div>
              )}
              {/* Session ID */}
              {sut.session_id && (
                <div className="pt-2 border-t border-border">
                  <p className="text-xs text-text-muted">Session ID</p>
                  <p className="text-xs font-mono text-text-secondary">{sut.session_id}</p>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Loading state */}
        {loading && (
          <div className="space-y-3">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="h-12 bg-surface-elevated rounded animate-pulse" />
            ))}
          </div>
        )}

        {/* Error state */}
        {error && !loading && (
          <div className="p-3 bg-danger/10 border border-danger/20 rounded-lg">
            <p className="text-sm text-danger">{error}</p>
          </div>
        )}

        {/* System Info */}
        {!loading && systemInfo && (
          <div>
            <h3 className="text-xs font-semibold text-text-muted uppercase tracking-wide mb-2">
              Hardware
            </h3>
            <div className="bg-surface-elevated rounded-lg p-3 divide-y divide-border">
              <HardwareRow
                icon={<GpuIcon />}
                label="GPU"
                value={systemInfo.gpu?.name || 'Unknown'}
              />
              <HardwareRow
                icon={<CpuIcon />}
                label="CPU"
                value={systemInfo.cpu?.brand_string || 'Unknown'}
              />
              <HardwareRow
                icon={<RamIcon />}
                label="Memory"
                value={systemInfo.ram ? `${systemInfo.ram.total_gb} GB` : 'Unknown'}
              />
              <HardwareRow
                icon={<ScreenIcon />}
                label="Display"
                value={systemInfo.screen
                  ? getResolutionName(systemInfo.screen.width, systemInfo.screen.height)
                  : 'Unknown'
                }
                subValue={systemInfo.screen
                  ? `Max Preset: ${getMaxPresetResolution(systemInfo.screen.width, systemInfo.screen.height)}`
                  : undefined
                }
              />
            </div>
          </div>
        )}

        {/* Max Resolution Badge */}
        {!loading && systemInfo?.screen && (
          <div className="flex items-center gap-2 p-3 bg-primary/5 border border-primary/20 rounded-lg">
            <ScreenIcon />
            <div>
              <p className="text-xs text-text-muted">Maximum Preset Resolution</p>
              <p className="text-sm font-semibold text-primary">
                {getMaxPresetResolution(systemInfo.screen.width, systemInfo.screen.height)}
              </p>
            </div>
          </div>
        )}

        {/* Installed Games */}
        {!loading && (
          <div>
            <h3 className="text-xs font-semibold text-text-muted uppercase tracking-wide mb-2 flex items-center gap-2">
              <GameIcon />
              Installed Games ({installedGames.length})
            </h3>
            {installedGames.length === 0 ? (
              <div className="bg-surface-elevated rounded-lg p-4 text-center">
                <p className="text-sm text-text-muted">
                  {sut.status === 'online' ? 'No games found' : 'SUT offline - cannot fetch games'}
                </p>
              </div>
            ) : (
              <div className="bg-surface-elevated rounded-lg divide-y divide-border max-h-64 overflow-y-auto">
                {installedGames.map((game, index) => (
                  <div key={index} className="px-3 py-2 flex items-center justify-between hover:bg-surface-hover transition-colors">
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium text-text-primary truncate" title={game.name}>
                        {game.name}
                      </p>
                      {game.steam_app_id && (
                        <p className="text-xs text-text-muted">Steam ID: {game.steam_app_id}</p>
                      )}
                    </div>
                    {game.exists !== false && (
                      <span className="ml-2 text-success text-xs">Installed</span>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Stats */}
        <div>
          <h3 className="text-xs font-semibold text-text-muted uppercase tracking-wide mb-2">
            Statistics
          </h3>
          <div className="grid grid-cols-2 gap-2">
            <div className="bg-surface-elevated rounded-lg p-3 text-center">
              <p className="text-2xl font-bold text-text-primary">{sut.success_rate.toFixed(0)}%</p>
              <p className="text-xs text-text-muted">Success Rate</p>
            </div>
            <div className="bg-surface-elevated rounded-lg p-3 text-center">
              <p className="text-2xl font-bold text-text-primary">{sut.error_count}</p>
              <p className="text-xs text-text-muted">Errors</p>
            </div>
          </div>
        </div>

        {/* Timestamps */}
        <div className="text-xs text-text-muted space-y-1">
          {sut.first_discovered && (
            <p>First discovered: {new Date(sut.first_discovered).toLocaleString()}</p>
          )}
          {sut.last_seen && (
            <p>Last seen: {new Date(sut.last_seen).toLocaleString()}</p>
          )}
          {sut.paired_at && (
            <p>Paired: {new Date(sut.paired_at).toLocaleString()} by {sut.paired_by || 'user'}</p>
          )}
          {sut.master_key_installed_at && (
            <p>SSH key installed: {new Date(sut.master_key_installed_at).toLocaleString()}</p>
          )}
          {sut.last_ip_change && (
            <p className="text-warning">IP changed: {new Date(sut.last_ip_change).toLocaleString()}</p>
          )}
        </div>
      </div>
    </div>
  );
}
