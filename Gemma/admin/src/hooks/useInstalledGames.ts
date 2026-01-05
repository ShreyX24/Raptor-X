/**
 * useInstalledGames - Shared hook for fetching and matching installed games on a SUT
 *
 * Contains the sophisticated 6-strategy game matching algorithm used by both
 * desktop Dashboard and MobileDashboard.
 */

import { useState, useEffect, useCallback } from 'react';
import { getSutInstalledGamesViaProxy } from '../api';
import type { GameConfig } from '../types';

interface UseInstalledGamesResult {
  /** Array of matched game config names (e.g., ['far-cry-6', 'cyberpunk-2077']) */
  installedGames: string[] | null;
  /** Loading state */
  loading: boolean;
  /** Error message if fetch failed */
  error: string | null;
  /** Check if a specific game is installed */
  isGameInstalled: (game: GameConfig) => boolean | null;
  /** Refetch installed games */
  refetch: () => void;
}

/**
 * Fetches installed games from a SUT and matches them to game configs
 * using a sophisticated multi-strategy matching algorithm.
 *
 * @param deviceId - The SUT device ID to fetch games from
 * @param gamesList - Array of game configs to match against
 */
export function useInstalledGames(
  deviceId: string | undefined,
  gamesList: GameConfig[]
): UseInstalledGamesResult {
  const [installedGames, setInstalledGames] = useState<string[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchInstalledGames = useCallback(async () => {
    if (!deviceId) {
      setInstalledGames(null);
      setLoading(false);
      setError(null);
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

    setLoading(true);
    setError(null);

    try {
      // Use proxy via discovery service to avoid CORS
      const response = await getSutInstalledGamesViaProxy(deviceId);
      console.log('[useInstalledGames] Installed games from SUT:', response.games);

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
            'tina': ['tiny tina', 'tiny-tina'],
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

      console.log('[useInstalledGames] Matched games:', installedNames, `(${installedNames.length}/${response.games.length})`);
      setInstalledGames(installedNames);
    } catch (err) {
      console.error('[useInstalledGames] Failed to fetch installed games:', err);
      // On error, set null so games are NOT grayed out (null = no data available)
      setInstalledGames(null);
      setError(err instanceof Error ? err.message : 'Failed to fetch installed games');
    } finally {
      setLoading(false);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [deviceId, gamesList.length]); // Use length to avoid re-fetch on array reference change

  // Fetch on mount and when deviceId or gamesList length changes
  useEffect(() => {
    fetchInstalledGames();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [deviceId, gamesList.length]);

  // Helper to check if a game is installed
  const isGameInstalled = useCallback((game: GameConfig): boolean | null => {
    if (installedGames === null) return null; // No data yet
    return installedGames.includes(game.name);
  }, [installedGames]);

  return {
    installedGames,
    loading,
    error,
    isGameInstalled,
    refetch: fetchInstalledGames,
  };
}
