/**
 * MobileDashboard - Simplified mobile admin interface
 * Left drawer: Online SUTs
 * Main: SUT info, Game library (horizontal), preset dropdown, preflight, GO button
 * Right drawer: Settings, active run, recent runs with snake timeline
 */

import { useState, useCallback, useMemo, useEffect } from 'react';
import { Menu, X, ChevronRight, ChevronDown, Play, Monitor, Clock, Zap, Cpu, HardDrive, MonitorPlay, CheckCircle, AlertCircle, Loader2, Brain, Antenna, ListOrdered, FileChartColumn, ScanEye } from 'lucide-react';
import { useDevices, useGames, useRuns, useCampaigns, useServiceHealth, useInstalledGames } from '../../hooks';
import { SnakeTimeline } from '../SnakeTimeline';
import { getSutSystemInfoByIp, startRun, createCampaign } from '../../api';
import type { SUT, GameConfig, SUTSystemInfo, AutomationRun } from '../../types';

// Preset levels for dropdown
const PRESET_LEVELS = [
  { id: 'low-1080p', name: 'Low 1080p' },
  { id: 'medium-1080p', name: 'Medium 1080p' },
  { id: 'high-1080p', name: 'High 1080p' },
  { id: 'ultra-1080p', name: 'Ultra 1080p' },
  { id: 'low-1440p', name: 'Low 1440p' },
  { id: 'medium-1440p', name: 'Medium 1440p' },
  { id: 'high-1440p', name: 'High 1440p' },
  { id: 'ultra-1440p', name: 'Ultra 1440p' },
  { id: 'high-2160p', name: 'High 4K' },
  { id: 'ultra-2160p', name: 'Ultra 4K' },
];

// Get game image URL
const getGameImageUrl = (game: GameConfig): string => {
  const slug = game.preset_id || game.name.toLowerCase().replace(/[^a-z0-9]+/g, '-');
  return `/game-images/${slug}.jpg`;
};

const getSteamHeaderUrl = (steamAppId: string | undefined): string | null => {
  if (!steamAppId) return null;
  return `https://cdn.cloudflare.steamstatic.com/steam/apps/${steamAppId}/header.jpg`;
};

// Mobile Game Card - Compact horizontal layout with bg image, name at bottom
function MobileGameCard({
  game,
  isSelected,
  isInstalled,
  onSelect
}: {
  game: GameConfig;
  isSelected: boolean;
  isInstalled: boolean | null;
  onSelect: () => void;
}) {
  const [imgSrc, setImgSrc] = useState(getGameImageUrl(game));
  const [imgError, setImgError] = useState(false);

  const handleImageError = () => {
    if (!imgError) {
      setImgError(true);
      const steamUrl = getSteamHeaderUrl(game.steam_app_id);
      if (steamUrl) setImgSrc(steamUrl);
    }
  };

  const displayName = game.display_name || game.name.replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
  const isAvailable = isInstalled === null || isInstalled;

  return (
    <button
      onClick={onSelect}
      disabled={!isAvailable}
      className={`
        relative flex-shrink-0 w-36 h-24 rounded-xl overflow-hidden
        transition-all duration-200 touch-manipulation
        ${isSelected
          ? 'ring-2 ring-accent scale-[1.02] shadow-lg shadow-accent/20'
          : 'ring-1 ring-white/10'
        }
        ${!isAvailable ? 'opacity-40 grayscale' : ''}
      `}
    >
      {/* Background Image */}
      <img
        src={imgSrc}
        alt={displayName}
        onError={handleImageError}
        className="absolute inset-0 w-full h-full object-cover"
      />

      {/* Bottom gradient overlay */}
      <div className="absolute inset-0 bg-gradient-to-t from-black/90 via-black/30 to-transparent" />

      {/* Content - name at bottom */}
      <div className="absolute inset-x-0 bottom-0 p-2">
        <h3 className="text-white font-medium text-xs leading-tight line-clamp-2 text-center">
          {displayName}
        </h3>
      </div>

      {/* Selection indicator */}
      {isSelected && (
        <div className="absolute top-1.5 right-1.5 w-5 h-5 rounded-full bg-accent flex items-center justify-center">
          <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
          </svg>
        </div>
      )}

      {/* Not installed badge */}
      {isInstalled === false && (
        <span className="absolute top-1.5 left-1.5 text-[8px] text-white/60 bg-black/60 px-1 py-0.5 rounded">
          N/A
        </span>
      )}
    </button>
  );
}

