/**
 * Preset Manager API Client
 * Connects to the Preset Manager service via Vite proxy (/preset-api -> localhost:5002)
 */

import type { PresetGame, PresetLevel, SyncStats, SyncResult, BackupInfo } from '../types';

// Use proxy path for cross-device compatibility (mobile, desktop)
const PRESET_MANAGER_URL = '/preset-api';

class PresetManagerError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = 'PresetManagerError';
  }
}

async function fetchPresetJson<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${PRESET_MANAGER_URL}${endpoint}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ error: response.statusText }));
    throw new PresetManagerError(response.status, error.detail || error.error || response.statusText);
  }

  return response.json();
}

// ============================================
// SUT Installed Games API
// ============================================

export interface InstalledGameInfo {
  name: string;
  steam_app_id: string | null;
  install_path: string | null;
  install_dir: string | null;
  exists: boolean;
  has_presets: boolean;
  preset_short_name: string | null;
  available_preset_levels: string[];
  matched_by: 'steam_app_id' | 'name' | null;
}

export interface SutInstalledGamesResponse {
  sut_ip: string;
  sut_port: number;
  online: boolean;
  games: InstalledGameInfo[];
  games_count: number;
  games_with_presets: number;
  libraries_scanned: number | null;
  error: string | null;
}

/**
 * Get all installed games from a SUT with preset availability info
 */
export async function getSutInstalledGames(sutIp: string, port: number = 8080): Promise<SutInstalledGamesResponse> {
  const params = new URLSearchParams();
  // Always pass the port to backend
  params.set('port', port.toString());
  const queryString = params.toString();
  return fetchPresetJson<SutInstalledGamesResponse>(
    `/api/sync/sut-games/${encodeURIComponent(sutIp)}?${queryString}`
  );
}

// ============================================
// Games API
// ============================================

/**
 * Get all games with preset information
 */
export async function getPresetGames(options?: {
  skip?: number;
  limit?: number;
  enabledOnly?: boolean;
  search?: string;
}): Promise<PresetGame[]> {
  const params = new URLSearchParams();
  if (options?.skip) params.set('skip', options.skip.toString());
  if (options?.limit) params.set('limit', options.limit.toString());
  if (options?.enabledOnly !== undefined) params.set('enabled_only', options.enabledOnly.toString());
  if (options?.search) params.set('search', options.search);

  const queryString = params.toString();
  return fetchPresetJson<PresetGame[]>(`/api/games${queryString ? `?${queryString}` : ''}`);
}

/**
 * Get game statistics
 */
export async function getGameStats(): Promise<{
  total_games: number;
  enabled_games: number;
  disabled_games: number;
  total_presets: number;
  total_suts: number;
  total_syncs: number;
}> {
  return fetchPresetJson('/api/games/stats');
}

/**
 * Get preset levels for a specific game
 */
export async function getGamePresets(gameSlug: string): Promise<{
  game_slug: string;
  game_name: string;
  preset_count: number;
  presets: PresetLevel[];
}> {
  return fetchPresetJson(`/api/games/${encodeURIComponent(gameSlug)}/presets`);
}

// ============================================
// Sync API
// ============================================

/**
 * Get sync statistics
 */
export async function getSyncStats(): Promise<SyncStats> {
  return fetchPresetJson<SyncStats>('/api/sync/stats');
}

/**
 * Push preset to specified SUTs
 */
export async function pushPreset(
  gameShortName: string,
  presetLevel: string,
  sutUniqueIds: string[]
): Promise<SyncResult> {
  return fetchPresetJson<SyncResult>('/api/sync/push', {
    method: 'POST',
    body: JSON.stringify({
      game_short_name: gameShortName,
      preset_level: presetLevel,
      sut_unique_ids: sutUniqueIds,
    }),
  });
}

/**
 * Bulk sync presets to multiple SUTs
 */
export async function bulkSync(
  operations: Array<{
    game_slug: string;
    preset_level: string;
    sut_unique_ids: string[];
  }>
): Promise<{
  total_operations: number;
  successful: number;
  failed: number;
  results: SyncResult[];
}> {
  return fetchPresetJson('/api/sync/bulk', {
    method: 'POST',
    body: JSON.stringify({ operations }),
  });
}

/**
 * Get sync history
 */
export async function getSyncHistory(): Promise<Array<{
  id: string;
  game_slug: string;
  preset_level: string;
  sut_id: string;
  status: 'success' | 'failed';
  timestamp: string;
  duration_ms: number;
}>> {
  return fetchPresetJson('/api/sync/history');
}

// ============================================
// Backup API
// ============================================

