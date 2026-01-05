/**
 * Dashboard - Data-Dense Operations Dashboard
 * Unified view combining Fleet Status, Quick Launch, Active Runs, Games, and Metrics
 * Grafana/Datadog-style layout with radial gauges and grid panels
 *
 * Mobile: Shows simplified MobileDashboard for screens < 768px
 */

import { useState, useCallback, useMemo, useEffect } from 'react';
import { useDevices, useGames, useRuns, useCampaigns } from '../hooks';
import {
  FleetStatusPanel,
  QuickLaunchPanel,
  ActiveRunsPanel,
  GameLibraryPanel,
  RunMetricsPanel,
  SnakeTimeline,
} from '../components';
import { MobileDashboard } from '../components/mobile';
import { getSutInstalledGamesViaProxy, createCampaign } from '../api';
import type { SUT, GameConfig } from '../types';

// Hook to detect mobile viewport
function useIsMobile(breakpoint = 768) {
  const [isMobile, setIsMobile] = useState(() =>
    typeof window !== 'undefined' ? window.innerWidth < breakpoint : false
  );

  useEffect(() => {
    const handleResize = () => {
      setIsMobile(window.innerWidth < breakpoint);
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [breakpoint]);

  return isMobile;
}

export function Dashboard() {
  const isMobile = useIsMobile();

  // IMPORTANT: All hooks must be called BEFORE any conditional returns
  // Core data hooks (called even on mobile to avoid hooks order violation)
  const { devices, onlineDevices } = useDevices();
  const { gamesList } = useGames();
  const { activeRunsList, history, start, stop } = useRuns();
  const { activeCampaigns, historyCampaigns, stop: stopCampaignFn } = useCampaigns();

  // Cross-panel selection state
  const [selectedSutId, setSelectedSutId] = useState<string | undefined>();
  const [selectedGameNames, setSelectedGameNames] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [installedGames, setInstalledGames] = useState<string[] | null>(null);

  // All runs for metrics
  const allRuns = useMemo(() => [...activeRunsList, ...history], [activeRunsList, history]);

  // All campaigns for metrics (combine active and history)
  const allCampaigns = useMemo(() => [...activeCampaigns, ...historyCampaigns], [activeCampaigns, historyCampaigns]);

  // Get selected SUT object
  const selectedSut = useMemo(() =>
    devices.find(d => d.device_id === selectedSutId),
    [devices, selectedSutId]
  );

  // Fetch installed games when SUT is selected
  useEffect(() => {
    if (!selectedSut?.device_id) {
      setInstalledGames(null);
      return;
    }

    // Helper: normalize string for matching (remove special chars, lowercase)
    const normalize = (s: string) => s.toLowerCase().replace(/[^a-z0-9]/g, '');

    // Helper: extract significant words (3+ chars) for word-based matching
    const getWords = (s: string) => s.toLowerCase()
      .split(/[\s\-_:,.]+/)
      .filter(w => w.length >= 3);

    // Helper: check if word sets overlap significantly
    const hasSignificantOverlap = (words1: string[], words2: string[]) => {
      const matchCount = words1.filter(w1 =>
        words2.some(w2 => w1.includes(w2) || w2.includes(w1))
      ).length;
      return matchCount >= 2; // At least 2 matching words
    };

    const fetchInstalledGames = async () => {
      try {
        // Use proxy via discovery service to avoid CORS
        const response = await getSutInstalledGamesViaProxy(selectedSut.device_id);
        console.log('Installed games from SUT:', response.games);

        // Match installed games to our game configs
        const installedNames: string[] = [];

        for (const installedGame of response.games) {
          // Debug: log FFXIV processing
          const isFFXIV = installedGame.name.toLowerCase().includes('ffxiv');
          if (isFFXIV) {
            console.log('[FFXIV] Processing:', installedGame.name, 'steam_app_id:', installedGame.steam_app_id);
          }

          // Try each matching strategy
          let matchedConfig: GameConfig | undefined;
          const installedLower = installedGame.name.toLowerCase();
          const installedNorm = normalize(installedGame.name);
          const installedWords = getWords(installedGame.name);

          // 1. Match by Steam App ID (most reliable)
          if (installedGame.steam_app_id) {
            matchedConfig = gamesList.find(gc =>
              gc.steam_app_id && String(gc.steam_app_id) === String(installedGame.steam_app_id)
            );
            if (matchedConfig) {
              console.log(`[Steam ID] "${installedGame.name}" (${installedGame.steam_app_id}) -> "${matchedConfig.name}"`);
            }
          }

          // 2. Exact name match (case-insensitive)
          if (!matchedConfig) {
            matchedConfig = gamesList.find(gc => {
              const displayLower = (gc.display_name || '').toLowerCase();
              const nameLower = gc.name.toLowerCase().replace(/-/g, ' ');
              return displayLower === installedLower || nameLower === installedLower;
            });
            if (isFFXIV && matchedConfig) console.log('[FFXIV] Matched by Strategy 2 (exact):', matchedConfig.name);
          }

          // 3. Contains match (substring) - skip empty strings!
          if (!matchedConfig) {
            matchedConfig = gamesList.find(gc => {
              const displayLower = (gc.display_name || '').toLowerCase();
              const nameLower = gc.name.toLowerCase().replace(/-/g, ' ');
              // Guard against empty string matches (every string contains "")
              return (displayLower && (installedLower.includes(displayLower) || displayLower.includes(installedLower))) ||
                     (nameLower && (installedLower.includes(nameLower) || nameLower.includes(installedLower)));
            });
            if (isFFXIV && matchedConfig) console.log('[FFXIV] Matched by Strategy 3 (contains):', matchedConfig.name);
          }

          // 4. Normalized string match (ignore all special chars) - skip empty strings!
          if (!matchedConfig) {
            matchedConfig = gamesList.find(gc => {
              const displayNorm = normalize(gc.display_name || '');
              const nameNorm = normalize(gc.name);
              const presetNorm = normalize(gc.preset_id || '');
              // Guard against empty string matches
              return (displayNorm && (installedNorm.includes(displayNorm) || displayNorm.includes(installedNorm))) ||
                     (nameNorm && (installedNorm.includes(nameNorm) || nameNorm.includes(installedNorm))) ||
                     (presetNorm && (installedNorm.includes(presetNorm) || presetNorm.includes(installedNorm)));
            });
            if (isFFXIV && matchedConfig) console.log('[FFXIV] Matched by Strategy 4 (normalized):', matchedConfig.name);
          }

          // 5. Word-based matching (at least 2 significant words overlap)
          if (!matchedConfig) {
            // Debug for FFXIV
            if (installedGame.name.toLowerCase().includes('ffxiv')) {
              console.log('[FFXIV Debug] installedWords:', installedWords);
              const ffxivConfig = gamesList.find(gc => gc.name.toLowerCase().includes('fantasy'));
              if (ffxivConfig) {
                const nameWords = getWords(ffxivConfig.name);
                console.log('[FFXIV Debug] config name:', ffxivConfig.name);
                console.log('[FFXIV Debug] nameWords:', nameWords);
                console.log('[FFXIV Debug] hasSignificantOverlap:', hasSignificantOverlap(installedWords, nameWords));
              } else {
                console.log('[FFXIV Debug] No config with "fantasy" found in gamesList');
                console.log('[FFXIV Debug] gamesList names:', gamesList.map(g => g.name));
              }
            }
            matchedConfig = gamesList.find(gc => {
              const displayWords = getWords(gc.display_name || '');
              const nameWords = getWords(gc.name);
              return hasSignificantOverlap(installedWords, displayWords) ||
                     hasSignificantOverlap(installedWords, nameWords);
            });
          }

          // 6. Known abbreviation mappings for benchmarks
          if (!matchedConfig) {
            const abbreviations: Record<string, string[]> = {
              'ffxiv': ['final fantasy xiv', 'final-fantasy-xiv'],
              'bmw': ['black myth wukong', 'black-myth-wukong'],
              'sotr': ['shadow of the tomb raider', 'shadow-of-the-tomb-raider'],
              'rdr2': ['red dead redemption 2', 'red-dead-redemption-2'],
              'cp2077': ['cyberpunk 2077', 'cyberpunk-2077'],
              'hzd': ['horizon zero dawn', 'horizon-zero-dawn'],
              'cs2': ['counter strike 2', 'counter-strike-2'],
            };

            for (const [abbr, expansions] of Object.entries(abbreviations)) {
              if (installedLower.includes(abbr)) {
                matchedConfig = gamesList.find(gc =>
                  expansions.some(exp =>
                    gc.name.toLowerCase().includes(exp) ||
                    (gc.display_name || '').toLowerCase().includes(exp)
                  )
                );
                if (matchedConfig) break;
              }
            }
          }

          if (matchedConfig && !installedNames.includes(matchedConfig.name)) {
            console.log(`Matched "${installedGame.name}" -> "${matchedConfig.name}"`);
            installedNames.push(matchedConfig.name);
          }

          // Debug: show final FFXIV result
          if (isFFXIV) {
            if (matchedConfig) {
              console.log('[FFXIV] Final match:', matchedConfig.name);
            } else {
              console.warn('[FFXIV] NO MATCH FOUND!');
              console.warn('[FFXIV] gamesList has FFXIV?', gamesList.some(g => g.name.toLowerCase().includes('fantasy')));
            }
          }
        }

        console.log('Matched games:', installedNames, `(${installedNames.length}/${response.games.length})`);
        setInstalledGames(installedNames);
      } catch (err) {
        console.error('Failed to fetch installed games:', err);
        // On error, set null so games are NOT grayed out (null = no data available)
        setInstalledGames(null);
      }
    };

    fetchInstalledGames();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedSut?.device_id, gamesList.length]);

  // Handle SUT selection from FleetStatusPanel
  const handleSelectSut = useCallback((sut: SUT | null) => {
    setSelectedSutId(sut?.device_id);
  }, []);

  // Handle game selection from GameLibraryPanel (multi-select)
  const handleSelectGames = useCallback((gameNames: string[]) => {
    setSelectedGameNames(gameNames);
  }, []);

  // Handle quick run from GameLibraryPanel (double-click)
  const handleQuickRun = useCallback(async (game: GameConfig) => {
    // Use first online SUT if none selected
    const targetSutId = selectedSutId || onlineDevices[0]?.device_id;
    if (!targetSutId) {
      setError('No SUT available for quick run');
      return;
    }
    const sut = devices.find(d => d.device_id === targetSutId);
    if (!sut) return;

    try {
      await start(sut.ip, game.name, 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start run');
    }
  }, [selectedSutId, onlineDevices, devices, start]);

  // Handle run started from QuickLaunchPanel
  const handleRunStarted = useCallback((_runId: string) => {
    setError(null);
    // Clear selection after successful run
    setSelectedGameNames([]);
  }, []);

  // Handle campaign started from QuickLaunchPanel
  const handleCampaignStarted = useCallback((_campaignId: string) => {
    setError(null);
    // Clear selection after successful campaign
    setSelectedGameNames([]);
  }, []);

  // Handle stop run
  const handleStopRun = useCallback(async (runId: string, killGame?: boolean) => {
    try {
      await stop(runId, killGame);
    } catch (err) {
      console.error('Failed to stop run:', err);
    }
  }, [stop]);

  // Handle stop campaign
  const handleStopCampaign = useCallback(async (campaignId: string) => {
    try {
      await stopCampaignFn(campaignId);
    } catch (err) {
      console.error('Failed to stop campaign:', err);
    }
  }, [stopCampaignFn]);

  // Handle re-run from metrics panel
  const handleRerun = useCallback(async (gameName: string, sutIp: string) => {
    try {
      await start(sutIp, gameName, 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start re-run');
    }
  }, [start]);

  // Handle re-run campaign from metrics panel
  const handleRerunCampaign = useCallback(async (games: string[], sutIp: string, quality?: string, resolution?: string) => {
    try {
      await createCampaign(sutIp, games, 1, undefined, quality, resolution);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start campaign re-run');
    }
  }, []);

  // Show mobile dashboard on small screens (AFTER all hooks to avoid hooks order violation)
  if (isMobile) {
    return <MobileDashboard />;
  }

  return (
    <div className="flex flex-col h-[calc(100vh-100px)] p-3 bg-background text-text-primary overflow-hidden">
      {/* Error Banner */}
      {error && (
        <div className="flex items-center justify-between bg-danger/20 border border-danger/50 rounded-lg px-4 py-2 mb-3 flex-shrink-0">
          <span className="text-danger text-sm">{error}</span>
          <button
            onClick={() => setError(null)}
            className="text-danger/70 hover:text-danger text-sm"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Main 2-Column Layout: Left (content) + Right (metrics) */}
      <div className="flex-1 min-h-0 flex gap-3">

        {/* === LEFT COLUMN: Fleet + Quick Launch + Game Library === */}
        <div className="flex-1 min-w-0 flex flex-col gap-3">

          {/* Top Bar: Fleet Status + Quick Launch */}
          <div className="flex gap-3 flex-shrink-0 h-48">
            {/* Fleet Status (compact) */}
            <div className="w-48 flex-shrink-0">
              <FleetStatusPanel
                devices={devices}
                onlineDevices={onlineDevices}
                selectedSutId={selectedSutId}
                onSelectSut={handleSelectSut}
                className="h-full"
                compact
              />
            </div>

            {/* Quick Launch (takes remaining width) */}
            <div className="flex-1 min-w-0">
              <QuickLaunchPanel
                devices={devices}
                games={gamesList}
                selectedSutId={selectedSutId}
                selectedGameNames={selectedGameNames}
                onSelectSut={handleSelectSut}
                onRunStarted={handleRunStarted}
                onCampaignStarted={handleCampaignStarted}
                className="h-full"
                compact
              />
            </div>
          </div>

          {/* Game Library (takes remaining height) */}
          <div className="flex-1 min-h-0">
            <GameLibraryPanel
              games={gamesList}
              selectedGames={selectedGameNames}
              installedGames={installedGames ?? undefined}
              hasSutSelected={!!selectedSutId}
              onSelectGames={handleSelectGames}
              onQuickRun={handleQuickRun}
              className="h-full"
            />
          </div>
        </div>

        {/* === RIGHT COLUMN: Active Runs + Timeline + Metrics === */}
        {/* Wider when runs are active to show timeline properly */}
        <div className={`flex-shrink-0 flex flex-col gap-3 overflow-hidden ${
          activeRunsList.length > 0 ? 'w-[650px]' : 'w-[400px]'
        }`}>

          {/* Active Runs Panel - only when runs active */}
          {(activeRunsList.length > 0 || activeCampaigns.length > 0) && (
            <ActiveRunsPanel
              runs={activeRunsList}
              campaigns={activeCampaigns}
              onStopRun={handleStopRun}
              onStopCampaign={handleStopCampaign}
              maxHeight="200px"
              className="flex-shrink-0"
            />
          )}

          {/* Snake Timeline - only visible when a run is actually running */}
          {activeRunsList.some(r => r.status === 'running') && (
            <div className="flex-shrink-0 bg-surface border border-border rounded-lg overflow-hidden animate-in fade-in slide-in-from-top-2 duration-300">
              <div className="px-3 py-2 border-b border-border bg-surface-elevated/50 flex items-center justify-between">
                <h3 className="text-sm font-semibold text-text-secondary uppercase tracking-wide">
                  Timeline
                </h3>
              </div>
              <div className="p-3">
                <SnakeTimeline
                  runId={activeRunsList.find(r => r.status === 'running')?.run_id || null}
                  gameName={activeRunsList.find(r => r.status === 'running')?.game_name?.replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
                  pollInterval={2000}
                  maxRows={4}
                />
              </div>
            </div>
          )}

          {/* Run Metrics Panel - takes full remaining height */}
          <div className="flex-1 min-h-0">
            <RunMetricsPanel
              runs={allRuns}
              campaigns={allCampaigns}
              className="h-full"
              expanded={activeRunsList.length === 0}
              onRerun={handleRerun}
              onRerunCampaign={handleRerunCampaign}
            />
          </div>
        </div>
      </div>

    </div>
  );
}
