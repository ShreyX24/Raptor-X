import type {
  DevicesResponse,
  GamesResponse,
  RunsResponse,
  RunsStats,
  SystemStatus,
  SUT,
  AutomationRun,
  SutDisplayResolutionsResponse,
} from '../types';
import { TIMEOUTS } from '../config';

const API_BASE = '/api';
const DISCOVERY_API = '/discovery-api';  // Proxied to discovery service (localhost:5001/api)

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = 'ApiError';
  }
}

class TimeoutError extends Error {
  constructor(url: string, timeout: number) {
    super(`Request to ${url} timed out after ${timeout}ms`);
    this.name = 'TimeoutError';
  }
}

interface FetchOptions extends RequestInit {
  timeout?: number;
}

async function fetchWithTimeout(url: string, options: FetchOptions = {}): Promise<Response> {
  const { timeout = TIMEOUTS.default, ...fetchOptions } = options;

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeout);

  try {
    const response = await fetch(url, {
      ...fetchOptions,
      signal: controller.signal,
    });
    return response;
  } catch (error) {
    if (error instanceof Error && error.name === 'AbortError') {
      throw new TimeoutError(url, timeout);
    }
    throw error;
  } finally {
    clearTimeout(timeoutId);
  }
}

async function fetchJson<T>(url: string, options?: FetchOptions): Promise<T> {
  const response = await fetchWithTimeout(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ error: response.statusText }));
    throw new ApiError(response.status, error.error || response.statusText);
  }

  return response.json();
}

// System APIs
export async function getSystemStatus(): Promise<SystemStatus> {
  return fetchJson<SystemStatus>(`${API_BASE}/status`);
}

export async function getHealth(): Promise<{ status: string }> {
  return fetchJson<{ status: string }>(`${API_BASE}/health`);
}

// Device/SUT APIs
export async function getDevices(): Promise<DevicesResponse> {
  return fetchJson<DevicesResponse>(`${API_BASE}/devices`);
}

export async function getDevice(deviceId: string): Promise<SUT> {
  return fetchJson<SUT>(`${API_BASE}/devices/${deviceId}`);
}

export async function getPairedSuts(): Promise<{ paired_suts: SUT[]; count: number }> {
  return fetchJson<{ paired_suts: SUT[]; count: number }>(`${API_BASE}/suts/paired`);
}

export async function pairSut(deviceId: string, pairedBy: string = 'user'): Promise<{ status: string }> {
  return fetchJson<{ status: string }>(`${API_BASE}/suts/pair`, {
    method: 'POST',
    body: JSON.stringify({ device_id: deviceId, paired_by: pairedBy }),
  });
}

export async function unpairSut(deviceId: string): Promise<{ status: string }> {
  return fetchJson<{ status: string }>(`${API_BASE}/suts/unpair/${deviceId}`, {
    method: 'POST',
  });
}

// Discovery APIs
export async function triggerDiscoveryScan(): Promise<{ status: string; scan_result: unknown }> {
  return fetchJson<{ status: string; scan_result: unknown }>(`${API_BASE}/discovery/scan`, {
    method: 'POST',
  });
}

export async function getDiscoveryStatus(): Promise<unknown> {
  return fetchJson<unknown>(`${API_BASE}/discovery/status`);
}

// Game APIs
export async function getGames(): Promise<GamesResponse> {
  return fetchJson<GamesResponse>(`${API_BASE}/games`);
}

export async function getGame(gameName: string): Promise<{ game: unknown }> {
  return fetchJson<{ game: unknown }>(`${API_BASE}/games/${gameName}`);
}

export async function reloadGames(): Promise<unknown> {
  return fetchJson<unknown>(`${API_BASE}/games/reload`, {
    method: 'POST',
  });
}

export interface GameAvailabilityResult {
  available: boolean;
  game_name: string;
  steam_app_id: string | null;
  install_path?: string;
  sut_ip: string;
  match_method: 'steam_app_id' | 'name' | null;
  error?: string;
  installed_games_count?: number;
}

export async function checkGameAvailability(
  gameName: string,
  sutIp: string
): Promise<GameAvailabilityResult> {
  return fetchJson<GameAvailabilityResult>(
    `${API_BASE}/games/${encodeURIComponent(gameName)}/check-availability?sut_ip=${encodeURIComponent(sutIp)}`
  );
}

// Automation Run APIs
export async function getRuns(page: number = 1, perPage: number = 50): Promise<RunsResponse> {
  const params = new URLSearchParams();
  if (page > 1) params.set('page', page.toString());
  if (perPage !== 50) params.set('per_page', perPage.toString());
  const query = params.toString();
  return fetchJson<RunsResponse>(`${API_BASE}/runs${query ? `?${query}` : ''}`);
}

export async function getRun(runId: string): Promise<AutomationRun> {
  return fetchJson<AutomationRun>(`${API_BASE}/runs/${runId}`);
}

