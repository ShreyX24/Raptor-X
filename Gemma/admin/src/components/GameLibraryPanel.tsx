/**
 * GameLibraryPanel - Netflix-style game grid for dashboard
 * Portrait cards (9:16 ratio) with multi-select for campaigns
 */

import { useState, useMemo, useEffect, useCallback } from 'react';
import { RefreshCw } from 'lucide-react';
import { getPresetGames } from '../api/presetManager';
import type { GameConfig } from '../types';

interface GameLibraryPanelProps {
  games: GameConfig[];
  selectedGames?: string[];
  installedGames?: string[];  // Games installed on selected SUT
  hasSutSelected?: boolean;   // Whether a SUT is selected
  onSelectGames: (gameNames: string[]) => void;
  onQuickRun?: (game: GameConfig) => void;
  className?: string;
}

type FilterType = 'all' | 'installed' | 'ppg' | 'spl' | 'ppg+spl';
type SortType = 'alphabetical' | 'selection' | 'benchmark';

// ============================================================
// Image Caching System - Avoid repeated 404s and network requests
// ============================================================

// Global cache for resolved image URLs (persists across re-renders)
const imageUrlCache = new Map<string, string | null>();
let prefetchInProgress = false;

// Get Steam library image URL (portrait format) - primary source
const getSteamLibraryUrl = (steamAppId: string | undefined): string | null => {
  if (!steamAppId) return null;
  return `https://steamcdn-a.akamaihd.net/steam/apps/${steamAppId}/library_600x900.jpg`;
};

// Get Steam header image URL (landscape format - fallback)
const getSteamHeaderUrl = (steamAppId: string | undefined): string | null => {
  if (!steamAppId) return null;
  return `https://steamcdn-a.akamaihd.net/steam/apps/${steamAppId}/header.jpg`;
};

// Check if a URL is valid (returns a promise that resolves to true/false)
const checkImageUrl = (url: string): Promise<boolean> => {
  return new Promise((resolve) => {
    const img = new Image();
    img.onload = () => resolve(true);
    img.onerror = () => resolve(false);
    // Set crossOrigin to handle CORS
    img.crossOrigin = 'anonymous';
    img.src = url;
    // Timeout after 5 seconds
    setTimeout(() => resolve(false), 5000);
  });
};

// Get the best available image URL for a game (with caching)
const getBestImageUrl = async (game: GameConfig): Promise<string | null> => {
  const cacheKey = game.name;

  // Return cached result if available
  if (imageUrlCache.has(cacheKey)) {
    return imageUrlCache.get(cacheKey) || null;
  }

  // Try Steam library image first (portrait, best for our cards)
  const steamLibraryUrl = getSteamLibraryUrl(game.steam_app_id);
  if (steamLibraryUrl) {
    const isValid = await checkImageUrl(steamLibraryUrl);
    if (isValid) {
      imageUrlCache.set(cacheKey, steamLibraryUrl);
      return steamLibraryUrl;
    }
  }

  // Try Steam header image (landscape, will be cropped)
  const steamHeaderUrl = getSteamHeaderUrl(game.steam_app_id);
  if (steamHeaderUrl) {
    const isValid = await checkImageUrl(steamHeaderUrl);
    if (isValid) {
      imageUrlCache.set(cacheKey, steamHeaderUrl);
      return steamHeaderUrl;
    }
  }

  // No valid image found
  imageUrlCache.set(cacheKey, null);
  return null;
};

// Prefetch images for a list of games (called once when component mounts)
const prefetchGameImages = async (games: GameConfig[]) => {
  if (prefetchInProgress) return;
  prefetchInProgress = true;

  // Process games in batches of 6 for parallel loading
  const batchSize = 6;
  for (let i = 0; i < games.length; i += batchSize) {
    const batch = games.slice(i, i + batchSize);
    await Promise.all(batch.map(game => getBestImageUrl(game)));
  }

  prefetchInProgress = false;
};