/**
 * Get all backups
 */
export async function getBackups(): Promise<{
  backups: Record<string, BackupInfo[]>;
  total_games: number;
  total_backups: number;
}> {
  return fetchPresetJson('/api/backups');
}

/**
 * Get backups for a specific game
 */
export async function getGameBackups(gameSlug: string): Promise<{
  game_slug: string;
  backups: BackupInfo[];
  total_backups: number;
}> {
  return fetchPresetJson(`/api/backups/${encodeURIComponent(gameSlug)}`);
}

/**
 * Rollback to a backup
 */
export async function rollbackToBackup(
  sutUniqueId: string,
  gameSlug: string,
  backupId?: string
): Promise<{
  status: string;
  message: string;
}> {
  return fetchPresetJson(`/api/sync/rollback/${encodeURIComponent(sutUniqueId)}`, {
    method: 'POST',
    body: JSON.stringify({
      game_slug: gameSlug,
      backup_id: backupId,
    }),
  });
}

/**
 * Cleanup old backups for a game
 */
export async function cleanupBackups(
  gameSlug: string,
  keepCount: number = 5
): Promise<{
  deleted_count: number;
  kept_count: number;
  message: string;
}> {
  return fetchPresetJson(`/api/backups/${encodeURIComponent(gameSlug)}/cleanup`, {
    method: 'POST',
    body: JSON.stringify({ keep_count: keepCount }),
  });
}

/**
 * Check if preset manager is available
 */
export async function isPresetManagerAvailable(): Promise<boolean> {
  try {
    await getSyncStats();
    return true;
  } catch {
    return false;
  }
}

// ============================================
// Preset Matrix API (Phase 1 - Quality × Resolution)
// ============================================

export interface PresetConstants {
  quality_levels: string[];
  resolutions: Record<string, { width: number; height: number; name: string }>;
  standard_levels: string[];
}

export interface PresetMatrixResponse {
  game_slug: string;
  game_name: string;
  default_quality: string;
  default_resolution: string;
  available_presets: Record<string, string[]>;  // quality -> resolutions[]
  total_available: number;
  total_placeholders: number;
}

export interface PresetMetadataResponse {
  quality: string;
  resolution: string;
  resolution_width: number;
  resolution_height: number;
  description?: string;
  target_gpu?: string;
  target_fps?: string;
  settings_summary?: Record<string, string>;
  files: string[];
  status: 'available' | 'placeholder';
  last_updated?: string;
}

/**
 * Get preset constants (quality levels, resolutions)
 */
export async function getPresetConstants(): Promise<PresetConstants> {
  return fetchPresetJson<PresetConstants>('/api/presets/constants');
}

/**
 * Get preset matrix for a game (available quality × resolution combinations)
 * Transforms API response to frontend-expected format
 */
export async function getPresetMatrix(gameSlug: string): Promise<PresetMatrixResponse> {
  // Raw API response has different structure
  interface RawMatrixResponse {
    game: string;
    quality_levels: string[];
    resolutions: string[];
    available: Record<string, Record<string, { exists: boolean; has_files: boolean; status: string }>>;
    default_quality: string;
    default_resolution: string;
  }

  const raw = await fetchPresetJson<RawMatrixResponse>(`/api/presets/${encodeURIComponent(gameSlug)}/matrix`);

  // Transform to frontend expected format
  const available_presets: Record<string, string[]> = {};
  let total_available = 0;
  let total_placeholders = 0;

  for (const quality of Object.keys(raw.available || {})) {
    available_presets[quality] = [];
    for (const resolution of Object.keys(raw.available[quality] || {})) {
      const preset = raw.available[quality][resolution];
      // Include if has_files (actual preset exists) - status "ready"
      if (preset.has_files || preset.status === 'ready') {
        available_presets[quality].push(resolution);
        total_available++;
      } else if (preset.exists) {
        total_placeholders++;
      }
    }
  }

  return {
    game_slug: raw.game,
    game_name: raw.game,
    default_quality: raw.default_quality,
    default_resolution: raw.default_resolution,
    available_presets,
    total_available,
    total_placeholders,
  };
}

/**
 * Get metadata for a specific quality/resolution preset
 */
export async function getPresetMetadata(
  gameSlug: string,
  quality: string,
  resolution: string
): Promise<PresetMetadataResponse> {
  return fetchPresetJson<PresetMetadataResponse>(
    `/api/presets/${encodeURIComponent(gameSlug)}/${encodeURIComponent(quality)}/${encodeURIComponent(resolution)}/metadata`
  );
}

export { PresetManagerError };