export async function startRun(
  sutIp: string,
  gameName: string,
  iterations: number = 1,
  quality?: string,   // 'low' | 'medium' | 'high' | 'ultra'
  resolution?: string, // '720p' | '1080p' | '1440p' | '2160p'
  skipSteamLogin: boolean = false  // If true, skip Steam account management (user pre-logged in)
): Promise<{ status: string; run_id: string; message: string }> {
  return fetchJson<{ status: string; run_id: string; message: string }>(`${API_BASE}/runs`, {
    method: 'POST',
    body: JSON.stringify({
      sut_ip: sutIp,
      game_name: gameName,
      iterations,
      quality,
      resolution,
      skip_steam_login: skipSteamLogin,
    }),
  });
}

export async function stopRun(runId: string, killGame: boolean = false): Promise<{ status: string; message: string; game_killed?: boolean }> {
  return fetchJson<{ status: string; message: string; game_killed?: boolean }>(`${API_BASE}/runs/${runId}/stop`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ kill_game: killGame }),
  });
}

export async function getRunsStats(): Promise<RunsStats> {
  return fetchJson<RunsStats>(`${API_BASE}/runs/stats`);
}

// Run Logs and Timeline APIs
export interface LogEntry {
  timestamp: string;
  level: 'info' | 'warning' | 'error' | 'debug';
  message: string;
}

export interface RunLogsResponse {
  logs: LogEntry[];
  run_id: string;
  total_count: number;
}

export interface TimelineEvent {
  event_id: string;
  event_type: string;
  message: string;
  status: string;
  timestamp: string;
  duration_ms: number | null;
  metadata: Record<string, unknown>;
  group: string;
  replaces_event_id: string | null;
}

export interface RunTimelineResponse {
  status: string;
  run_id: string;
  events: TimelineEvent[];
}

export async function getRunLogs(runId: string): Promise<RunLogsResponse> {
  return fetchJson<RunLogsResponse>(`${API_BASE}/runs/${runId}/logs`, {
    timeout: TIMEOUTS.default * 2, // Logs can be large, give more time
  });
}

export async function getRunTimeline(runId: string): Promise<RunTimelineResponse> {
  return fetchJson<RunTimelineResponse>(`${API_BASE}/runs/${runId}/timeline`);
}

// SUT Action APIs
export async function getSutStatus(deviceId: string): Promise<unknown> {
  return fetchJson<unknown>(`${API_BASE}/sut/${deviceId}/status`);
}

// System info from SUT - flat structure matching actual response
export interface SUTSystemInfo {
  cpu: { brand_string: string };
  gpu: { name: string };
  ram: { total_gb: number };
  os: { name: string; version: string; release: string; build: string };
  bios: { name: string; version: string };
  screen: { width: number; height: number };
  hostname: string;
  device_id: string;
}

// Backend response wraps data in 'data' field
interface SUTSystemInfoBackendResponse {
  data: SUTSystemInfo;
  status: string;
  response_time: number;
}

// Legacy type for backward compatibility
export interface SUTSystemInfoResponse {
  system_info: SUTSystemInfo;
  sut_ip: string;
  timestamp: string;
}

export async function getSutSystemInfo(deviceId: string): Promise<SUTSystemInfo | null> {
  try {
    const response = await fetchJson<SUTSystemInfoBackendResponse>(`${API_BASE}/sut/${deviceId}/system_info`, {
      timeout: TIMEOUTS.default,
    });
    return response.data || null;
  } catch {
    return null;
  }
}

export async function getSutSystemInfoByIp(ip: string): Promise<SUTSystemInfo | null> {
  try {
    const response = await fetchJson<SUTSystemInfoBackendResponse>(`${API_BASE}/sut/by-ip/${ip}/system_info`, {
      timeout: TIMEOUTS.default,
    });
    return response.data || null;
  } catch {
    return null;
  }
}

export async function getSutSystemInfoViaProxy(deviceId: string): Promise<SUTSystemInfo | null> {
  // Go through discovery service proxy to avoid CORS
  try {
    const response = await fetchWithTimeout(`${DISCOVERY_API}/suts/${deviceId}/health`, {
      timeout: TIMEOUTS.default,
    });
    if (!response.ok) return null;
    const data = await response.json();
    // The health endpoint returns system info
    return data as SUTSystemInfo;
  } catch {
    return null;
  }
}

export interface InstalledGame {
  name: string;
  steam_app_id?: string | number;
  install_path?: string;
  exists?: boolean;
}

export interface InstalledGamesResponse {
  games: InstalledGame[];
  count: number;
}

export async function getSutInstalledGames(sutIp: string): Promise<InstalledGamesResponse> {
  // Direct call to SUT client (may fail due to CORS)
  const response = await fetchWithTimeout(`http://${sutIp}:8080/installed_games`, {
    timeout: TIMEOUTS.default,
  });
  if (!response.ok) {
    throw new ApiError(response.status, 'Failed to get installed games');
  }
  return response.json();
}