export function GameLibraryPanel({
  games,
  selectedGames = [],
  installedGames,
  hasSutSelected = false,
  onSelectGames,
  onQuickRun,
  className = '',
}: GameLibraryPanelProps) {
  const [filter, setFilter] = useState<FilterType>('all');
  const [sortBy, setSortBy] = useState<SortType>('alphabetical');
  const [searchQuery, setSearchQuery] = useState('');
  const [ppgGames, setPpgGames] = useState<Set<string>>(new Set());
  const [splGames, setSplGames] = useState<Set<string>>(new Set());
  const [reloading, setReloading] = useState(false);

  // Convert installedGames array to Set for fast lookup
  const installedSet = useMemo(() =>
    new Set(installedGames || []),
    [installedGames]
  );

  // Handle reload games
  const handleReloadGames = async () => {
    setReloading(true);
    try {
      await fetch('/api/games/reload', { method: 'POST' });
    } catch (error) {
      console.error('Reload failed:', error);
    } finally {
      setTimeout(() => setReloading(false), 1500);
    }
  };

  // SPL games list (hardcoded - CS2, Civ 6, Black Myth Wukong)
  // Neither PPG nor SPL: Dota 2
  const SPL_GAMES = new Set([
    'black-myth-wukong',
    'sid-meier-civ-6',
    'cs2',
    'counter-strike-2',
    'counter-strike2',
  ]);

  const NEITHER_GAMES = new Set([
    'dota-2',
    'dota2',
  ]);

  // Track image cache refresh
  const [imageCacheVersion, setImageCacheVersion] = useState(0);

  // Prefetch game images when games list changes
  useEffect(() => {
    if (games.length > 0) {
      // Start prefetching in background
      prefetchGameImages(games).then(() => {
        // Trigger re-render to show loaded images
        setImageCacheVersion(v => v + 1);
      });
    }
  }, [games]);

  // Fetch PPG/SPL classification from preset-manager
  useEffect(() => {
    const fetchPresetGames = async () => {
      try {
        const presetGames = await getPresetGames();
        const ppg = new Set<string>();
        const spl = new Set<string>();

        presetGames.forEach(pg => {
          const shortName = pg.short_name;

          // Check if it's an SPL game (hardcoded list)
          if (SPL_GAMES.has(shortName)) {
            spl.add(shortName);
          }
          // Check if it's neither PPG nor SPL
          else if (!NEITHER_GAMES.has(shortName)) {
            // All other games are PPG
            ppg.add(shortName);
          }
          // Games in NEITHER_GAMES are not added to either set
        });

        setPpgGames(ppg);
        setSplGames(spl);
      } catch (error) {
        console.error('Failed to fetch preset games:', error);
      }
    };

    fetchPresetGames();
  }, []);

  const filteredGames = useMemo(() => {
    let result = [...games];

    // Apply filter
    if (filter === 'installed') {
      result = result.filter(g => g.path && g.path.length > 0);
    } else if (filter === 'ppg') {
      result = result.filter(g => g.preset_id && ppgGames.has(g.preset_id));
    } else if (filter === 'spl') {
      result = result.filter(g => g.preset_id && splGames.has(g.preset_id));
    } else if (filter === 'ppg+spl') {
      result = result.filter(g => g.preset_id && (ppgGames.has(g.preset_id) || splGames.has(g.preset_id)));
    }

    // Apply search
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      result = result.filter(g =>
        g.name.toLowerCase().includes(query) ||
        (g.display_name && g.display_name.toLowerCase().includes(query))
      );
    }

    // Apply sorting
    if (sortBy === 'alphabetical') {
      result.sort((a, b) => (a.display_name || a.name).localeCompare(b.display_name || b.name));
    } else if (sortBy === 'selection') {
      // Selected games first, in selection order
      result.sort((a, b) => {
        const aSelected = selectedGames.indexOf(a.name);
        const bSelected = selectedGames.indexOf(b.name);
        if (aSelected >= 0 && bSelected >= 0) return aSelected - bSelected;
        if (aSelected >= 0) return -1;
        if (bSelected >= 0) return 1;
        return (a.display_name || a.name).localeCompare(b.display_name || b.name);
      });
    }
    // benchmark sorting would need benchmark time data - keep alphabetical as fallback

    return result;
  }, [games, filter, searchQuery, ppgGames, splGames, sortBy, selectedGames]);

  const filterCounts = useMemo(() => ({
    all: games.length,
    installed: games.filter(g => g.path && g.path.length > 0).length,
    ppg: games.filter(g => g.preset_id && ppgGames.has(g.preset_id)).length,
    spl: games.filter(g => g.preset_id && splGames.has(g.preset_id)).length,
    'ppg+spl': games.filter(g => g.preset_id && (ppgGames.has(g.preset_id) || splGames.has(g.preset_id))).length,
  }), [games, ppgGames, splGames]);

  // Check if a game is available for selection (installed on SUT or no SUT selected)
  const isGameAvailable = useCallback((game: GameConfig) => {
    if (!hasSutSelected) return true;  // No SUT selected = all games available
    if (!installedGames) return true;   // No installed info = assume available
    return installedSet.has(game.name);
  }, [hasSutSelected, installedGames, installedSet]);

  // Handle game click - toggle selection (only if available)
  const handleGameClick = (game: GameConfig) => {
    if (!isGameAvailable(game)) return; // Can't select unavailable games

    if (selectedGames.includes(game.name)) {
      // Already selected - remove from selection
      onSelectGames(selectedGames.filter(n => n !== game.name));
    } else {
      // Not selected - add to selection (order = selection order)
      onSelectGames([...selectedGames, game.name]);
    }
  };

  // Clear selection
  const handleClearSelection = () => {
    onSelectGames([]);
  };

  // Select all visible
  const handleSelectAll = () => {
    onSelectGames(filteredGames.map(g => g.name));
  };

  return (
    <div className={`bg-surface border border-border rounded-lg overflow-hidden flex flex-col min-h-[300px] ${className}`}>
      {/* Header with filters */}
      <div className="px-3 py-2 bg-surface-elevated/50 border-b border-border flex-shrink-0">
        {/* Top row: Title + Sort + Counts + Actions */}
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-3">
            <h3 className="text-sm font-semibold text-text-secondary uppercase tracking-wide">
              Game Library
            </h3>
            {/* Sort dropdown */}
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as SortType)}
              className="px-2 py-0.5 text-[10px] bg-surface border border-border rounded text-text-muted"
            >
              <option value="alphabetical">A-Z</option>
              <option value="selection">Selection Order</option>
            </select>
          </div>

          {/* Right side: Counts + Actions */}
          <div className="flex items-center gap-3">
            {/* Available | Selected counts */}
            <div className="flex items-center gap-2 text-xs">
              <span className="text-text-muted">
                Available: <span className="font-numbers text-text-secondary">{filteredGames.length}</span>
              </span>
              <span className="text-text-muted">|</span>
              <span className="text-text-muted">
                Selected: <span className={`font-numbers ${selectedGames.length > 0 ? 'text-primary font-medium' : 'text-text-secondary'}`}>{selectedGames.length}</span>
              </span>
            </div>

            {/* Action buttons */}
            <div className="flex items-center gap-1.5">
              <button
                onClick={handleSelectAll}
                className="px-2 py-0.5 text-[10px] text-text-muted hover:text-primary border border-border rounded hover:border-primary transition-colors"
              >
                Select All
              </button>
              <button
                onClick={handleClearSelection}
                disabled={selectedGames.length === 0}
                className="px-2 py-0.5 text-[10px] text-text-muted hover:text-danger border border-border rounded hover:border-danger transition-colors disabled:opacity-50"
              >
                Clear
              </button>
              <button
                onClick={handleReloadGames}
                disabled={reloading}
                className="p-1 text-text-muted hover:text-text-primary border border-border rounded transition-colors disabled:opacity-50"
                title="Reload game configs"
              >
                <RefreshCw className={`w-3 h-3 ${reloading ? 'animate-spin' : ''}`} />
              </button>
            </div>
          </div>
        </div>

        {/* Filter tabs + Search + Legend */}
        <div className="flex items-center gap-1 flex-wrap">
          {(['all', 'installed', 'ppg', 'spl', 'ppg+spl'] as FilterType[]).map((f) => {
            const getButtonStyles = () => {
              if (filter !== f) {
                return 'bg-surface-elevated text-text-muted hover:text-text-secondary';
              }
              if (f === 'ppg') return 'bg-emerald-500 text-white';
              if (f === 'spl') return 'bg-cyan-500 text-white';
              if (f === 'ppg+spl') return 'bg-gradient-to-r from-emerald-500 to-cyan-500 text-white';
              return 'bg-primary text-white';
            };

            return (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`px-2.5 py-1 text-xs font-medium rounded transition-colors uppercase ${getButtonStyles()}`}
              >
                {f === 'ppg+spl' ? 'PPG+SPL' : f}
                <span className="ml-1 font-numbers opacity-70">{filterCounts[f]}</span>
              </button>
            );
          })}

          {/* Search */}
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search..."
            className="ml-auto px-2 py-1 text-xs bg-surface border border-border rounded w-32 focus:w-40 transition-all focus:outline-none focus:border-primary"
          />

          {/* Legend for status dots */}
          <div className="flex items-center gap-3 ml-3 text-[10px] text-text-muted">
            <div className="flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-success" />
              <span>Preset</span>
            </div>
            <div className="flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-primary" />
              <span>Path</span>
            </div>
          </div>
        </div>
      </div>

      {/* Game Grid - Netflix style portrait cards */}
      <div className="flex-1 overflow-y-auto p-3">
        {filteredGames.length === 0 ? (
          <div className="text-center py-8 text-text-muted text-xs">
            No games found
          </div>
        ) : (
          <div className="grid grid-cols-4 sm:grid-cols-5 md:grid-cols-6 lg:grid-cols-8 xl:grid-cols-10 gap-3">
            {filteredGames.map((game) => (
              <NetflixGameCard
                key={game.name}
                game={game}
                isSelected={selectedGames.includes(game.name)}
                isAvailable={isGameAvailable(game)}
                isPpg={ppgGames.has(game.preset_id || '')}
                isSpl={splGames.has(game.preset_id || '')}
                onClick={() => handleGameClick(game)}
                onDoubleClick={() => isGameAvailable(game) && onQuickRun?.(game)}
                cacheVersion={imageCacheVersion}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * NetflixGameCard - Portrait game card (9:16 ratio)
 *
 * Status dots at bottom:
 * - Green dot = hasPreset (game has automation preset configured)
 * - Blue dot = hasPath (game executable path is set)
 */
interface NetflixGameCardProps {
  game: GameConfig;
  isSelected: boolean;
  isAvailable: boolean;  // Whether game is installed on selected SUT
  isPpg: boolean;
  isSpl: boolean;
  onClick: () => void;
  onDoubleClick?: () => void;
  cacheVersion?: number;  // Triggers re-render when cache updates
}

function NetflixGameCard({ game, isSelected, isAvailable, isPpg, isSpl, onClick, onDoubleClick, cacheVersion }: NetflixGameCardProps) {
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const hasPreset = !!game.preset_id;
  const hasPath = !!(game.path && game.path.length > 0);

  // Get cached image URL on mount and when cache updates
  useEffect(() => {
    // Check if already in cache
    const cached = imageUrlCache.get(game.name);
    if (cached !== undefined) {
      setImageUrl(cached);
      setIsLoading(false);
    } else {
      // Not in cache yet, load it
      setIsLoading(true);
      getBestImageUrl(game).then(url => {
        setImageUrl(url);
        setIsLoading(false);
      });
    }
  }, [game.name, game.steam_app_id, cacheVersion]);

  // Generate a color based on game name for placeholder
  const placeholderColor = useMemo(() => {
    let hash = 0;
    const name = game.name;
    for (let i = 0; i < name.length; i++) {
      hash = name.charCodeAt(i) + ((hash << 5) - hash);
    }
    const h = hash % 360;
    return `hsl(${h}, 40%, 25%)`;
  }, [game.name]);

  return (
    <button
      onClick={onClick}
      onDoubleClick={onDoubleClick}
      disabled={!isAvailable}
      title={`${game.display_name || game.name}${isPpg ? ' (PPG)' : ''}${isSpl ? ' (SPL)' : ''}${!isAvailable ? ' (Not installed on SUT)' : ''}`}
      className={`
        relative flex flex-col rounded-lg overflow-hidden transition-all group
        aspect-[9/16] w-full
        ${!isAvailable
          ? 'opacity-40 cursor-not-allowed grayscale'
          : isSelected
            ? 'ring-2 ring-primary ring-offset-1 ring-offset-background'
            : 'hover:ring-1 hover:ring-border-hover'
        }
      `}
    >
      {/* Background Image or Placeholder */}
      <div
        className="absolute inset-0 bg-cover bg-center"
        style={{
          backgroundColor: placeholderColor,
        }}
      >
        {/* Loading shimmer effect */}
        {isLoading && (
          <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/10 to-transparent animate-shimmer" />
        )}
        {/* Game image */}
        {imageUrl && (
          <img
            src={imageUrl}
            alt={game.name}
            loading="lazy"
            className="w-full h-full object-cover"
          />
        )}
        {/* Placeholder text when no image */}
        {!imageUrl && !isLoading && (
          <div className="absolute inset-0 flex items-center justify-center">
            <span className="text-2xl font-bold text-white/50">
              {(game.display_name || game.name).charAt(0).toUpperCase()}
            </span>
          </div>
        )}
        {/* Gradient overlay for text readability */}
        <div className="absolute inset-0 bg-gradient-to-t from-black/90 via-black/30 to-transparent" />
      </div>

      {/* Selection indicator */}
      {isSelected && (
        <div className="absolute top-2 right-2 w-5 h-5 bg-primary rounded-full flex items-center justify-center z-10">
          <svg className="w-3 h-3 text-white" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
          </svg>
        </div>
      )}

      {/* Badges (top left) - PPG=green/lime, SPL=cyan (matching preset-manager) */}
      <div className="absolute top-2 left-2 flex flex-col gap-1 z-10">
        {isPpg && (
          <span className="px-1.5 py-0.5 text-[8px] bg-emerald-500/90 text-white rounded font-bold shadow-sm">
            PPG
          </span>
        )}
        {isSpl && (
          <span className="px-1.5 py-0.5 text-[8px] bg-cyan-500/90 text-white rounded font-bold shadow-sm">
            SPL
          </span>
        )}
      </div>

      {/* Content at bottom */}
      <div className="relative mt-auto p-2 z-10">
        {/* Game name */}
        <div className="text-xs font-medium text-white leading-tight line-clamp-2 mb-1">
          {game.display_name || game.name}
        </div>

        {/* Status indicators - Green: has preset_id (automation config), Blue: has path (local install detected) */}
        <div className="flex items-center gap-1">
          {hasPreset && (
            <span className="w-1.5 h-1.5 rounded-full bg-success" title="Automation preset configured (preset_id)" />
          )}
          {hasPath && (
            <span className="w-1.5 h-1.5 rounded-full bg-primary" title="Local installation path detected" />
          )}
        </div>
      </div>

      {/* Hover overlay with quick actions */}
      <div className="absolute inset-0 bg-primary/0 group-hover:bg-primary/10 transition-colors" />
    </button>
  );
}

/**
 * GameListItem - Larger list item variant (for alternate views)
 */
interface GameListItemProps {
  game: GameConfig;
  isSelected: boolean;
  onClick: () => void;
  onRun?: () => void;
}

export function GameListItem({ game, isSelected, onClick, onRun }: GameListItemProps) {
  return (
    <div
      onClick={onClick}
      className={`
        flex items-center justify-between px-3 py-2 rounded-lg cursor-pointer transition-all
        ${isSelected
          ? 'bg-primary/20 border border-primary'
          : 'bg-surface-elevated border border-transparent hover:bg-surface-hover'
        }
      `}
    >
      <div className="flex items-center gap-2 min-w-0">
        <span className="text-sm font-medium text-text-primary truncate">
          {game.display_name || game.name}
        </span>
        {game.preset_id && (
          <span className="px-1.5 py-0.5 text-[10px] bg-success/20 text-success rounded">
            Preset
          </span>
        )}
      </div>

      {onRun && (
        <button
          onClick={(e) => {
            e.stopPropagation();
            onRun();
          }}
          className="px-2 py-1 text-xs bg-primary/20 text-primary rounded hover:bg-primary/30 transition-colors"
        >
          Run
        </button>
      )}
    </div>
  );
}
