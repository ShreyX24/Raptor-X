/**
 * QuickLaunchPanel - Main launch control for dashboard
 * Simplified preset selection with 2 rows: Resolution + Quality
 * Supports both single runs and campaign runs (multi-game)
 */

import { useState, useMemo, useEffect, useCallback } from 'react';
import { startRun, checkGameAvailability, getSutResolutions, createCampaign, getSutSystemInfoByIp, type SUTSystemInfo } from '../api';
import { getPresetMatrix, type PresetMatrixResponse } from '../api/presetManager';
import type { SUT, GameConfig, SutDisplayResolution } from '../types';

interface QuickLaunchPanelProps {
  devices: SUT[];
  games: GameConfig[];
  selectedSutId?: string;
  selectedGameNames?: string[];  // Changed to array for multi-select
  onSelectSut?: (sut: SUT | null) => void;
  onRunStarted?: (runId: string) => void;
  onCampaignStarted?: (campaignId: string) => void;
  className?: string;
  compact?: boolean;  // Compact horizontal mode
}

type LaunchState = 'idle' | 'checking' | 'ready' | 'launching' | 'error';

// Resolution and Quality options
const RESOLUTIONS = ['720p', '1080p', '1440p', '2160p'] as const;
const QUALITY_LEVELS = ['low', 'medium', 'high', 'ultra'] as const;
type Resolution = typeof RESOLUTIONS[number];
type QualityLevel = typeof QUALITY_LEVELS[number];

const RESOLUTION_LABELS: Record<Resolution, string> = {
  '720p': '720p',
  '1080p': '1080p',
  '1440p': '2K',
  '2160p': '4K',
};

const RESOLUTION_INFO: Record<Resolution, { width: number; height: number }> = {
  '720p': { width: 1280, height: 720 },
  '1080p': { width: 1920, height: 1080 },
  '1440p': { width: 2560, height: 1440 },
  '2160p': { width: 3840, height: 2160 },
};

// Short form game name abbreviations
const GAME_ABBREVIATIONS: Record<string, string> = {
  'ac-mirage': 'AC-M',
  'assassins-creed-mirage': 'AC-M',
  'black-myth-wukong': 'BMW',
  'cyberpunk-2077': 'CP77',
  'counter-strike-2': 'CS2',
  'f1-24': 'F124',
  'far-cry-6': 'FC6',
  'final-fantasy-xiv-dawntrail': 'FF14',
  'hitman-3': 'HM3',
  'hitman-3-dubai': 'HM3',
  'horizon-zero-dawn-remastered': 'HZD',
  'red-dead-redemption-2': 'RDR2',
  'shadow-of-the-tomb-raider': 'SOTR',
  'sid-meier-civ-6': 'CIV6',
  'tiny-tina-wonderlands': 'TTW',
  'dota-2': 'Dota2',
};

function getGameShortName(game: GameConfig): string {
  // Try preset_id first, then name
  if (game.preset_id && GAME_ABBREVIATIONS[game.preset_id]) {
    return GAME_ABBREVIATIONS[game.preset_id];
  }
  if (GAME_ABBREVIATIONS[game.name]) {
    return GAME_ABBREVIATIONS[game.name];
  }
  // Fallback: First letters of each word, max 4 chars
  const words = (game.display_name || game.name).split(/[\s-]+/);
  if (words.length >= 2) {
    return words.map(w => w[0]?.toUpperCase()).join('').slice(0, 4);
  }
  return (game.display_name || game.name).slice(0, 4).toUpperCase();
}

// Games that actually have presets in preset-manager/configs/presets
const GAMES_WITH_PRESETS = new Set([
  'assassins-creed-mirage',
  'black-myth-wukong',
  'cyberpunk-2077',
  'f1-24',
  'far-cry-6',
  'final-fantasy-xiv-dawntrail',
  'hitman-3-dubai',
  'horizon-zero-dawn-remastered',
  'red-dead-redemption-2',
  'shadow-of-tomb-raider',
  'sid-meier-civ-6',
  'tiny-tina-wonderlands',
]);

function gameHasPreset(game: GameConfig): boolean {
  return game.preset_id ? GAMES_WITH_PRESETS.has(game.preset_id) : false;
}

// Filter out virtual GPUs - only show NVIDIA, AMD, or Intel
function getDisplayGpu(gpuName: string): string {
  const lower = gpuName.toLowerCase();
  // Check for virtual/meta GPUs
  if (lower.includes('virtual') || lower.includes('meta') || lower.includes('basic') || lower.includes('microsoft')) {
    return 'Virtual (no GPU)';
  }
  // Clean up the name
  return gpuName
    .replace('NVIDIA ', '')
    .replace('AMD ', '')
    .replace('GeForce ', '')
    .replace('Radeon ', '');
}

// Round RAM to nearest even number (31.2 → 32, 15.8 → 16)
function roundRamToEven(gb: number): number {
  const rounded = Math.round(gb);
  // If odd, round up to next even
  return rounded % 2 === 0 ? rounded : rounded + 1;
}

