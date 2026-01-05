/**
 * PreflightChecks Component
 * Validation checklist before starting automation
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import type { SUT } from '../types';
import type { QualityLevel, Resolution } from './PresetMatrix';

export type CheckStatus = 'pending' | 'checking' | 'passed' | 'failed' | 'warning' | 'skipped';

export interface PreflightCheck {
  id: string;
  label: string;
  status: CheckStatus;
  message?: string;
  details?: string;
}

interface PreflightChecksProps {
  sut: SUT | null;
  gameName: string | null;
  gameSlug: string | null;
  quality: QualityLevel | null;
  resolution: Resolution | null;
  onAllChecksPassed?: (passed: boolean) => void;
  autoRun?: boolean;
}

const STATUS_ICONS: Record<CheckStatus, { icon: string; color: string }> = {
  pending: { icon: '○', color: 'text-gray-400' },
  checking: { icon: '◐', color: 'text-blue-500 animate-pulse' },
  passed: { icon: '✓', color: 'text-green-500' },
  failed: { icon: '✗', color: 'text-red-500' },
  warning: { icon: '⚠', color: 'text-yellow-500' },
  skipped: { icon: '–', color: 'text-gray-400' },
};

const INITIAL_CHECKS: Omit<PreflightCheck, 'status'>[] = [
  { id: 'sut_selected', label: 'SUT selected' },
  { id: 'sut_online', label: 'SUT is online and responding' },
  { id: 'game_selected', label: 'Game selected' },
  { id: 'game_installed', label: 'Game is installed on SUT' },
  { id: 'preset_selected', label: 'Preset quality and resolution selected' },
  { id: 'preset_available', label: 'Preset exists for selected configuration' },
  { id: 'omniparser_healthy', label: 'OmniParser service is available' },
];

export function PreflightChecks({
  sut,
  gameName,
  gameSlug,
  quality,
  resolution,
  onAllChecksPassed,
  autoRun = true,
}: PreflightChecksProps) {
  const [checks, setChecks] = useState<PreflightCheck[]>(
    INITIAL_CHECKS.map((c) => ({ ...c, status: 'pending' }))
  );
  const [isRunning, setIsRunning] = useState(false);

  // Use refs to avoid infinite loops from callback dependencies
  const onAllChecksPassedRef = useRef(onAllChecksPassed);
  const isRunningRef = useRef(false);
  const qualityRef = useRef(quality);
  const resolutionRef = useRef(resolution);
  const gameSlugRef = useRef(gameSlug);

  // Keep refs updated
  useEffect(() => {
    onAllChecksPassedRef.current = onAllChecksPassed;
  }, [onAllChecksPassed]);

  useEffect(() => {
    qualityRef.current = quality;
    resolutionRef.current = resolution;
  }, [quality, resolution]);

  useEffect(() => {
    gameSlugRef.current = gameSlug;
  }, [gameSlug]);

  const updateCheck = useCallback((id: string, updates: Partial<PreflightCheck>) => {
    setChecks((prev) =>
      prev.map((check) => (check.id === id ? { ...check, ...updates } : check))
    );
  }, []);

  const runChecks = useCallback(async () => {
    // Prevent concurrent runs
    if (isRunningRef.current) return;
    isRunningRef.current = true;
    setIsRunning(true);

    // Reset all checks to pending
    setChecks(INITIAL_CHECKS.map((c) => ({ ...c, status: 'pending' })));

    // Check 1: SUT selected
    updateCheck('sut_selected', { status: 'checking' });
    await delay(200);
    if (!sut) {
      updateCheck('sut_selected', { status: 'failed', message: 'No SUT selected' });
      setIsRunning(false);
      onAllChecksPassed?.(false);
      return;
    }
    updateCheck('sut_selected', {
      status: 'passed',
      message: `${sut.hostname || sut.ip}:${sut.port}`,
    });

    // Check 2: SUT online
    updateCheck('sut_online', { status: 'checking' });
    await delay(300);
    if (sut.status !== 'online') {
      updateCheck('sut_online', {
        status: 'failed',
        message: `SUT status: ${sut.status}`,
      });
      setIsRunning(false);
      onAllChecksPassed?.(false);
      return;
    }
    updateCheck('sut_online', { status: 'passed', message: 'SUT is responding' });

    // Check 3: Game selected - use ref for current gameSlug
    updateCheck('game_selected', { status: 'checking' });
    await delay(200);
    const currentGameSlug = gameSlugRef.current;
    if (!gameName || !currentGameSlug) {
      updateCheck('game_selected', { status: 'failed', message: 'No game selected' });
      setIsRunning(false);
      onAllChecksPassedRef.current?.(false);
      return;
    }
    updateCheck('game_selected', { status: 'passed', message: gameName });

    // Check 4: Game installed on SUT
    updateCheck('game_installed', { status: 'checking' });
    await delay(400);
    try {
      const response = await fetch(
        `/preset-api/api/sync/sut-games/${encodeURIComponent(sut.ip)}?port=${sut.port}`
      );
      if (response.ok) {
        const data = await response.json();
        const installedGame = data.games?.find(
          (g: { preset_short_name: string | null }) => g.preset_short_name === currentGameSlug
        );
        if (installedGame) {
          updateCheck('game_installed', {
            status: 'passed',
            message: `Found at ${installedGame.install_path || 'Steam'}`,
          });
        } else {
          updateCheck('game_installed', {
            status: 'warning',
            message: 'Game not found in installed games list',
            details: 'Game may still be available if manually installed',
          });
        }
      } else {
        updateCheck('game_installed', {
          status: 'warning',
          message: 'Could not verify installation',
        });
      }
    } catch {
      updateCheck('game_installed', {
        status: 'warning',
        message: 'Could not check SUT (preset-manager unavailable)',
      });
    }

    // Check 5: Preset selected - use refs for current values
    updateCheck('preset_selected', { status: 'checking' });
    await delay(200);
    const currentQuality = qualityRef.current;
    const currentResolution = resolutionRef.current;
    if (!currentQuality || !currentResolution) {
      updateCheck('preset_selected', {
        status: 'failed',
        message: 'Select quality and resolution',
      });
      setIsRunning(false);
      onAllChecksPassedRef.current?.(false);
      return;
    }
    updateCheck('preset_selected', {
      status: 'passed',
      message: `${currentQuality} @ ${currentResolution}`,
    });

    // Check 6: Preset available
    updateCheck('preset_available', { status: 'checking' });
    await delay(300);
    try {
      const response = await fetch(
        `/preset-api/api/presets/${encodeURIComponent(currentGameSlug)}/${currentQuality}/${currentResolution}/metadata`
      );
      if (response.ok) {
        const data = await response.json();
        const fileCount = data.files?.length || 0;
        if (data.status === 'placeholder' || fileCount === 0) {
          updateCheck('preset_available', {
            status: 'failed',
            message: fileCount === 0 ? 'No config files in preset' : 'Preset is a placeholder',
          });
        } else {
          updateCheck('preset_available', {
            status: 'passed',
            message: `${fileCount} config file${fileCount > 1 ? 's' : ''}`,
          });
        }
      } else if (response.status === 404) {
        updateCheck('preset_available', {
          status: 'failed',
          message: 'Preset not found',
        });
        setIsRunning(false);
        onAllChecksPassedRef.current?.(false);
        return;
      } else {
        updateCheck('preset_available', {
          status: 'warning',
          message: 'Could not verify preset',
        });
      }
    } catch {
      updateCheck('preset_available', {
        status: 'warning',
        message: 'Could not check preset (preset-manager unavailable)',
      });
    }

    // Check 7: OmniParser healthy
    updateCheck('omniparser_healthy', { status: 'checking' });
    await delay(300);
    try {
      const response = await fetch('/queue-api/probe');
      if (response.ok) {
        const data = await response.json();
        // Check overall_omniparser_status or stats.worker_running
        const isHealthy = data.overall_omniparser_status === 'healthy' || data.stats?.worker_running;
        const healthyCount = data.omniparser_healthy_count || 0;
        const totalCount = data.omniparser_total_count || 0;
        const queueSize = data.stats?.current_queue_size || 0;

        if (isHealthy) {
          updateCheck('omniparser_healthy', {
            status: 'passed',
            message: `${healthyCount}/${totalCount} servers, Queue: ${queueSize}`,
          });
        } else {
          updateCheck('omniparser_healthy', {
            status: 'warning',
            message: `OmniParser: ${data.overall_omniparser_status || 'unknown'}`,
          });
        }
      } else {
        updateCheck('omniparser_healthy', {
          status: 'warning',
          message: 'Queue service responding but status unknown',
        });
      }
    } catch {
      updateCheck('omniparser_healthy', {
        status: 'failed',
        message: 'Queue service unavailable',
      });
    }

    isRunningRef.current = false;
    setIsRunning(false);

    // Check if all passed (no failures)
    setChecks((current) => {
      const anyFailed = current.some((c) => c.status === 'failed');
      onAllChecksPassedRef.current?.(!anyFailed);
      return current;
    });
  }, [sut, gameName, updateCheck]);

  // Separate function to only run preset-related checks (5 & 6)
  const runPresetChecks = useCallback(async () => {
    const currentQuality = qualityRef.current;
    const currentResolution = resolutionRef.current;
    const currentGameSlug = gameSlugRef.current;

    // Check 5: Preset selected
    updateCheck('preset_selected', { status: 'checking' });
    await delay(100);
    if (!currentQuality || !currentResolution) {
      updateCheck('preset_selected', {
        status: 'failed',
        message: 'Select quality and resolution',
      });
      setChecks((current) => {
        const anyFailed = current.some((c) => c.status === 'failed');
        onAllChecksPassedRef.current?.(!anyFailed);
        return current;
      });
      return;
    }
    updateCheck('preset_selected', {
      status: 'passed',
      message: `${currentQuality} @ ${currentResolution}`,
    });

    // Check 6: Preset available
    updateCheck('preset_available', { status: 'checking' });
    await delay(100);
    if (currentGameSlug) {
      try {
        const response = await fetch(
          `/preset-api/api/presets/${encodeURIComponent(currentGameSlug)}/${currentQuality}/${currentResolution}/metadata`
        );
        if (response.ok) {
          const data = await response.json();
          const fileCount = data.files?.length || 0;
          if (data.status === 'placeholder' || fileCount === 0) {
            updateCheck('preset_available', {
              status: 'failed',
              message: fileCount === 0 ? 'No config files in preset' : 'Preset is a placeholder',
            });
          } else {
            updateCheck('preset_available', {
              status: 'passed',
              message: `${fileCount} config file${fileCount > 1 ? 's' : ''}`,
            });
          }
        } else if (response.status === 404) {
          updateCheck('preset_available', {
            status: 'failed',
            message: 'Preset not found',
          });
        } else {
          updateCheck('preset_available', {
            status: 'warning',
            message: 'Could not verify preset',
          });
        }
      } catch {
        updateCheck('preset_available', {
          status: 'warning',
          message: 'Could not check preset',
        });
      }
    }

    // Update overall status
    setChecks((current) => {
      const anyFailed = current.some((c) => c.status === 'failed');
      onAllChecksPassedRef.current?.(!anyFailed);
      return current;
    });
  }, [updateCheck]);

  // Key for SUT/game changes (runs full checks)
  const sutGameKey = sut?.device_id
    ? `${sut.device_id}-${gameSlug || ''}`
    : '';

  // Key for preset changes (runs only checks 5-6)
  const presetKey = `${quality || ''}-${resolution || ''}`;

  // Track if initial checks have run
  const initialChecksRanRef = useRef(false);

  // Run full checks when SUT or game changes
  useEffect(() => {
    if (autoRun && sutGameKey) {
      initialChecksRanRef.current = false;
      const timer = setTimeout(() => {
        runChecks();
        initialChecksRanRef.current = true;
      }, 500);
      return () => clearTimeout(timer);
    }
  }, [sutGameKey, autoRun]); // eslint-disable-line react-hooks/exhaustive-deps

  // Run only preset checks when quality/resolution changes (after initial checks)
  useEffect(() => {
    if (autoRun && initialChecksRanRef.current && presetKey) {
      const timer = setTimeout(() => {
        runPresetChecks();
      }, 200);
      return () => clearTimeout(timer);
    }
  }, [presetKey, autoRun]); // eslint-disable-line react-hooks/exhaustive-deps

  const passedCount = checks.filter((c) => c.status === 'passed').length;
  const failedCount = checks.filter((c) => c.status === 'failed').length;
  const warningCount = checks.filter((c) => c.status === 'warning').length;

  return (
    <div className="rounded-lg border border-gray-200 bg-white">
      <div className="border-b border-gray-200 px-4 py-3">
        <div className="flex items-center justify-between">
          <h3 className="font-semibold text-gray-900">Pre-flight Checks</h3>
          <div className="flex items-center gap-3">
            <div className="flex gap-2 text-xs">
              <span className="text-green-600">{passedCount} passed</span>
              {warningCount > 0 && <span className="text-yellow-600">{warningCount} warnings</span>}
              {failedCount > 0 && <span className="text-red-600">{failedCount} failed</span>}
            </div>
            <button
              onClick={runChecks}
              disabled={isRunning}
              className="rounded bg-gray-100 px-3 py-1 text-sm font-medium text-gray-700 hover:bg-gray-200 disabled:opacity-50"
            >
              {isRunning ? 'Checking...' : 'Re-run'}
            </button>
          </div>
        </div>
      </div>

      <div className="divide-y divide-gray-100">
        {checks.map((check) => {
          const statusInfo = STATUS_ICONS[check.status];
          return (
            <div key={check.id} className="flex items-start gap-2 px-3 py-2 overflow-hidden">
              <span className={`mt-0.5 flex-shrink-0 ${statusInfo.color}`}>{statusInfo.icon}</span>
              <div className="flex-1 min-w-0">
                <div className="text-sm text-gray-900">{check.label}</div>
                {check.message && (
                  <div
                    className={`text-xs truncate ${
                      check.status === 'passed'
                        ? 'text-green-600'
                        : check.status === 'failed'
                        ? 'text-red-600'
                        : check.status === 'warning'
                        ? 'text-yellow-600'
                        : 'text-gray-500'
                    }`}
                    title={check.message}
                  >
                    {check.message}
                  </div>
                )}
                {check.details && (
                  <div className="mt-0.5 text-xs text-gray-500">{check.details}</div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Summary Bar */}
      <div className="border-t border-gray-200 px-4 py-3">
        {failedCount > 0 ? (
          <div className="flex items-center gap-2 text-sm text-red-600">
            <svg className="h-4 w-4" fill="currentColor" viewBox="0 0 20 20">
              <path
                fillRule="evenodd"
                d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
                clipRule="evenodd"
              />
            </svg>
            <span>Cannot start automation — fix failed checks above</span>
          </div>
        ) : warningCount > 0 ? (
          <div className="flex items-center gap-2 text-sm text-yellow-600">
            <svg className="h-4 w-4" fill="currentColor" viewBox="0 0 20 20">
              <path
                fillRule="evenodd"
                d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z"
                clipRule="evenodd"
              />
            </svg>
            <span>Ready with warnings — automation may encounter issues</span>
          </div>
        ) : passedCount === checks.length ? (
          <div className="flex items-center gap-2 text-sm text-green-600">
            <svg className="h-4 w-4" fill="currentColor" viewBox="0 0 20 20">
              <path
                fillRule="evenodd"
                d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                clipRule="evenodd"
              />
            </svg>
            <span>All checks passed — ready to start automation</span>
          </div>
        ) : (
          <div className="flex items-center gap-2 text-sm text-gray-500">
            <svg className="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
              />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
              />
            </svg>
            <span>Running checks...</span>
          </div>
        )}
      </div>
    </div>
  );
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Compact inline check indicator
 */
interface CheckIndicatorProps {
  status: CheckStatus;
  label?: string;
}

export function CheckIndicator({ status, label }: CheckIndicatorProps) {
  const info = STATUS_ICONS[status];
  return (
    <span className={`inline-flex items-center gap-1 ${info.color}`}>
      <span>{info.icon}</span>
      {label && <span className="text-xs">{label}</span>}
    </span>
  );
}