// Mobile SUT Card
function MobileSUTCard({
  sut,
  isSelected,
  onSelect
}: {
  sut: SUT;
  isSelected: boolean;
  onSelect: () => void;
}) {
  const isOnline = sut.status === 'online';

  return (
    <button
      onClick={onSelect}
      className={`
        w-full p-3 rounded-lg text-left transition-all touch-manipulation
        ${isSelected
          ? 'bg-accent/20 border border-accent'
          : 'bg-surface-elevated border border-transparent hover:border-white/10'
        }
      `}
    >
      <div className="flex items-center gap-3">
        <div className={`w-2.5 h-2.5 rounded-full ${isOnline ? 'bg-success' : 'bg-text-muted'}`} />
        <div className="flex-1 min-w-0">
          <div className="text-sm font-medium text-text-primary truncate">
            {sut.hostname || sut.ip}
          </div>
          <div className="text-xs text-text-muted">{sut.ip}</div>
        </div>
        <ChevronRight className="w-4 h-4 text-text-muted" />
      </div>
    </button>
  );
}

// Recent Run Item with re-run button
function RecentRunItem({
  run,
  onRerun,
  isCampaign = false
}: {
  run: { game_name: string; status: string; sut_ip: string; games?: string[] };
  onRerun: () => void;
  isCampaign?: boolean;
}) {
  const statusColor = run.status === 'completed' ? 'text-success' :
                      run.status === 'failed' ? 'text-danger' :
                      run.status === 'running' ? 'text-accent' : 'text-text-muted';

  const displayName = isCampaign && run.games
    ? `Campaign (${run.games.length} games)`
    : run.game_name.replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase());

  return (
    <div className="flex items-center gap-2 py-2 border-b border-border/50 last:border-0">
      <div className="flex-1 min-w-0">
        <div className="text-sm text-text-primary truncate">{displayName}</div>
        {isCampaign && run.games && (
          <div className="text-[10px] text-text-muted truncate">
            {run.games.slice(0, 2).join(', ')}{run.games.length > 2 ? '...' : ''}
          </div>
        )}
      </div>
      <span className={`text-xs font-medium ${statusColor}`}>
        {run.status}
      </span>
      <button
        onClick={(e) => { e.stopPropagation(); onRerun(); }}
        className="p-1.5 rounded hover:bg-surface-hover text-text-muted hover:text-accent transition-colors"
        title="Re-run"
      >
        <Play className="w-3.5 h-3.5" />
      </button>
    </div>
  );
}

// Preflight Check Item
function PreflightItem({ label, status, detail }: { label: string; status: 'pass' | 'fail' | 'pending'; detail?: string }) {
  return (
    <div className="flex items-center gap-2 py-1.5">
      {status === 'pass' && <CheckCircle className="w-4 h-4 text-success flex-shrink-0" />}
      {status === 'fail' && <AlertCircle className="w-4 h-4 text-danger flex-shrink-0" />}
      {status === 'pending' && <Loader2 className="w-4 h-4 text-text-muted flex-shrink-0 animate-spin" />}
      <span className="text-xs text-text-secondary flex-1">{label}</span>
      {detail && <span className="text-xs text-text-muted">{detail}</span>}
    </div>
  );
}