export async function getSutInstalledGamesViaProxy(deviceId: string): Promise<InstalledGamesResponse> {
  // Go through discovery service proxy to avoid CORS
  const response = await fetchWithTimeout(`${DISCOVERY_API}/suts/${deviceId}/games`, {
    timeout: TIMEOUTS.default,
  });
  if (!response.ok) {
    throw new ApiError(response.status, 'Failed to get installed games via proxy');
  }
  return response.json();
}

export async function takeSutScreenshot(deviceId: string): Promise<Blob> {
  const response = await fetchWithTimeout(`${API_BASE}/sut/${deviceId}/screenshot`, {
    timeout: TIMEOUTS.screenshot,
  });
  if (!response.ok) {
    throw new ApiError(response.status, 'Failed to take screenshot');
  }
  return response.blob();
}

export async function launchApplication(
  deviceId: string,
  path: string,
  processId?: string
): Promise<unknown> {
  return fetchJson<unknown>(`${API_BASE}/sut/${deviceId}/launch`, {
    method: 'POST',
    body: JSON.stringify({ path, process_id: processId }),
  });
}

/**
 * Get supported display resolutions from a SUT
 * @param deviceId - Device ID or IP address
 * @param commonOnly - If true, only return common resolutions (720p, 1080p, 1440p, 4K)
 */
export async function getSutResolutions(
  deviceId: string,
  commonOnly: boolean = true
): Promise<SutDisplayResolutionsResponse> {
  const params = commonOnly ? '?common_only=true' : '';
  return fetchJson<SutDisplayResolutionsResponse>(
    `${API_BASE}/sut/${deviceId}/display/resolutions${params}`,
    { timeout: TIMEOUTS.default }
  );
}

// OmniParser APIs
export async function getOmniparserStatus(): Promise<unknown> {
  return fetchJson<unknown>(`${API_BASE}/omniparser/status`);
}

// WebSocket connection helper
export function createWebSocketConnection(
  onMessage: (event: MessageEvent) => void,
  onOpen?: () => void,
  onClose?: () => void,
  onError?: (error: Event) => void
): WebSocket {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${window.location.host}/socket.io/?EIO=4&transport=websocket`;

  const ws = new WebSocket(wsUrl);

  ws.onmessage = onMessage;
  if (onOpen) ws.onopen = onOpen;
  if (onClose) ws.onclose = onClose;
  if (onError) ws.onerror = onError;

  return ws;
}

// =====================================================================
// Campaign APIs (Multi-Game Runs)
// =====================================================================

export interface Campaign {
  campaign_id: string;
  name: string;
  sut_ip: string;
  sut_device_id: string;
  games: string[];
  iterations_per_game: number;
  status: 'queued' | 'running' | 'completed' | 'failed' | 'partially_completed' | 'stopped';
  run_ids: string[];
  progress: {
    total_games: number;
    completed_games: number;
    failed_games: number;
    current_game: string | null;
    current_game_index: number;
  };
  created_at: string;
  completed_at: string | null;
  error_message: string | null;
  runs?: AutomationRun[];  // Populated when fetching single campaign
}

export interface CreateCampaignResponse {
  status: string;
  campaign_id: string;
  name: string;
  run_ids: string[];
  total_games: number;
  iterations_per_game: number;
  campaign_status: string;
  message: string;
}

export interface CampaignsResponse {
  active: Campaign[];
  history: Campaign[];
}

export async function createCampaign(
  sutIp: string,
  games: string[],
  iterations: number = 1,
  name?: string,
  quality?: string,    // 'low' | 'medium' | 'high' | 'ultra'
  resolution?: string, // '720p' | '1080p' | '1440p' | '2160p'
  skipSteamLogin: boolean = false  // If true, skip Steam account management (user pre-logged in)
): Promise<CreateCampaignResponse> {
  return fetchJson<CreateCampaignResponse>(`${API_BASE}/campaigns`, {
    method: 'POST',
    body: JSON.stringify({
      sut_ip: sutIp,
      games,
      iterations,
      name,
      quality,
      resolution,
      skip_steam_login: skipSteamLogin,
    }),
  });
}

export async function getCampaigns(): Promise<CampaignsResponse> {
  return fetchJson<CampaignsResponse>(`${API_BASE}/campaigns`);
}

export async function getCampaign(campaignId: string): Promise<Campaign> {
  return fetchJson<Campaign>(`${API_BASE}/campaigns/${campaignId}`);
}

export async function stopCampaign(campaignId: string): Promise<{ status: string; message: string }> {
  return fetchJson<{ status: string; message: string }>(`${API_BASE}/campaigns/${campaignId}/stop`, {
    method: 'POST',
  });
}

export { ApiError, TimeoutError };

// Re-export service-specific APIs
export * from './queueService';
export * from './presetManager';
export * from './workflowBuilder';
