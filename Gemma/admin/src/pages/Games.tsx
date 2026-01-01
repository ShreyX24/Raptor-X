import { useState, useEffect } from 'react';
import { useGames, useDevices } from '../hooks';
import { GameCard, PresetMatrix, PreflightChecks, CampaignModal } from '../components';
import type { QualityLevel, Resolution, PresetAvailability } from '../components';
import { startRun, getSutResolutions } from '../api';
import { getSutInstalledGames, getPresetMatrix, type InstalledGameInfo, type SutInstalledGamesResponse } from '../api/presetManager';
import type { GameConfig, SUT, SutDisplayResolution } from '../types';

export function Games() {
  const { gamesList, loading, reload } = useGames();
  const { onlineDevices } = useDevices();
  const [reloading, setReloading] = useState(false);
  const [selectedGame, setSelectedGame] = useState<GameConfig | null>(null);
  const [showRunModal, setShowRunModal] = useState(false);

  // SUT selection for both views
  const [selectedSutIp, setSelectedSutIp] = useState<string>('');
  const [installedGames, setInstalledGames] = useState<SutInstalledGamesResponse | null>(null);
  const [loadingInstalled, setLoadingInstalled] = useState(false);
  const [viewMode, setViewMode] = useState<'configs' | 'installed'>('configs');

  // Separate SUT selection for configs view (to check availability)
  const [configsSutIp, setConfigsSutIp] = useState<string>('');

  // Campaign mode state
  const [campaignMode, setCampaignMode] = useState(false);
  const [selectedCampaignGames, setSelectedCampaignGames] = useState<Set<string>>(new Set());
  const [showCampaignModal, setShowCampaignModal] = useState(false);

  const handleCampaignToggle = (gameName: string, selected: boolean) => {
    setSelectedCampaignGames(prev => {
      const next = new Set(prev);
      if (selected) {
        next.add(gameName);
      } else {
        next.delete(gameName);
      }
      return next;
    });
  };

  const handleClearSelection = () => {
    setSelectedCampaignGames(new Set());
  };

  const handleExitCampaignMode = () => {
    setCampaignMode(false);
    setSelectedCampaignGames(new Set());
  };

  const handleReload = async () => {
    setReloading(true);
    try {
      await reload();
    } catch (error) {
      console.error('Reload failed:', error);
    } finally {
      setReloading(false);
    }
  };

  const handleRunGame = (gameName: string) => {
    const game = gamesList.find(g => g.name === gameName);
    if (game) {
      setSelectedGame(game);
      setShowRunModal(true);
    }
  };

  // Fetch installed games when SUT is selected
  useEffect(() => {
    if (!selectedSutIp) {
      setInstalledGames(null);
      return;
    }

    const fetchInstalledGames = async () => {
      setLoadingInstalled(true);
      try {
        // Get the device's actual port from onlineDevices
        const device = onlineDevices.find(d => d.ip === selectedSutIp);
        const port = device?.port || 8080;  // Default to 8080 (SUT client port)
        const result = await getSutInstalledGames(selectedSutIp, port);
        setInstalledGames(result);
      } catch (error) {
        console.error('Failed to fetch installed games:', error);
        setInstalledGames(null);
      } finally {
        setLoadingInstalled(false);
      }
    };

    fetchInstalledGames();
  }, [selectedSutIp, onlineDevices]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Games</h1>
          <p className="text-gray-500">Configure and run game automation</p>
        </div>
        <div className="flex items-center gap-3">
          {/* Campaign Mode Toggle */}
          <button
            onClick={() => campaignMode ? handleExitCampaignMode() : setCampaignMode(true)}
            className={`px-4 py-2 rounded-lg font-medium flex items-center gap-2 ${
              campaignMode
                ? 'bg-purple-500 text-white hover:bg-purple-600'
                : 'bg-purple-100 text-purple-700 hover:bg-purple-200'
            }`}
          >
            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
            </svg>
            {campaignMode ? 'Exit Campaign Mode' : 'Campaign Mode'}
          </button>
          {/* View Mode Toggle */}
          <div className="flex rounded-lg border border-gray-300 overflow-hidden">
            <button
              onClick={() => setViewMode('configs')}
              className={`px-3 py-1.5 text-sm font-medium ${
                viewMode === 'configs'
                  ? 'bg-blue-500 text-white'
                  : 'bg-white text-gray-700 hover:bg-gray-50'
              }`}
            >
              Configs ({gamesList.length})
            </button>
            <button
              onClick={() => setViewMode('installed')}
              className={`px-3 py-1.5 text-sm font-medium ${
                viewMode === 'installed'
                  ? 'bg-blue-500 text-white'
                  : 'bg-white text-gray-700 hover:bg-gray-50'
              }`}
            >
              Installed on SUT
            </button>
          </div>
          <button
            onClick={handleReload}
            disabled={reloading}
            className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg font-medium hover:bg-gray-200 disabled:bg-gray-50"
          >
            {reloading ? 'Reloading...' : 'Reload Configs'}
          </button>
        </div>
      </div>

      {/* Campaign Mode Floating Action Bar */}
      {campaignMode && (
        <div className="sticky top-0 z-40 bg-purple-600 text-white rounded-lg p-4 shadow-lg flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
              </svg>
              <span className="font-semibold">Campaign Mode</span>
            </div>
            <div className="h-6 w-px bg-purple-400"></div>
            <span className="text-purple-100">
              {selectedCampaignGames.size} game{selectedCampaignGames.size !== 1 ? 's' : ''} selected
            </span>
            {selectedCampaignGames.size > 0 && (
              <button
                onClick={handleClearSelection}
                className="text-purple-200 hover:text-white text-sm underline"
              >
                Clear
              </button>
            )}
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={handleExitCampaignMode}
              className="px-4 py-2 bg-purple-700 hover:bg-purple-800 rounded-lg text-sm font-medium"
            >
              Cancel
            </button>
            <button
              onClick={() => setShowCampaignModal(true)}
              disabled={selectedCampaignGames.size === 0}
              className="px-4 py-2 bg-white text-purple-600 hover:bg-purple-50 rounded-lg text-sm font-semibold disabled:bg-purple-300 disabled:text-purple-500"
            >
              Create Campaign ({selectedCampaignGames.size})
            </button>
          </div>
        </div>
      )}

      {/* SUT Selector (shown in installed view) */}
      {viewMode === 'installed' && (
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <div className="flex items-center gap-4 flex-wrap">
            <div className="flex-1 min-w-[200px]">
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Select SUT to view installed games
              </label>
              <select
                value={selectedSutIp}
                onChange={(e) => setSelectedSutIp(e.target.value)}
                className="w-full rounded-lg border border-gray-300 px-3 py-2"
              >
                <option value="">Choose a SUT...</option>
                {onlineDevices.map((device) => (
                  <option key={device.device_id} value={device.ip}>
                    {device.hostname || device.ip} ({device.ip})
                  </option>
                ))}
              </select>
            </div>
            {installedGames && (
              <div className="flex gap-4 text-sm">
                <div className="px-3 py-2 bg-gray-100 rounded-lg">
                  <span className="text-gray-500">Total:</span>{' '}
                  <span className="font-semibold">{installedGames.games_count}</span>
                </div>
                <div className="px-3 py-2 bg-green-100 rounded-lg">
                  <span className="text-green-700">With Presets:</span>{' '}
                  <span className="font-semibold text-green-700">{installedGames.games_with_presets}</span>
                </div>
                {installedGames.libraries_scanned && (
                  <div className="px-3 py-2 bg-blue-100 rounded-lg">
                    <span className="text-blue-700">Libraries:</span>{' '}
                    <span className="font-semibold text-blue-700">{installedGames.libraries_scanned}</span>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* SUT Selector for Configs view (to check installation) */}
      {viewMode === 'configs' && (
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <div className="flex items-center gap-4 flex-wrap">
            <div className="flex-1 min-w-[200px]">
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Check installation on SUT (optional)
              </label>
              <select
                value={configsSutIp}
                onChange={(e) => setConfigsSutIp(e.target.value)}
                className="w-full rounded-lg border border-gray-300 px-3 py-2"
              >
                <option value="">All configs (no SUT check)</option>
                {onlineDevices.map((device) => (
                  <option key={device.device_id} value={device.ip}>
                    {device.hostname || device.ip} ({device.ip})
                  </option>
                ))}
              </select>
            </div>
            {configsSutIp && (
              <div className="text-sm text-gray-500">
                Showing installation status for each game on {configsSutIp}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Content based on view mode */}
      {viewMode === 'configs' ? (
        // Game Configs View
        loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {[...Array(6)].map((_, i) => (
              <div key={i} className="bg-white rounded-lg border border-gray-200 p-4 animate-pulse">
                <div className="h-4 bg-gray-200 rounded w-2/3 mb-4"></div>
                <div className="h-3 bg-gray-200 rounded w-1/2 mb-2"></div>
                <div className="h-3 bg-gray-200 rounded w-1/3"></div>
              </div>
            ))}
          </div>
        ) : gamesList.length === 0 ? (
          <div className="text-center py-12 bg-white rounded-lg border border-gray-200">
            <p className="text-gray-500">No games configured</p>
            <p className="text-sm text-gray-400 mt-2">
              Add game configurations to the config directory
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {gamesList.map((game) => (
              <GameCard
                key={game.name}
                game={game}
                onSelect={setSelectedGame}
                onRun={handleRunGame}
                isSelected={selectedGame?.name === game.name}
                disabled={onlineDevices.length === 0}
                sutIp={configsSutIp}
                campaignMode={campaignMode}
                isCampaignSelected={selectedCampaignGames.has(game.name)}
                onCampaignToggle={handleCampaignToggle}
              />
            ))}
          </div>
        )
      ) : (
        // Installed Games View
        !selectedSutIp ? (
          <div className="text-center py-12 bg-white rounded-lg border border-gray-200">
            <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z" />
            </svg>
            <p className="mt-4 text-gray-500">Select a SUT to view installed games</p>
            <p className="text-sm text-gray-400 mt-2">
              Games will be enriched with preset availability information
            </p>
          </div>
        ) : loadingInstalled ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {[...Array(6)].map((_, i) => (
              <div key={i} className="bg-white rounded-lg border border-gray-200 p-4 animate-pulse">
                <div className="h-4 bg-gray-200 rounded w-2/3 mb-4"></div>
                <div className="h-3 bg-gray-200 rounded w-1/2 mb-2"></div>
                <div className="h-3 bg-gray-200 rounded w-1/3"></div>
              </div>
            ))}
          </div>
        ) : installedGames?.error ? (
          <div className="text-center py-12 bg-red-50 rounded-lg border border-red-200">
            <p className="text-red-700">{installedGames.error}</p>
          </div>
        ) : installedGames?.games.length === 0 ? (
          <div className="text-center py-12 bg-white rounded-lg border border-gray-200">
            <p className="text-gray-500">No games installed on this SUT</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {installedGames?.games.map((game) => (
              <InstalledGameCard
                key={game.steam_app_id || game.name}
                game={game}
                onRun={(presetShortName) => {
                  // Find matching game config and open run modal
                  const config = gamesList.find(g =>
                    g.name.toLowerCase().includes(presetShortName.toLowerCase().replace(/-/g, ' ')) ||
                    presetShortName.toLowerCase().includes(g.name.toLowerCase().replace(/ /g, '-'))
                  );
                  if (config) {
                    setSelectedGame(config);
                    setShowRunModal(true);
                  }
                }}
              />
            ))}
          </div>
        )
      )}

      {/* Run Modal */}
      {showRunModal && selectedGame && (
        <RunGameModal
          game={selectedGame}
          devices={onlineDevices}
          preSelectedSut={selectedSutIp}
          onClose={() => {
            setShowRunModal(false);
            setSelectedGame(null);
          }}
        />
      )}

      {/* Campaign Modal */}
      {showCampaignModal && (
        <CampaignModal
          selectedGames={Array.from(selectedCampaignGames)}
          devices={onlineDevices}
          onClose={() => setShowCampaignModal(false)}
          onRemoveGame={(gameName) => handleCampaignToggle(gameName, false)}
          onSuccess={(campaignId) => {
            // Clear selection and exit campaign mode after successful creation
            handleExitCampaignMode();
            // Could navigate to runs page or show success message
            console.log(`Campaign ${campaignId} created successfully`);
          }}
        />
      )}
    </div>
  );
}

// Component for displaying installed games with rich info
interface InstalledGameCardProps {
  game: InstalledGameInfo;
  onRun: (presetShortName: string) => void;
}

function InstalledGameCard({ game, onRun }: InstalledGameCardProps) {
  return (
    <div className={`bg-white rounded-lg border p-4 ${
      game.has_presets ? 'border-green-300 ring-1 ring-green-100' : 'border-gray-200'
    }`}>
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-gray-900 truncate" title={game.name}>
            {game.name}
          </h3>
          {game.steam_app_id && (
            <p className="text-xs text-gray-500">
              Steam App ID: {game.steam_app_id}
            </p>
          )}
        </div>
        {game.has_presets ? (
          <span className="ml-2 px-2 py-0.5 text-xs font-medium bg-green-100 text-green-700 rounded-full">
            Presets
          </span>
        ) : (
          <span className="ml-2 px-2 py-0.5 text-xs font-medium bg-gray-100 text-gray-500 rounded-full">
            No Presets
          </span>
        )}
      </div>

      {/* Install Path */}
      <div className="mb-3">
        <p className="text-xs text-gray-500 truncate" title={game.install_path || undefined}>
          {game.install_path || 'Path unknown'}
        </p>
      </div>

      {/* Preset Info */}
      {game.has_presets && (
        <div className="mb-3 p-2 bg-green-50 rounded-lg">
          <p className="text-xs font-medium text-green-700 mb-1">
            Matched via: {game.matched_by}
          </p>
          <p className="text-xs text-green-600">
            Preset: {game.preset_short_name}
          </p>
          <div className="flex flex-wrap gap-1 mt-1">
            {game.available_preset_levels.map((level) => (
              <span key={level} className="px-1.5 py-0.5 text-xs bg-green-200 text-green-800 rounded">
                {level}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Actions */}
      {game.has_presets && game.preset_short_name && (
        <button
          onClick={() => onRun(game.preset_short_name!)}
          className="w-full px-3 py-2 bg-green-500 text-white text-sm font-medium rounded-lg hover:bg-green-600"
        >
          Run Automation
        </button>
      )}
    </div>
  );
}

interface RunGameModalProps {
  game: GameConfig;
  devices: SUT[];
  preSelectedSut?: string;
  onClose: () => void;
}

function RunGameModal({ game, devices, preSelectedSut, onClose }: RunGameModalProps) {
  const [selectedDevice, setSelectedDevice] = useState(preSelectedSut || '');
  const [iterations, setIterations] = useState(1);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [installedInfo, setInstalledInfo] = useState<InstalledGameInfo | null>(null);
  const [checkingAvailability, setCheckingAvailability] = useState(false);

  // Preset matrix state
  const [selectedQuality, setSelectedQuality] = useState<QualityLevel | null>(null);
  const [selectedResolution, setSelectedResolution] = useState<Resolution | null>(null);
  const [presetMatrix, setPresetMatrix] = useState<PresetAvailability>({});
  const [loadingMatrix, setLoadingMatrix] = useState(false);
  const [preflightPassed, setPreflightPassed] = useState(false);
  const [manualPresetOverride, setManualPresetOverride] = useState(false);

  // SUT display resolution state
  const [sutResolutions, setSutResolutions] = useState<SutDisplayResolution[]>([]);
  const [loadingSutResolutions, setLoadingSutResolutions] = useState(false);

  // Get the selected SUT object
  const selectedSut = devices.find(d => d.ip === selectedDevice) || null;

  // Derive game slug from game name (simple conversion)
  const gameSlug = installedInfo?.preset_short_name || game.name.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, '');

  // Get selected device info (stable reference via useMemo pattern)
  const selectedDeviceInfo = devices.find(d => d.ip === selectedDevice);
  const selectedDevicePort = selectedDeviceInfo?.port || 8080;
  const selectedDeviceId = selectedDeviceInfo?.device_id;

  // Check game availability when device is selected
  useEffect(() => {
    if (!selectedDevice) {
      setInstalledInfo(null);
      return;
    }

    const checkAvailability = async () => {
      setCheckingAvailability(true);
      setError(null);
      try {
        const result = await getSutInstalledGames(selectedDevice, selectedDevicePort);
        if (!result.online) {
          setError('SUT is offline');
          setInstalledInfo(null);
          return;
        }

        // Preset-manager already enriches games with has_presets and preset_short_name
        // Find game by matching preset_short_name to our game config name
        const gameNameSlug = game.name.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, '');

        const found = result.games.find(g => {
          if (!g.has_presets || !g.preset_short_name) return false;
          // Match if preset_short_name matches the game name slug
          return g.preset_short_name === gameNameSlug;
        });

        if (found) {
          setInstalledInfo(found);
        } else {
          setError('Game not installed on selected SUT');
          setInstalledInfo(null);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to check availability');
        setInstalledInfo(null);
      } finally {
        setCheckingAvailability(false);
      }
    };

    checkAvailability();
  }, [selectedDevice, selectedDevicePort, game.name]);

  // Fetch SUT display resolutions when device is selected
  useEffect(() => {
    if (!selectedDevice || !selectedDeviceId) {
      setSutResolutions([]);
      return;
    }

    const fetchSutResolutions = async () => {
      setLoadingSutResolutions(true);
      try {
        // Use device_id for the resolution API
        const response = await getSutResolutions(selectedDeviceId);
        setSutResolutions(response.resolutions || []);
      } catch (err) {
        console.error('Failed to fetch SUT resolutions:', err);
        // Fall back to common resolutions if fetch fails
        setSutResolutions([
          { width: 1920, height: 1080, name: '1080p' },
          { width: 2560, height: 1440, name: '1440p' },
          { width: 3840, height: 2160, name: '4K' },
        ]);
      } finally {
        setLoadingSutResolutions(false);
      }
    };

    fetchSutResolutions();
  }, [selectedDevice, selectedDeviceId]);

  // Fetch preset matrix when game is found
  useEffect(() => {
    if (!installedInfo?.preset_short_name) {
      setPresetMatrix({});
      return;
    }

    const fetchMatrix = async () => {
      setLoadingMatrix(true);
      try {
        const matrix = await getPresetMatrix(installedInfo.preset_short_name!);
        // Cast string[] to Resolution[] since API returns string format
        const presets: PresetAvailability = {};
        for (const [quality, resolutions] of Object.entries(matrix.available_presets)) {
          presets[quality] = resolutions as Resolution[];
        }
        setPresetMatrix(presets);
        // Set defaults if available
        if (matrix.default_quality && matrix.default_resolution) {
          setSelectedQuality(matrix.default_quality as QualityLevel);
          setSelectedResolution(matrix.default_resolution as Resolution);
        }
      } catch (err) {
        console.error('Failed to fetch preset matrix:', err);
        // Fall back to simple structure from installed info
        const levels = installedInfo.available_preset_levels;
        const matrix: PresetAvailability = {};
        for (const level of levels) {
          const [quality, resolution] = level.split('-');
          if (quality && resolution) {
            if (!matrix[quality]) matrix[quality] = [];
            matrix[quality].push(resolution as Resolution);
          }
        }
        setPresetMatrix(matrix);
        // Default to high-1080p if available
        if (matrix['high']?.includes('1080p')) {
          setSelectedQuality('high');
          setSelectedResolution('1080p');
        }
      } finally {
        setLoadingMatrix(false);
      }
    };

    fetchMatrix();
  }, [installedInfo?.preset_short_name]);

  const handleStart = async () => {
    if (!selectedDevice || !installedInfo?.has_presets || !selectedQuality || !selectedResolution) return;

    setStarting(true);
    setError(null);

    try {
      // Pass quality and resolution to startRun
      await startRun(selectedDevice, game.name, iterations, selectedQuality, selectedResolution);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start run');
    } finally {
      setStarting(false);
    }
  };

  // Allow starting if preflight passed OR if user acknowledged manual preset override
  const canStart = selectedDevice && installedInfo?.has_presets && selectedQuality && selectedResolution && (preflightPassed || manualPresetOverride) && !starting && !checkingAvailability;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4 overflow-y-auto">
      <div className="bg-white rounded-lg p-6 max-w-3xl w-full my-4">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-bold text-gray-900">
            Run {game.display_name || game.name}
          </h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {error && (
          <div className="mb-4 p-3 bg-red-50 text-red-700 rounded-lg text-sm">
            {error}
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Left Column - Configuration */}
          <div className="space-y-4">
            {/* SUT Selection */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Select SUT
              </label>
              <select
                value={selectedDevice}
                onChange={(e) => setSelectedDevice(e.target.value)}
                className="w-full rounded-lg border border-gray-300 px-3 py-2"
              >
                <option value="">Choose a device...</option>
                {devices.map((device) => (
                  <option key={device.device_id} value={device.ip}>
                    {device.hostname || device.ip} ({device.ip})
                  </option>
                ))}
              </select>
            </div>

            {/* Game Info from SUT */}
            {selectedDevice && (
              <div className={`p-3 rounded-lg text-sm ${
                checkingAvailability
                  ? 'bg-gray-50'
                  : installedInfo?.has_presets
                  ? 'bg-green-50 border border-green-200'
                  : installedInfo
                  ? 'bg-yellow-50 border border-yellow-200'
                  : 'bg-red-50 border border-red-200'
              }`}>
                {checkingAvailability ? (
                  <div className="flex items-center gap-2 text-gray-600">
                    <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                    </svg>
                    Checking game availability...
                  </div>
                ) : installedInfo ? (
                  <div className="flex items-center gap-2">
                    {installedInfo.has_presets ? (
                      <svg className="h-5 w-5 text-green-600 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                      </svg>
                    ) : (
                      <svg className="h-5 w-5 text-yellow-600 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                      </svg>
                    )}
                    <span className={installedInfo.has_presets ? 'text-green-700' : 'text-yellow-700'}>
                      {installedInfo.name} — {installedInfo.has_presets ? 'Ready' : 'No presets'}
                    </span>
                  </div>
                ) : (
                  <div className="flex items-center gap-2 text-red-700">
                    <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                    Game not installed on this SUT
                  </div>
                )}
              </div>
            )}

            {/* Preset Matrix */}
            {installedInfo?.has_presets && (
              <div>
                {loadingMatrix ? (
                  <div className="p-4 bg-gray-50 rounded-lg text-center text-gray-500">
                    Loading preset options...
                  </div>
                ) : (
                  <PresetMatrix
                    gameName={game.display_name || game.name}
                    availablePresets={presetMatrix}
                    selectedQuality={selectedQuality}
                    selectedResolution={selectedResolution}
                    onSelect={(quality, resolution) => {
                      setSelectedQuality(quality);
                      setSelectedResolution(resolution);
                      setManualPresetOverride(false); // Reset override when selection changes
                    }}
                    disabled={!installedInfo?.has_presets}
                    sutResolutions={sutResolutions}
                    loadingSutResolutions={loadingSutResolutions}
                  />
                )}
              </div>
            )}

            {/* Iterations */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Iterations
              </label>
              <input
                type="number"
                min="1"
                max="100"
                value={iterations}
                onChange={(e) => setIterations(parseInt(e.target.value) || 1)}
                className="w-full rounded-lg border border-gray-300 px-3 py-2"
              />
            </div>
          </div>

          {/* Right Column - Preflight Checks */}
          <div>
            <PreflightChecks
              sut={selectedSut}
              gameName={game.display_name || game.name}
              gameSlug={gameSlug}
              quality={selectedQuality}
              resolution={selectedResolution}
              onAllChecksPassed={setPreflightPassed}
              autoRun={true}
            />
          </div>
        </div>

        {/* Manual Override Option - shown when preflight fails but selections are made */}
        {!preflightPassed && selectedDevice && selectedQuality && selectedResolution && (
          <div className="mt-4 p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
            <label className="flex items-start gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={manualPresetOverride}
                onChange={(e) => setManualPresetOverride(e.target.checked)}
                className="mt-0.5 h-4 w-4 rounded border-gray-300 text-yellow-600 focus:ring-yellow-500"
              />
              <div>
                <span className="text-sm font-medium text-yellow-800">
                  I've configured the preset manually
                </span>
                <p className="text-xs text-yellow-600 mt-0.5">
                  Check this to override preflight failures and start automation anyway.
                  Make sure the game settings are configured correctly on the SUT.
                </p>
              </div>
            </label>
          </div>
        )}

        {/* Actions */}
        <div className="flex gap-3 mt-6 pt-4 border-t border-gray-200">
          <button
            onClick={onClose}
            className="flex-1 px-4 py-2 border border-gray-300 rounded-lg text-gray-700 font-medium hover:bg-gray-50"
          >
            Cancel
          </button>
          <button
            onClick={handleStart}
            disabled={!canStart}
            className="flex-1 px-4 py-2 bg-green-500 text-white rounded-lg font-medium hover:bg-green-600 disabled:bg-gray-300 disabled:cursor-not-allowed"
          >
            {starting ? 'Starting...' : `Start Automation (${selectedQuality || '?'} @ ${selectedResolution || '?'})`}
          </button>
        </div>
      </div>
    </div>
  );
}