// Get max supported resolution from SUT resolutions
function getMaxResolution(resolutions: SutDisplayResolution[]): SutDisplayResolution | null {
  if (resolutions.length === 0) return null;
  return resolutions.reduce((max, res) =>
    (res.width * res.height > max.width * max.height) ? res : max
  );
}

export function QuickLaunchPanel({
  devices,
  games,
  selectedSutId,
  selectedGameNames = [],
  onSelectSut,
  onRunStarted,
  onCampaignStarted,
  className = '',
  compact = false,
}: QuickLaunchPanelProps) {
  // Selection state
  const [localSutId, setLocalSutId] = useState<string | undefined>(selectedSutId);
  const [localGameNames, setLocalGameNames] = useState<string[]>(selectedGameNames);

  // Preset selection - simplified to separate dropdowns
  const [selectedQuality, setSelectedQuality] = useState<QualityLevel | null>(null);
  const [selectedResolution, setSelectedResolution] = useState<Resolution | null>(null);
  const [iterations, setIterations] = useState(1);
  const [skipSteamLogin, setSkipSteamLogin] = useState(false);  // Manual login mode

  // Status
  const [launchState, setLaunchState] = useState<LaunchState>('idle');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [gameAvailable, setGameAvailable] = useState<boolean | null>(null);

  // Preset matrix for availability
  const [presetMatrix, setPresetMatrix] = useState<PresetMatrixResponse | null>(null);
  const [loadingPresets, setLoadingPresets] = useState(false);

  // SUT resolutions
  const [sutResolutions, setSutResolutions] = useState<SutDisplayResolution[]>([]);

  // SUT system info
  const [sutSystemInfo, setSutSystemInfo] = useState<SUTSystemInfo | null>(null);
  const [loadingSutInfo, setLoadingSutInfo] = useState(false);

  // Sync with parent selections
  useEffect(() => {
    if (selectedSutId !== undefined) setLocalSutId(selectedSutId);
  }, [selectedSutId]);

  useEffect(() => {
    if (selectedGameNames.length > 0) {
      setLocalGameNames(selectedGameNames);
      // Set default iterations based on selection type
      setIterations(selectedGameNames.length > 1 ? 3 : 1);
    }
  }, [selectedGameNames]);

  // Get selected SUT and game objects
  const selectedSut = useMemo(() =>
    devices.find(d => d.device_id === localSutId),
    [devices, localSutId]
  );

  const selectedGames = useMemo(() =>
    games.filter(g => localGameNames.includes(g.name)),
    [games, localGameNames]
  );

  const isCampaign = selectedGames.length > 1;
  const firstSelectedGame = selectedGames[0];

  // Online devices only
  const onlineDevices = useMemo(() =>
    devices.filter(d => d.status === 'online'),
    [devices]
  );

  // Check game availability when SUT or game changes
  useEffect(() => {
    if (!selectedSut || !firstSelectedGame) {
      setGameAvailable(null);
      return;
    }

    const checkAvailability = async () => {
      setLaunchState('checking');
      try {
        const result = await checkGameAvailability(firstSelectedGame.name, selectedSut.ip);
        setGameAvailable(result.available);
        setLaunchState(result.available ? 'ready' : 'idle');
        setErrorMessage(result.available ? null : 'Game not installed on SUT');
      } catch (error) {
        console.error('Failed to check game availability:', error);
        setGameAvailable(null);
        setLaunchState('error');
        setErrorMessage('Failed to check game availability');
      }
    };

    checkAvailability();
  }, [selectedSut?.ip, firstSelectedGame?.name]);

  // Fetch SUT resolutions when SUT changes
  useEffect(() => {
    if (!selectedSut) {
      setSutResolutions([]);
      return;
    }

    const fetchResolutions = async () => {
      try {
        const response = await getSutResolutions(selectedSut.device_id);
        setSutResolutions(response.resolutions || []);
      } catch (error) {
        console.error('Failed to fetch SUT resolutions:', error);
        setSutResolutions([]);
      }
    };

    fetchResolutions();
  }, [selectedSut?.device_id]);

  // Fetch SUT system info when SUT changes - use backend proxy (CORS-safe)
  useEffect(() => {
    if (!selectedSut) {
      setSutSystemInfo(null);
      return;
    }

    const fetchSystemInfo = async () => {
      setLoadingSutInfo(true);
      try {
        // Use backend proxy - handles CORS and unwraps response
        const systemInfo = await getSutSystemInfoByIp(selectedSut.ip);
        setSutSystemInfo(systemInfo);
      } catch (error) {
        console.error('Failed to fetch SUT system info:', error);
        setSutSystemInfo(null);
      } finally {
        setLoadingSutInfo(false);
      }
    };

    fetchSystemInfo();
  }, [selectedSut?.ip]);

  // Fetch preset matrix when game changes
  useEffect(() => {
    if (!firstSelectedGame?.preset_id) {
      setPresetMatrix(null);
      return;
    }

    const fetchMatrix = async () => {
      setLoadingPresets(true);
      try {
        const matrix = await getPresetMatrix(firstSelectedGame.preset_id!);
        setPresetMatrix(matrix);

        // Auto-select defaults if available
        if (matrix.default_quality && matrix.default_resolution) {
          const q = matrix.default_quality as QualityLevel;
          const r = matrix.default_resolution as Resolution;
          if (matrix.available_presets[q]?.includes(r)) {
            setSelectedQuality(q);
            setSelectedResolution(r);
          }
        }
      } catch (error) {
        console.error('Failed to fetch preset matrix:', error);
        setPresetMatrix(null);
      } finally {
        setLoadingPresets(false);
      }
    };

    fetchMatrix();
  }, [firstSelectedGame?.preset_id]);

  // Check if resolution is supported by SUT
  const isSutSupported = useCallback((res: Resolution) => {
    if (sutResolutions.length === 0) return true;
    const info = RESOLUTION_INFO[res];
    return sutResolutions.some(sr => sr.width === info.width && sr.height === info.height);
  }, [sutResolutions]);

  // Check if quality has any presets available
  // If no preset matrix yet but game has preset_id, enable all qualities as fallback
  const isQualityAvailable = useCallback((quality: QualityLevel) => {
    // If still loading and game has preset, allow all qualities
    if (loadingPresets && firstSelectedGame?.preset_id) return true;
    // If no preset matrix, enable all qualities as fallback (let backend validate)
    if (!presetMatrix) return !!firstSelectedGame?.preset_id;
    const resolutions = presetMatrix.available_presets[quality];
    return resolutions && resolutions.length > 0;
  }, [presetMatrix, loadingPresets, firstSelectedGame?.preset_id]);

  // Check if resolution has presets for selected quality (used for highlighting)
  const _isResolutionAvailable = useCallback((res: Resolution) => {
    if (!presetMatrix || !selectedQuality) return false;
    const resolutions = presetMatrix.available_presets[selectedQuality];
    return resolutions?.includes(res) && isSutSupported(res);
  }, [presetMatrix, selectedQuality, isSutSupported]);
  void _isResolutionAvailable; // Suppress unused warning for future use

  // Handle SUT selection
  const handleSutChange = (deviceId: string) => {
    setLocalSutId(deviceId);
    const sut = devices.find(d => d.device_id === deviceId);
    onSelectSut?.(sut || null);
    // Reset selections
    setSelectedQuality(null);
    setSelectedResolution(null);
  };

  // Handle launch
  const handleLaunch = async () => {
    if (!selectedSut || selectedGames.length === 0) return;

    setLaunchState('launching');
    setErrorMessage(null);

    try {
      if (isCampaign) {
        // Campaign run (multiple games)
        const result = await createCampaign(
          selectedSut.ip,
          selectedGames.map(g => g.name),
          iterations,
          undefined, // auto-generate name
          selectedQuality || undefined,
          selectedResolution || undefined,
          skipSteamLogin
        );
        setLaunchState('idle');
        onCampaignStarted?.(result.campaign_id);
      } else {
        // Single run
        const result = await startRun(
          selectedSut.ip,
          selectedGames[0].name,
          iterations,
          selectedQuality || undefined,
          selectedResolution || undefined,
          skipSteamLogin
        );
        setLaunchState('idle');
        onRunStarted?.(result.run_id);
      }

      // Reset for next run
      setIterations(1);
    } catch (error) {
      console.error('Failed to start run:', error);
      setLaunchState('error');
      setErrorMessage(error instanceof Error ? error.message : 'Failed to start run');
    }
  };

  // Determine if launch is possible
  const isReady = launchState === 'ready';
  const isLaunching = launchState === 'launching';
  const canLaunch = isReady &&
    selectedSut &&
    selectedGames.length > 0 &&
    (isCampaign || gameAvailable === true) &&
    iterations > 0;

  // Compact mode - horizontal layout with system info and preflight
  if (compact) {
    return (
      <div className={`bg-surface border border-border rounded-lg p-3 h-full flex flex-col ${className}`}>
        {/* Row 1: Game selection + Preset + Iterations + Launch */}
        <div className="flex items-start gap-4 flex-1">
          {/* Selected Games Display */}
          <div className="flex-1 min-w-0">
            <div className="text-[10px] text-text-muted uppercase mb-1">
              {isCampaign ? `Campaign (${selectedGames.length} games)` : 'Game'}
            </div>
            <div className="px-3 py-2 text-sm bg-surface-elevated rounded border border-border min-h-[36px] max-h-[60px] overflow-y-auto">
              {selectedGames.length === 0 ? (
                <span className="text-text-muted">Select from library below</span>
              ) : selectedGames.length === 1 ? (
                <span className="text-text-primary font-medium">{selectedGames[0].display_name || selectedGames[0].name}</span>
              ) : (
                <div className="flex flex-wrap gap-1.5">
                  {selectedGames.map((g) => (
                    <span
                      key={g.name}
                      className={`px-2 py-0.5 text-xs font-medium rounded ${
                        gameHasPreset(g)
                          ? 'bg-primary/20 text-primary'
                          : 'bg-warning/20 text-warning'
                      }`}
                      title={g.display_name || g.name}
                    >
                      {getGameShortName(g)}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Preset selectors - only if game has presets */}
          {firstSelectedGame?.preset_id && (
            <>
              <div className="w-24 flex-shrink-0">
                <div className="text-[10px] text-text-muted uppercase mb-1">Quality</div>
                <select
                  value={selectedQuality || ''}
                  onChange={(e) => setSelectedQuality(e.target.value as QualityLevel || null)}
                  className="w-full px-2 py-1.5 text-sm bg-surface-elevated border border-border rounded"
                >
                  <option value="">Select</option>
                  {QUALITY_LEVELS.map(q => (
                    <option key={q} value={q} disabled={!isQualityAvailable(q)}>{q}</option>
                  ))}
                </select>
              </div>

              <div className="w-20 flex-shrink-0">
                <div className="text-[10px] text-text-muted uppercase mb-1">Resolution</div>
                <select
                  value={selectedResolution || ''}
                  onChange={(e) => setSelectedResolution(e.target.value as Resolution || null)}
                  className="w-full px-2 py-1.5 text-sm bg-surface-elevated border border-border rounded"
                >
                  <option value="">Select</option>
                  {RESOLUTIONS.map(r => (
                    <option key={r} value={r} disabled={!isSutSupported(r)}>{RESOLUTION_LABELS[r]}</option>
                  ))}
                </select>
              </div>
            </>
          )}

          {/* Iterations */}
          <div className="w-16 flex-shrink-0">
            <div className="text-[10px] text-text-muted uppercase mb-1">Iterations</div>
            <input
              type="number"
              min={1}
              max={100}
              value={iterations}
              onChange={(e) => setIterations(Math.max(1, parseInt(e.target.value) || 1))}
              className="w-full px-2 py-1.5 text-sm bg-surface-elevated border border-border rounded text-center"
            />
          </div>

          {/* Skip Steam Login toggle */}
          <div className="flex-shrink-0">
            <div className="text-[10px] text-text-muted uppercase mb-1">Steam</div>
            <label
              className={`flex items-center gap-1.5 px-2 py-1.5 rounded cursor-pointer transition-colors ${
                skipSteamLogin
                  ? 'bg-warning/20 border border-warning/50'
                  : 'bg-surface-elevated border border-border hover:border-border-hover'
              }`}
              title={skipSteamLogin ? 'Manual login: Steam account switching disabled' : 'Auto login: Will switch Steam accounts as needed'}
            >
              <input
                type="checkbox"
                checked={skipSteamLogin}
                onChange={(e) => setSkipSteamLogin(e.target.checked)}
                className="sr-only"
              />
              <span className={`text-xs font-medium ${skipSteamLogin ? 'text-warning' : 'text-text-secondary'}`}>
                {skipSteamLogin ? 'Manual' : 'Auto'}
              </span>
            </label>
          </div>

          {/* Launch button */}
          <div className="flex-shrink-0">
            <div className="text-[10px] text-transparent mb-1">.</div>
            <button
              onClick={handleLaunch}
              disabled={!canLaunch || isLaunching}
              className={`
                px-4 py-1.5 rounded text-xs font-medium transition-all
                ${canLaunch && !isLaunching
                  ? 'bg-primary hover:bg-primary-hover text-white'
                  : 'bg-surface-elevated text-text-muted cursor-not-allowed'
                }
              `}
            >
              {isLaunching ? '...' : isCampaign ? 'START CAMPAIGN' : 'START'}
            </button>
          </div>
        </div>

        {/* Row 2: System Info + Preflight - horizontal layout */}
        <div className="mt-auto pt-2 border-t border-border/50">
          <div className="flex items-center gap-6 text-xs">
            {/* SUT System Info */}
            {selectedSut ? (
              loadingSutInfo ? (
                <span className="text-text-muted animate-pulse">Loading...</span>
              ) : sutSystemInfo ? (
                <>
                  <div className="flex items-center gap-1.5">
                    <span className="text-text-muted">GPU:</span>
                    <span className="text-text-secondary font-medium truncate max-w-[160px]" title={sutSystemInfo.gpu.name}>
                      {getDisplayGpu(sutSystemInfo.gpu.name)}
                    </span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className="text-text-muted">RAM:</span>
                    <span className="text-text-secondary font-medium">{roundRamToEven(sutSystemInfo.ram.total_gb)}GB</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className="text-text-muted">Display:</span>
                    <span className="text-text-secondary font-medium">
                      {sutSystemInfo.screen.width}×{sutSystemInfo.screen.height}
                    </span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className="text-text-muted">Max:</span>
                    <span className="text-text-secondary font-medium">
                      {(() => {
                        const maxRes = getMaxResolution(sutResolutions);
                        return maxRes ? `${maxRes.width}×${maxRes.height}` : 'N/A';
                      })()}
                    </span>
                  </div>
                </>
              ) : (
                <span className="text-text-muted">No system info</span>
              )
            ) : (
              <span className="text-text-muted">Select a SUT</span>
            )}

            {/* Divider */}
            <div className="h-4 w-px bg-border" />

            {/* Horizontal Preflight Checks */}
            <HorizontalPreflightChecks
              sut={selectedSut}
              gameAvailable={gameAvailable}
              selectedGames={selectedGames}
              selectedQuality={selectedQuality}
              selectedResolution={selectedResolution}
              presetMatrix={presetMatrix}
            />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={`bg-surface border border-border rounded-lg overflow-hidden ${className}`}>
      {/* Header */}
      <div className="px-4 py-3 bg-surface-elevated/50 border-b border-border">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-text-primary">Quick Launch</h3>
          {isCampaign && (
            <span className="px-2 py-0.5 text-xs bg-primary/20 text-primary rounded font-medium">
              CAMPAIGN ({selectedGames.length} games)
            </span>
          )}
        </div>
      </div>

      <div className="p-4 space-y-4">
        {/* Row 1: SUT + Game selection */}
        <div className="grid grid-cols-2 gap-3">
          {/* SUT Dropdown */}
          <div>
            <label className="block text-xs font-medium text-text-muted mb-1">
              Target SUT
            </label>
            <select
              value={localSutId || ''}
              onChange={(e) => handleSutChange(e.target.value)}
              className="w-full px-3 py-2 text-sm bg-surface-elevated border border-border rounded-md
                focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary
                text-text-primary"
            >
              <option value="">Select SUT...</option>
              {onlineDevices.map((sut) => (
                <option key={sut.device_id} value={sut.device_id}>
                  {sut.hostname || sut.ip}
                  {sut.current_task && ' (busy)'}
                </option>
              ))}
            </select>
          </div>

          {/* Game Display (read-only, selected from library) - dynamic width */}
          <div className="flex-1">
            <label className="block text-xs font-medium text-text-muted mb-1">
              Game{selectedGames.length > 1 ? 's' : ''}
            </label>
            <div className="px-3 py-1.5 text-sm bg-surface-elevated border border-border rounded-md text-text-secondary min-h-[38px] max-h-[60px] overflow-y-auto">
              {selectedGames.length === 0 ? (
                <span className="text-text-muted italic">Select from library below</span>
              ) : selectedGames.length === 1 ? (
                <span>{selectedGames[0].display_name || selectedGames[0].name}</span>
              ) : (
                <div className="flex flex-wrap gap-1 items-center">
                  {selectedGames.map((g) => (
                    <span
                      key={g.name}
                      className={`px-1.5 py-0.5 text-[10px] font-medium rounded-full ${
                        gameHasPreset(g)
                          ? 'bg-primary/20 text-primary'
                          : 'bg-warning/20 text-warning'
                      }`}
                      title={`${g.display_name || g.name}${gameHasPreset(g) ? '' : ' (no preset)'}`}
                    >
                      {getGameShortName(g)}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* SUT System Info */}
        {selectedSut && (
          <div className="px-3 py-2 bg-surface-elevated/50 rounded-md border border-border/50">
            {loadingSutInfo ? (
              <div className="text-xs text-text-muted animate-pulse">Loading system info...</div>
            ) : sutSystemInfo ? (
              <div className="grid grid-cols-2 md:grid-cols-5 gap-x-4 gap-y-1 text-xs">
                <div className="flex items-center gap-1">
                  <span className="text-text-muted">OS:</span>
                  <span className="text-text-secondary font-medium">
                    {sutSystemInfo.os.name} {sutSystemInfo.os.build}
                  </span>
                </div>
                <div className="flex items-center gap-1">
                  <span className="text-text-muted">GPU:</span>
                  <span className="text-text-secondary font-medium truncate" title={sutSystemInfo.gpu.name}>
                    {getDisplayGpu(sutSystemInfo.gpu.name)}
                  </span>
                </div>
                <div className="flex items-center gap-1">
                  <span className="text-text-muted">RAM:</span>
                  <span className="text-text-secondary font-medium">{roundRamToEven(sutSystemInfo.ram.total_gb)}GB</span>
                </div>
                <div className="flex items-center gap-1">
                  <span className="text-text-muted">Current:</span>
                  <span className="text-text-secondary font-medium">
                    {sutSystemInfo.screen.width}×{sutSystemInfo.screen.height}
                  </span>
                </div>
                <div className="flex items-center gap-1">
                  <span className="text-text-muted">Max:</span>
                  <span className="text-text-secondary font-medium">
                    {(() => {
                      const maxRes = getMaxResolution(sutResolutions);
                      return maxRes ? `${maxRes.width}×${maxRes.height}` : 'N/A';
                    })()}
                  </span>
                </div>
              </div>
            ) : (
              <div className="text-xs text-text-muted">System info unavailable</div>
            )}
          </div>
        )}

        {/* Two-column layout: Left = Presets, Right = Pre-flight */}
        <div className="grid grid-cols-2 gap-4">
          {/* Left Column - Resolution & Quality */}
          <div className="space-y-3">
            {/* Resolution Selection */}
            {firstSelectedGame?.preset_id && (
              <div>
                <label className="block text-[10px] font-medium text-text-muted mb-1.5 uppercase tracking-wide">
                  Resolution
                </label>
                <div className="grid grid-cols-4 gap-1.5">
                  {RESOLUTIONS.map((res) => {
                    const sutSupported = isSutSupported(res);
                    // Check if ANY quality has this resolution, or if selected quality has it
                    const hasPresetForAnyQuality = presetMatrix
                      ? Object.values(presetMatrix.available_presets).some(resolutions => resolutions?.includes(res))
                      : true;
                    const hasPresetForSelectedQuality = selectedQuality && presetMatrix
                      ? presetMatrix.available_presets[selectedQuality]?.includes(res)
                      : hasPresetForAnyQuality;
                    const available = sutSupported;
                    const isSelected = selectedResolution === res;

                    return (
                      <button
                        key={res}
                        onClick={() => available && setSelectedResolution(res)}
                        disabled={!available}
                        className={`
                          py-2 px-2 text-sm font-medium rounded transition-all
                          ${isSelected
                            ? 'bg-primary text-white'
                            : available
                              ? hasPresetForSelectedQuality || !selectedQuality
                                ? 'bg-surface-elevated border border-border hover:border-primary text-text-secondary'
                                : 'bg-surface-elevated border border-warning/50 text-warning'
                              : 'bg-surface border border-border/30 text-text-muted/50 cursor-not-allowed'
                          }
                        `}
                        title={!sutSupported ? 'Not supported by SUT' : !hasPresetForSelectedQuality && selectedQuality ? 'No preset for selected quality' : ''}
                      >
                        {RESOLUTION_LABELS[res]}
                      </button>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Quality Selection */}
            {firstSelectedGame?.preset_id && (
              <div>
                <label className="block text-[10px] font-medium text-text-muted mb-1.5 uppercase tracking-wide">
                  Quality
                </label>
                <div className="grid grid-cols-4 gap-1.5">
                  {QUALITY_LEVELS.map((quality) => {
                    const available = isQualityAvailable(quality);
                    const hasResolutionPreset = selectedResolution && presetMatrix?.available_presets[quality]?.includes(selectedResolution);
                    const isSelected = selectedQuality === quality;

                    return (
                      <button
                        key={quality}
                        onClick={() => available && setSelectedQuality(quality)}
                        disabled={!available}
                        className={`
                          py-2 px-2 text-sm font-medium rounded transition-all capitalize
                          ${isSelected
                            ? 'bg-primary text-white'
                            : available
                              ? hasResolutionPreset || !selectedResolution
                                ? 'bg-surface-elevated border border-border hover:border-primary text-text-secondary'
                                : 'bg-surface-elevated border border-warning/50 text-warning'
                              : 'bg-surface border border-border/30 text-text-muted/50 cursor-not-allowed'
                          }
                        `}
                        title={!available ? 'No presets available' : !hasResolutionPreset && selectedResolution ? 'No preset for selected resolution' : ''}
                      >
                        {quality}
                      </button>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Selection summary */}
            {selectedQuality && selectedResolution && (
              <div className="text-xs text-text-muted flex items-center gap-2">
                <span className="text-primary capitalize font-medium">{selectedQuality}</span>
                <span>@</span>
                <span className="text-primary font-medium">{RESOLUTION_LABELS[selectedResolution]}</span>
                {presetMatrix?.available_presets[selectedQuality]?.includes(selectedResolution) ? (
                  <span className="text-success">✓ preset available</span>
                ) : (
                  <span className="text-warning">⚠ no preset for this combo</span>
                )}
              </div>
            )}
          </div>

          {/* Right Column - Pre-flight Checks */}
          <CompactPreflightChecks
            sut={selectedSut}
            gameAvailable={gameAvailable}
            selectedGames={selectedGames}
            selectedQuality={selectedQuality}
            selectedResolution={selectedResolution}
            presetMatrix={presetMatrix}
            isCampaign={isCampaign}
          />
        </div>

        {/* Iterations + Launch - Compact row */}
        <div className="flex items-center gap-3 pt-2 border-t border-border/50">
          {/* Iterations */}
          <div className="flex items-center gap-2">
            <label className="text-[10px] font-medium text-text-muted uppercase">Iter</label>
            <input
              type="number"
              min={1}
              max={100}
              value={iterations}
              onChange={(e) => setIterations(Math.max(1, parseInt(e.target.value) || 1))}
              className="w-14 px-2 py-1.5 text-xs bg-surface-elevated border border-border rounded
                focus:outline-none focus:border-primary text-text-primary font-numbers text-center"
            />
          </div>

          {/* Skip Steam Login toggle */}
          <label
            className={`flex items-center gap-2 px-3 py-1.5 rounded cursor-pointer transition-colors ${
              skipSteamLogin
                ? 'bg-warning/20 border border-warning/50'
                : 'bg-surface-elevated border border-border hover:border-border-hover'
            }`}
            title={skipSteamLogin ? 'Manual login: Steam account switching disabled. Pre-login to SUT required.' : 'Auto login: Will switch Steam accounts as needed'}
          >
            <input
              type="checkbox"
              checked={skipSteamLogin}
              onChange={(e) => setSkipSteamLogin(e.target.checked)}
              className="sr-only"
            />
            <span className="text-[10px] text-text-muted uppercase">Steam</span>
            <span className={`text-xs font-medium ${skipSteamLogin ? 'text-warning' : 'text-text-secondary'}`}>
              {skipSteamLogin ? 'Manual' : 'Auto'}
            </span>
          </label>

          {/* Launch Button */}
          <button
            onClick={handleLaunch}
            disabled={!canLaunch || isLaunching}
            className={`
              flex-1 py-2 px-4 rounded font-medium text-xs transition-all
              ${canLaunch && !isLaunching
                ? 'bg-primary hover:bg-primary-hover text-white shadow-md shadow-primary/25'
                : 'bg-surface-elevated text-text-muted cursor-not-allowed'
              }
            `}
          >
            {isLaunching ? (
              <span className="flex items-center justify-center gap-2">
                <svg className="animate-spin h-3 w-3" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                Starting...
              </span>
            ) : (
              <>{isCampaign ? `START CAMPAIGN (${selectedGames.length})` : 'START RUN'}</>
            )}
          </button>
        </div>

        {/* Error message */}
        {errorMessage && launchState === 'error' && (
          <div className="px-3 py-2 bg-danger/10 border border-danger/30 rounded text-xs text-danger">
            {errorMessage}
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * HorizontalPreflightChecks - Inline horizontal preflight checks
 */
interface HorizontalPreflightChecksProps {
  sut: SUT | null | undefined;
  gameAvailable: boolean | null;
  selectedGames: GameConfig[];
  selectedQuality: QualityLevel | null;
  selectedResolution: Resolution | null;
  presetMatrix: PresetMatrixResponse | null;
}

function HorizontalPreflightChecks({
  sut,
  gameAvailable,
  selectedGames,
  selectedQuality,
  selectedResolution,
  presetMatrix,
}: HorizontalPreflightChecksProps) {
  const [omniparserOnline, setOmniparserOnline] = useState<boolean | null>(null);

  useEffect(() => {
    const check = async () => {
      try {
        const response = await fetch('/queue-api/probe');
        if (response.ok) {
          const data = await response.json();
          setOmniparserOnline(data.overall_omniparser_status === 'healthy' || data.stats?.worker_running);
        } else {
          setOmniparserOnline(false);
        }
      } catch {
        setOmniparserOnline(false);
      }
    };
    check();
    const interval = setInterval(check, 30000);
    return () => clearInterval(interval);
  }, []);

  // Calculate statuses
  const sutOk = sut && sut.status === 'online';
  const gameOk = selectedGames.length > 0;
  const installedOk = gameAvailable === true;
  const presetOk = selectedQuality && selectedResolution &&
    presetMatrix?.available_presets[selectedQuality]?.includes(selectedResolution);

  const checks = [
    { label: 'SUT', ok: sutOk, pending: !sut },
    { label: 'Game', ok: gameOk, pending: false },
    { label: 'Installed', ok: installedOk, pending: gameAvailable === null && gameOk },
    { label: 'Preset', ok: !!presetOk, pending: !selectedQuality || !selectedResolution },
    { label: 'OmniParser', ok: omniparserOnline === true, pending: omniparserOnline === null },
  ];

  const passedCount = checks.filter(c => c.ok).length;
  const allPassed = passedCount === checks.length;

  return (
    <div className="flex items-center gap-4">
      {checks.map((check, i) => (
        <div key={i} className="flex items-center gap-1.5">
          <span
            className={`w-2 h-2 rounded-full flex-shrink-0 ${
              check.pending
                ? 'bg-text-muted/30'
                : check.ok
                  ? 'bg-success'
                  : 'bg-danger'
            }`}
          />
          <span className={`text-xs ${
            check.pending
              ? 'text-text-muted'
              : check.ok
                ? 'text-text-secondary'
                : 'text-danger'
          }`}>
            {check.label}
          </span>
        </div>
      ))}

      {/* Summary */}
      <span className={`text-xs font-medium ml-2 ${allPassed ? 'text-success' : 'text-text-muted'}`}>
        {allPassed ? '✓ Ready' : `${passedCount}/${checks.length}`}
      </span>
    </div>
  );
}

/**
 * CompactPreflightChecks - Inline pre-flight validation for Quick Launch
 */
interface CompactPreflightChecksProps {
  sut: SUT | null | undefined;
  gameAvailable: boolean | null;
  selectedGames: GameConfig[];
  selectedQuality: QualityLevel | null;
  selectedResolution: Resolution | null;
  presetMatrix: PresetMatrixResponse | null;
  isCampaign: boolean;
}

interface CheckItem {
  id: string;
  label: string;
  status: 'pass' | 'fail' | 'warn' | 'pending';
  message?: string;
}

function CompactPreflightChecks({
  sut,
  gameAvailable,
  selectedGames,
  selectedQuality,
  selectedResolution,
  presetMatrix,
  isCampaign,
}: CompactPreflightChecksProps) {
  const [omniparserStatus, setOmniparserStatus] = useState<'checking' | 'online' | 'offline'>('checking');

  // Check OmniParser status
  useEffect(() => {
    const checkOmniparser = async () => {
      try {
        const response = await fetch('/queue-api/probe');
        if (response.ok) {
          const data = await response.json();
          const isHealthy = data.overall_omniparser_status === 'healthy' || data.stats?.worker_running;
          setOmniparserStatus(isHealthy ? 'online' : 'offline');
        } else {
          setOmniparserStatus('offline');
        }
      } catch {
        setOmniparserStatus('offline');
      }
    };

    checkOmniparser();
    const interval = setInterval(checkOmniparser, 30000);
    return () => clearInterval(interval);
  }, []);

  // Calculate campaign-specific issues - use actual preset folder check
  const gamesWithoutPresets = isCampaign
    ? selectedGames.filter(g => !gameHasPreset(g)).map(g => g.display_name || g.name)
    : [];

  // Build checks list
  const checks: CheckItem[] = [
    {
      id: 'sut',
      label: 'SUT',
      status: sut ? (sut.status === 'online' ? 'pass' : 'warn') : 'fail',
      message: sut ? `${sut.hostname || sut.ip}` : 'Not selected',
    },
    {
      id: 'game',
      label: isCampaign ? 'Games' : 'Game',
      status: selectedGames.length > 0 ? 'pass' : 'fail',
      message: isCampaign ? `${selectedGames.length} selected` : (selectedGames[0]?.display_name || selectedGames[0]?.name || 'Not selected'),
    },
    {
      id: 'installed',
      label: 'Presets',
      status: isCampaign
        ? (gamesWithoutPresets.length > 0 ? 'warn' : 'pass')
        : (gameAvailable === true ? (gameHasPreset(selectedGames[0]) ? 'pass' : 'warn') : gameAvailable === false ? 'fail' : 'pending'),
      message: isCampaign
        ? (gamesWithoutPresets.length > 0
          ? `${gamesWithoutPresets.length} without presets`
          : 'All have presets')
        : (gameAvailable === true
          ? (gameHasPreset(selectedGames[0]) ? 'Available' : 'No preset files')
          : gameAvailable === false ? 'Not on SUT' : 'Checking...'),
    },
    {
      id: 'preset',
      label: 'Preset',
      status: selectedQuality && selectedResolution
        ? (presetMatrix?.available_presets[selectedQuality]?.includes(selectedResolution) ? 'pass' : 'warn')
        : 'fail',
      message: selectedQuality && selectedResolution
        ? `${selectedQuality}@${selectedResolution}`
        : 'Not selected',
    },
    {
      id: 'omniparser',
      label: 'OmniParser',
      status: omniparserStatus === 'online' ? 'pass' : omniparserStatus === 'offline' ? 'fail' : 'pending',
      message: omniparserStatus === 'checking' ? 'Checking...' : omniparserStatus,
    },
  ];

  const passedCount = checks.filter(c => c.status === 'pass').length;
  const failedCount = checks.filter(c => c.status === 'fail').length;
  const warnCount = checks.filter(c => c.status === 'warn').length;
  const allPassed = failedCount === 0 && passedCount === checks.length;

  const statusIcon = (status: CheckItem['status']) => {
    switch (status) {
      case 'pass': return <span className="text-success text-sm">✓</span>;
      case 'fail': return <span className="text-danger text-sm">✗</span>;
      case 'warn': return <span className="text-warning text-sm">⚠</span>;
      default: return <span className="text-text-muted animate-pulse text-sm">○</span>;
    }
  };

  return (
    <div className="px-2 py-1.5 bg-surface-elevated/30 rounded-md border border-border/50 h-full flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between mb-1 flex-shrink-0">
        <span className="text-[10px] font-semibold text-text-muted uppercase">Pre-flight</span>
        <span className={`text-[10px] font-medium ${allPassed ? 'text-success' : failedCount > 0 ? 'text-danger' : 'text-warning'}`}>
          {passedCount}/{checks.length}
        </span>
      </div>

      {/* Checks list */}
      <div className="space-y-0.5 flex-1 overflow-y-auto">
        {checks.map((check) => (
          <div key={check.id} className="flex items-center gap-1.5 text-[10px]">
            {statusIcon(check.status)}
            <span className="text-text-muted w-14 flex-shrink-0">{check.label}</span>
            <span className={`truncate flex-1 ${
              check.status === 'pass' ? 'text-text-secondary' :
              check.status === 'fail' ? 'text-danger' :
              check.status === 'warn' ? 'text-warning' : 'text-text-muted'
            }`} title={check.message}>
              {check.message}
            </span>
          </div>
        ))}
      </div>

      {/* Summary - compact */}
      <div className="mt-1 pt-1 border-t border-border/50 flex-shrink-0">
        {failedCount > 0 ? (
          <div className="text-[10px] text-danger">✗ {failedCount} issue{failedCount > 1 ? 's' : ''}</div>
        ) : warnCount > 0 ? (
          <div className="text-[10px] text-warning">⚠ {warnCount} warning{warnCount > 1 ? 's' : ''}</div>
        ) : (
          <div className="text-[10px] text-success">✓ Ready</div>
        )}
      </div>
    </div>
  );
}