export function MobileDashboard() {
  // Drawer states
  const [leftDrawerOpen, setLeftDrawerOpen] = useState(false);
  const [rightDrawerOpen, setRightDrawerOpen] = useState(false);

  // Core data hooks
  const { devices, onlineDevices } = useDevices();
  const { gamesList } = useGames();
  const { activeRunsList, history, start, stop } = useRuns();
  const { historyCampaigns } = useCampaigns();
  const { services } = useServiceHealth(10000);

  // Selection state
  const [selectedSutId, setSelectedSutId] = useState<string | undefined>();
  const [selectedGameNames, setSelectedGameNames] = useState<Set<string>>(new Set());
  const [selectedPreset, setSelectedPreset] = useState('high-1080p');
  const [iterations, setIterations] = useState(1);
  const [iterationsInput, setIterationsInput] = useState('1'); // String for input display
  const [sutSystemInfo, setSutSystemInfo] = useState<SUTSystemInfo | null>(null);
  const [isLaunching, setIsLaunching] = useState(false);

  // Get selected SUT
  const selectedSut = useMemo(() =>
    devices.find(d => d.device_id === selectedSutId),
    [devices, selectedSutId]
  );

  // Use shared hook for installed games (same logic as desktop)
  const {
    installedGames,
    loading: installedGamesLoading,
    isGameInstalled,
  } = useInstalledGames(selectedSut?.device_id, gamesList);

  // Fetch system info when SUT selected
  useEffect(() => {
    if (!selectedSut?.ip) {
      setSutSystemInfo(null);
      return;
    }

    const fetchSystemInfo = async () => {
      try {
        const sysInfo = await getSutSystemInfoByIp(selectedSut.ip);
        setSutSystemInfo(sysInfo);
      } catch {
        setSutSystemInfo(null);
      }
    };

    fetchSystemInfo();
  }, [selectedSut?.ip]);

  // Preflight status derived from hook state
  const preflightStatus = useMemo(() => {
    if (!selectedSut) return 'idle' as const;
    if (installedGamesLoading) return 'checking' as const;
    if (installedGames === null) return 'failed' as const;
    return 'ready' as const;
  }, [selectedSut, installedGamesLoading, installedGames]);

  // Handle SUT selection
  const handleSelectSut = useCallback((sut: SUT) => {
    setSelectedSutId(sut.device_id);
    setLeftDrawerOpen(false);
  }, []);

  // Handle game selection toggle
  const handleToggleGame = useCallback((gameName: string) => {
    setSelectedGameNames(prev => {
      const next = new Set(prev);
      if (next.has(gameName)) {
        next.delete(gameName);
      } else {
        next.add(gameName);
      }
      return next;
    });
  }, []);

  // Select all available games
  const handleSelectAll = useCallback(() => {
    const availableGames = gamesList.filter(g => {
      const installed = isGameInstalled(g);
      return installed === null || installed;
    });
    setSelectedGameNames(new Set(availableGames.map(g => g.name)));
  }, [gamesList, isGameInstalled]);

  // Clear all selected games
  const handleClearSelection = useCallback(() => {
    setSelectedGameNames(new Set());
  }, []);

  // Handle launch (single game or campaign)
  const handleLaunch = useCallback(async () => {
    if (!selectedSut || selectedGameNames.size === 0) return;

    setIsLaunching(true);
    try {
      const games = Array.from(selectedGameNames);
      if (games.length === 1) {
        // Single game run
        await start(selectedSut.ip, games[0], iterations);
      } else {
        // Multiple games = campaign
        await createCampaign(selectedSut.ip, games, iterations);
      }
      setSelectedGameNames(new Set());
    } catch (err) {
      console.error('Launch failed:', err);
    } finally {
      setIsLaunching(false);
    }
  }, [selectedSut, selectedGameNames, iterations, start]);

  // Handle stop
  const handleStop = useCallback(async (runId: string) => {
    try {
      await stop(runId, true);
    } catch (err) {
      console.error('Stop failed:', err);
    }
  }, [stop]);

  // Recent activity item type for type safety
  type RecentItem = {
    id: string;
    type: 'run' | 'campaign';
    game_name: string;
    games?: string[];
    status: string;
    sut_ip: string;
    sortTime: number;
    run?: AutomationRun;
  };

  // Recent runs and campaigns combined (last 5)
  const recentItems = useMemo((): RecentItem[] => {
    const items: RecentItem[] = [];

    // Add runs
    history.slice(0, 5).forEach(run => {
      items.push({
        id: `run-${run.run_id}`,
        type: 'run',
        game_name: run.game_name,
        status: run.status,
        sut_ip: run.sut_ip,
        sortTime: new Date(run.started_at || 0).getTime(),
        run,
      });
    });

    // Add campaigns
    (historyCampaigns || []).slice(0, 5).forEach(c => {
      items.push({
        id: `campaign-${c.campaign_id}`,
        type: 'campaign',
        game_name: c.name || `Campaign (${c.games?.length || 0} games)`,
        games: c.games,
        status: c.status,
        sut_ip: c.sut_ip,
        sortTime: new Date(c.created_at || 0).getTime(),
      });
    });

    return items
      .sort((a, b) => b.sortTime - a.sortTime)
      .slice(0, 5);
  }, [history, historyCampaigns]);

  // Re-run handlers
  const handleRerunRun = useCallback(async (run: AutomationRun) => {
    if (!run.sut_ip || !run.game_name) return;
    setIsLaunching(true);
    try {
      await startRun(run.sut_ip, run.game_name, 1);
    } catch (err) {
      console.error('Re-run failed:', err);
    } finally {
      setIsLaunching(false);
    }
  }, []);

  const handleRerunCampaign = useCallback(async (campaignData: { sut_ip: string; games?: string[] }) => {
    if (!campaignData.sut_ip || !campaignData.games?.length) return;
    setIsLaunching(true);
    try {
      await createCampaign(campaignData.sut_ip, campaignData.games, 1);
    } catch (err) {
      console.error('Re-run campaign failed:', err);
    } finally {
      setIsLaunching(false);
    }
  }, []);

  // Active run for timeline
  const activeRun = useMemo(() =>
    activeRunsList.find(r => r.status === 'running'),
    [activeRunsList]
  );

  // Preflight checks - detailed and context-aware
  const preflightChecks = useMemo((): Array<{ label: string; status: 'pass' | 'fail' | 'pending'; detail?: string }> => {
    if (!selectedSut) return [];

    const checks: Array<{ label: string; status: 'pass' | 'fail' | 'pending'; detail?: string }> = [];

    // 1. SUT Online
    checks.push({
      label: 'SUT Online',
      status: selectedSut.status === 'online' ? 'pass' : 'fail',
      detail: selectedSut.hostname || selectedSut.ip,
    });

    // 2. System Info Loaded
    checks.push({
      label: 'System Info',
      status: sutSystemInfo ? 'pass' : installedGamesLoading ? 'pending' : 'fail',
      detail: sutSystemInfo
        ? `${sutSystemInfo.gpu?.name?.split(' ').slice(0, 2).join(' ') || 'GPU'} • ${Math.round(sutSystemInfo.ram?.total_gb || 0)}GB`
        : undefined,
    });

    // 3. Game(s) Selected
    const selectedCount = selectedGameNames.size;
    checks.push({
      label: 'Game Selected',
      status: selectedCount > 0 ? 'pass' : 'fail',
      detail: selectedCount > 0
        ? selectedCount === 1
          ? Array.from(selectedGameNames)[0].replace(/-/g, ' ')
          : `${selectedCount} games`
        : 'None',
    });

    // 4. Selected Game(s) Installed
    if (selectedCount > 0 && installedGames !== null) {
      const selectedGamesArray = Array.from(selectedGameNames);
      const installedCount = selectedGamesArray.filter(g => installedGames.includes(g)).length;
      const allInstalled = installedCount === selectedCount;

      checks.push({
        label: 'Game Installed',
        status: allInstalled ? 'pass' : installedCount > 0 ? 'pending' : 'fail',
        detail: allInstalled
          ? `${installedCount}/${selectedCount} on SUT`
          : `${installedCount}/${selectedCount} found`,
      });
    } else if (selectedCount > 0) {
      checks.push({
        label: 'Game Installed',
        status: installedGamesLoading ? 'pending' : 'fail',
        detail: installedGamesLoading ? 'Checking...' : 'Unknown',
      });
    }

    // 5. Preset Selected
    checks.push({
      label: 'Preset Selected',
      status: selectedPreset ? 'pass' : 'fail',
      detail: selectedPreset
        ? PRESET_LEVELS.find(p => p.id === selectedPreset)?.name
        : 'None',
    });

    // 6. OmniParser Available (via services hook)
    const omniOnline = services?.omniparserInstances?.some(i => i.status === 'online') ?? false;
    const omniCount = services?.omniparserInstances?.filter(i => i.status === 'online').length ?? 0;
    const omniTotal = services?.omniparserInstances?.length ?? 0;
    checks.push({
      label: 'OmniParser',
      status: omniOnline ? 'pass' : 'fail',
      detail: omniTotal > 0 ? `${omniCount}/${omniTotal} online` : 'Unavailable',
    });

    return checks;
  }, [selectedSut, sutSystemInfo, selectedGameNames, installedGames, installedGamesLoading, selectedPreset, services]);

  const canLaunch = selectedSut && selectedGameNames.size > 0 && preflightStatus === 'ready' && !isLaunching;

  return (
    <div className="flex flex-col h-[100dvh] bg-background overflow-hidden">
      {/* Minimal Header - just logo and drawers */}
      <header className="flex-shrink-0 h-12 px-3 flex items-center justify-between bg-surface border-b border-border safe-area-pt">
        <button
          onClick={() => setLeftDrawerOpen(true)}
          className="p-2 -ml-1 rounded-lg hover:bg-surface-elevated touch-manipulation"
        >
          <Menu className="w-5 h-5 text-text-secondary" />
        </button>

        <div className="flex items-center gap-1.5">
          <span className="font-numbers text-base font-bold text-accent">RAPTOR</span>
          <span className="font-numbers text-base font-bold text-brand-cyan">X</span>
        </div>

        <button
          onClick={() => setRightDrawerOpen(true)}
          className="p-2 -mr-1 rounded-lg hover:bg-surface-elevated touch-manipulation relative"
        >
          <Clock className="w-5 h-5 text-text-secondary" />
          {activeRunsList.length > 0 && (
            <span className="absolute top-1 right-1 w-2 h-2 bg-accent rounded-full animate-pulse" />
          )}
        </button>
      </header>

      {/* Main Content - scrollable with extra padding for fixed bottom bar */}
      <main className="flex-1 overflow-y-auto overscroll-contain pb-32">
        {/* Selected SUT Banner with System Info */}
        <div className="px-3 py-2 bg-surface-elevated border-b border-border">
          <button
            onClick={() => setLeftDrawerOpen(true)}
            className="flex items-center gap-2 w-full text-left mb-2"
          >
            <Monitor className="w-4 h-4 text-text-muted" />
            {selectedSut ? (
              <>
                <span className="flex-1 text-sm font-medium text-text-primary truncate">
                  {selectedSut.hostname || selectedSut.ip}
                </span>
                <div className={`w-2 h-2 rounded-full ${selectedSut.status === 'online' ? 'bg-success' : 'bg-text-muted'}`} />
              </>
            ) : (
              <span className="flex-1 text-sm text-text-muted">Select a SUT...</span>
            )}
            <ChevronRight className="w-4 h-4 text-text-muted" />
          </button>

          {/* System Info - compact display */}
          {sutSystemInfo && (
            <div className="flex items-center gap-3 text-xs text-text-muted mt-1 overflow-x-auto scrollbar-hide">
              <div className="flex items-center gap-1 flex-shrink-0">
                <Cpu className="w-3 h-3" />
                <span className="truncate max-w-24">{sutSystemInfo.gpu?.name?.split(' ').slice(0, 3).join(' ') || 'GPU'}</span>
              </div>
              <div className="flex items-center gap-1 flex-shrink-0">
                <HardDrive className="w-3 h-3" />
                <span>{Math.round(sutSystemInfo.ram?.total_gb || 0)}GB</span>
              </div>
              <div className="flex items-center gap-1 flex-shrink-0">
                <MonitorPlay className="w-3 h-3" />
                <span>{sutSystemInfo.screen?.width}x{sutSystemInfo.screen?.height}</span>
              </div>
            </div>
          )}
        </div>

        {/* Active Run Section - shows when run is active */}
        {activeRun && (
          <section className="px-3 py-3 border-b border-border bg-surface">
            <div className="flex items-center justify-between mb-2">
              <h2 className="text-xs font-semibold text-text-secondary uppercase tracking-wide flex items-center gap-1.5">
                <Zap className="w-3.5 h-3.5 text-accent animate-pulse" />
                Active Run
              </h2>
              <button
                onClick={() => handleStop(activeRun.run_id)}
                className="text-xs text-danger hover:text-danger/80 px-2 py-1 rounded bg-danger/10"
              >
                Stop
              </button>
            </div>
            <div className="bg-surface-elevated rounded-lg p-2">
              <SnakeTimeline
                runId={activeRun.run_id}
                gameName={activeRun.game_name.replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
                pollInterval={2000}
                maxRows={3}
              />
            </div>
          </section>
        )}

        {/* Game Library - Horizontal Scroll */}
        <section className="py-3">
          <div className="px-3 mb-2 flex items-center justify-between">
            <h2 className="text-xs font-semibold text-text-secondary uppercase tracking-wide">
              Games
            </h2>
            <div className="flex items-center gap-2">
              <span className="text-xs text-text-muted">
                {selectedGameNames.size} selected
              </span>
              <button
                onClick={handleSelectAll}
                className="px-2 py-0.5 text-[10px] text-text-muted hover:text-primary border border-border rounded hover:border-primary transition-colors"
              >
                All
              </button>
              <button
                onClick={handleClearSelection}
                disabled={selectedGameNames.size === 0}
                className="px-2 py-0.5 text-[10px] text-text-muted hover:text-danger border border-border rounded hover:border-danger transition-colors disabled:opacity-50"
              >
                Clear
              </button>
            </div>
          </div>

          <div className="overflow-x-auto scrollbar-hide">
            <div className="flex gap-2 px-3 pb-1">
              {gamesList.map(game => (
                <MobileGameCard
                  key={game.name}
                  game={game}
                  isSelected={selectedGameNames.has(game.name)}
                  isInstalled={isGameInstalled(game)}
                  onSelect={() => handleToggleGame(game.name)}
                />
              ))}
            </div>
          </div>
        </section>

        {/* Preset & Iterations */}
        <section className="px-3 py-3 border-t border-border/50">
          <div className="flex gap-3">
            {/* Preset Dropdown */}
            <div className="flex-1">
              <label className="text-xs font-semibold text-text-secondary uppercase tracking-wide block mb-2">
                Preset Level
              </label>
              <div className="relative">
                <select
                  value={selectedPreset}
                  onChange={(e) => setSelectedPreset(e.target.value)}
                  className="w-full appearance-none bg-surface-elevated border border-border rounded-lg px-3 py-2.5 text-sm text-text-primary focus:outline-none focus:border-accent"
                >
                  {PRESET_LEVELS.map(preset => (
                    <option key={preset.id} value={preset.id}>
                      {preset.name}
                    </option>
                  ))}
                </select>
                <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted pointer-events-none" />
              </div>
            </div>

            {/* Iterations Input with +/- buttons */}
            <div className="w-28">
              <label className="text-xs font-semibold text-text-secondary uppercase tracking-wide block mb-2">
                Iterations
              </label>
              <div className="flex items-center">
                <button
                  onClick={() => {
                    const newVal = Math.max(1, iterations - 1);
                    setIterations(newVal);
                    setIterationsInput(String(newVal));
                  }}
                  className="w-9 h-10 bg-surface-elevated border border-border rounded-l-lg text-text-secondary hover:bg-surface hover:text-text-primary active:bg-accent/20 transition-colors text-lg font-medium touch-manipulation"
                >
                  −
                </button>
                <input
                  type="text"
                  inputMode="numeric"
                  pattern="[0-9]*"
                  value={iterationsInput}
                  onChange={(e) => {
                    const val = e.target.value;
                    // Allow empty or digits only while typing
                    if (val === '' || /^\d+$/.test(val)) {
                      setIterationsInput(val);
                      const num = parseInt(val) || 0;
                      setIterations(Math.min(100, num));
                    }
                  }}
                  onBlur={() => {
                    // On blur, enforce minimum of 1 and sync display
                    const finalVal = Math.max(1, Math.min(100, iterations));
                    setIterations(finalVal);
                    setIterationsInput(String(finalVal));
                  }}
                  className="w-10 h-10 bg-surface-elevated border-y border-border text-sm text-text-primary text-center focus:outline-none focus:bg-surface [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
                />
                <button
                  onClick={() => {
                    const newVal = Math.min(100, iterations + 1);
                    setIterations(newVal);
                    setIterationsInput(String(newVal));
                  }}
                  className="w-9 h-10 bg-surface-elevated border border-border rounded-r-lg text-text-secondary hover:bg-surface hover:text-text-primary active:bg-accent/20 transition-colors text-lg font-medium touch-manipulation"
                >
                  +
                </button>
              </div>
            </div>
          </div>
        </section>

        {/* Preflight Checks */}
        {selectedSut && (
          <section className="px-3 py-3 border-t border-border/50">
            <h2 className="text-xs font-semibold text-text-secondary uppercase tracking-wide mb-2">
              Preflight Checks
            </h2>
            <div className="bg-surface-elevated rounded-lg px-3 py-1">
              {preflightChecks.map((check, i) => (
                <PreflightItem key={i} {...check} />
              ))}
            </div>
          </section>
        )}
      </main>

      {/* Bottom Action Bar - Fixed with service status */}
      <div className="fixed bottom-0 left-0 right-0 bg-surface border-t border-border z-40">
        {/* Compact Service Status - centered */}
        <div className="flex items-center justify-center gap-4 px-3 py-1.5 border-b border-border/50 bg-surface-elevated">
          <div className="flex items-center gap-1" title="Gemma Backend">
            <Brain className={`w-3.5 h-3.5 ${services?.gemmaBackend?.status === 'online' ? 'text-success' : 'text-danger'}`} />
            <span className="text-[10px] text-text-muted">Gemma</span>
          </div>
          <div className="flex items-center gap-1" title="SUT Discovery">
            <Antenna className={`w-3.5 h-3.5 ${services?.discoveryService?.status === 'online' ? 'text-success' : 'text-danger'}`} />
            <span className="text-[10px] text-text-muted">Discovery</span>
          </div>
          <div className="flex items-center gap-1" title="Queue Service">
            <ListOrdered className={`w-3.5 h-3.5 ${services?.queueService?.status === 'online' ? 'text-success' : 'text-danger'}`} />
            <span className="text-[10px] text-text-muted">Queue</span>
          </div>
          <div className="flex items-center gap-1" title="Preset Manager">
            <FileChartColumn className={`w-3.5 h-3.5 ${services?.presetManager?.status === 'online' ? 'text-success' : 'text-danger'}`} />
            <span className="text-[10px] text-text-muted">Presets</span>
          </div>
          {/* OmniParser Instances - consolidated count */}
          {services?.omniparserInstances && services.omniparserInstances.length > 0 && (
            <div
              className="flex items-center gap-1"
              title={`${services.omniparserInstances.filter(i => i.status === 'online').length}/${services.omniparserInstances.length} online`}
            >
              <ScanEye className={`w-3.5 h-3.5 ${
                services.omniparserInstances.every(i => i.status === 'online') ? 'text-success' :
                services.omniparserInstances.some(i => i.status === 'online') ? 'text-warning' : 'text-danger'
              }`} />
              <span className="text-[10px] text-text-muted">OP ×{services.omniparserInstances.length}</span>
            </div>
          )}
        </div>

        {/* Launch Button */}
        <div className="p-3 pb-safe">
          <button
            onClick={handleLaunch}
            disabled={!canLaunch}
            className={`
              w-full py-3.5 rounded-xl font-semibold text-sm flex items-center justify-center gap-2
              transition-all touch-manipulation
              ${canLaunch
                ? 'bg-accent text-white active:scale-[0.98]'
                : 'bg-surface-elevated text-text-muted cursor-not-allowed'
              }
            `}
          >
            {isLaunching ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Launching...
              </>
            ) : (
              <>
                <Play className="w-4 h-4" />
                {selectedGameNames.size > 0
                  ? `Start Automation (${selectedGameNames.size})`
                  : 'Select Games'
                }
              </>
            )}
          </button>
        </div>
      </div>

      {/* Left Drawer - SUTs */}
      {leftDrawerOpen && (
        <div className="fixed inset-0 z-50">
          <div
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            onClick={() => setLeftDrawerOpen(false)}
          />
          <div className="absolute left-0 top-0 bottom-0 w-72 bg-surface slide-in-from-left">
            <div className="flex items-center justify-between p-3 border-b border-border">
              <h2 className="font-semibold text-text-primary">SUTs</h2>
              <button
                onClick={() => setLeftDrawerOpen(false)}
                className="p-2 -mr-2 rounded-lg hover:bg-surface-elevated"
              >
                <X className="w-5 h-5 text-text-secondary" />
              </button>
            </div>

            <div className="p-3 space-y-2 overflow-y-auto max-h-[calc(100vh-60px)]">
              {/* Online SUTs */}
              <div className="text-xs text-text-muted uppercase tracking-wide px-1 py-1">
                Online ({onlineDevices.length})
              </div>
              {onlineDevices.map(sut => (
                <MobileSUTCard
                  key={sut.device_id}
                  sut={sut}
                  isSelected={sut.device_id === selectedSutId}
                  onSelect={() => handleSelectSut(sut)}
                />
              ))}

              {/* Offline SUTs */}
              {devices.filter(d => d.status !== 'online').length > 0 && (
                <>
                  <div className="text-xs text-text-muted uppercase tracking-wide px-1 py-1 mt-3">
                    Offline
                  </div>
                  {devices.filter(d => d.status !== 'online').map(sut => (
                    <MobileSUTCard
                      key={sut.device_id}
                      sut={sut}
                      isSelected={sut.device_id === selectedSutId}
                      onSelect={() => handleSelectSut(sut)}
                    />
                  ))}
                </>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Right Drawer - Activity */}
      {rightDrawerOpen && (
        <div className="fixed inset-0 z-50">
          <div
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            onClick={() => setRightDrawerOpen(false)}
          />
          <div className="absolute right-0 top-0 bottom-0 w-80 bg-surface slide-in-from-right">
            <div className="flex items-center justify-between p-3 border-b border-border">
              <h2 className="font-semibold text-text-primary">Activity</h2>
              <button
                onClick={() => setRightDrawerOpen(false)}
                className="p-2 -mr-2 rounded-lg hover:bg-surface-elevated"
              >
                <X className="w-5 h-5 text-text-secondary" />
              </button>
            </div>

            <div className="overflow-y-auto max-h-[calc(100vh-60px)]">
              {/* Active Run Timeline */}
              {activeRun && (
                <div className="p-3 border-b border-border">
                  <h3 className="text-xs font-semibold text-text-secondary uppercase tracking-wide mb-2 flex items-center gap-1.5">
                    <Zap className="w-3.5 h-3.5 text-accent animate-pulse" />
                    Live Run
                  </h3>
                  <div className="bg-surface-elevated rounded-lg p-2">
                    <SnakeTimeline
                      runId={activeRun.run_id}
                      gameName={activeRun.game_name.replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
                      pollInterval={2000}
                      maxRows={4}
                    />
                  </div>
                </div>
              )}

              {/* Recent Runs & Campaigns */}
              <div className="p-3">
                <h3 className="text-xs font-semibold text-text-secondary uppercase tracking-wide mb-2 flex items-center gap-1.5">
                  <Clock className="w-3.5 h-3.5" />
                  Recent Activity
                </h3>
                <div className="bg-surface-elevated rounded-lg p-3">
                  {recentItems.length > 0 ? (
                    recentItems.map(item => (
                      <RecentRunItem
                        key={item.id}
                        run={item}
                        isCampaign={item.type === 'campaign'}
                        onRerun={() => {
                          if (item.type === 'campaign' && item.games) {
                            handleRerunCampaign({ sut_ip: item.sut_ip, games: item.games });
                          } else if (item.run) {
                            handleRerunRun(item.run);
                          }
                        }}
                      />
                    ))
                  ) : (
                    <div className="text-sm text-text-muted text-center py-3">
                      No recent activity
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
