/**
 * Admin API Client
 * Handles all admin panel API requests to /api/admin/*
 */

import type {
  AdminConfig,
  ServiceWithStatus,
  ServiceSettings,
  Profile,
  ProfilesResponse,
  OmniParserSettings,
  OmniParserTestResult,
  SteamAccountsResponse,
  SteamAccountPair,
  DiscoverySettings,
  AutomationSettings,
  GamesListResponse,
  GameYamlResponse,
  YamlValidationResult,
  ApiResponse,
  ApiResponseWithRestart,
  ServiceRestartResponse,
  GameCreateResponse,
  GameDeleteResponse,
  GameUpdateResponse,
} from '../types/admin';

const ADMIN_API_BASE = '/api/admin';
const DEFAULT_TIMEOUT = 10000;

class AdminApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = 'AdminApiError';
  }
}

interface FetchOptions extends RequestInit {
  timeout?: number;
}

async function fetchWithTimeout(url: string, options: FetchOptions = {}): Promise<Response> {
  const { timeout = DEFAULT_TIMEOUT, ...fetchOptions } = options;

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
      throw new Error(`Request to ${url} timed out after ${timeout}ms`);
    }
    throw error;
  } finally {
    clearTimeout(timeoutId);
  }
}

async function adminFetch<T>(
  endpoint: string,
  options: FetchOptions = {}
): Promise<T> {
  const url = `${ADMIN_API_BASE}${endpoint}`;
  const response = await fetchWithTimeout(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  });

  if (!response.ok) {
    let errorMessage = `HTTP ${response.status}`;
    try {
      const errorData = await response.json();
      errorMessage = errorData.error || errorMessage;
    } catch {
      // Ignore JSON parse errors
    }
    throw new AdminApiError(response.status, errorMessage);
  }

  return response.json();
}

// ============================================================================
// Configuration API
// ============================================================================

export async function getConfig(): Promise<AdminConfig> {
  return adminFetch<AdminConfig>('/config');
}

export async function updateConfig(updates: Partial<AdminConfig>): Promise<ApiResponse> {
  return adminFetch<ApiResponse>('/config', {
    method: 'PUT',
    body: JSON.stringify(updates),
  });
}

export async function resetConfig(): Promise<ApiResponse> {
  return adminFetch<ApiResponse>('/config/reset', {
    method: 'POST',
  });
}

// ============================================================================
// Services API
// ============================================================================

export async function getServices(): Promise<Record<string, ServiceWithStatus>> {
  return adminFetch<Record<string, ServiceWithStatus>>('/services');
}

export async function getService(name: string): Promise<ServiceWithStatus> {
  return adminFetch<ServiceWithStatus>(`/services/${encodeURIComponent(name)}`);
}

export async function updateService(
  name: string,
  settings: Partial<ServiceSettings>
): Promise<ApiResponse> {
  return adminFetch<ApiResponse>(`/services/${encodeURIComponent(name)}`, {
    method: 'PUT',
    body: JSON.stringify(settings),
  });
}

export async function restartService(name: string): Promise<ServiceRestartResponse> {
  return adminFetch<ServiceRestartResponse>(`/services/${encodeURIComponent(name)}/restart`, {
    method: 'POST',
  });
}

export async function getServiceStatus(name: string): Promise<ServiceWithStatus> {
  return adminFetch<ServiceWithStatus>(`/services/${encodeURIComponent(name)}/status`);
}

// ============================================================================
// Profiles API
// ============================================================================

export async function getProfiles(): Promise<ProfilesResponse> {
  return adminFetch<ProfilesResponse>('/profiles');
}

export async function updateProfile(
  name: string,
  profile: Omit<Profile, 'name' | 'is_active' | 'is_default'>
): Promise<ApiResponse> {
  return adminFetch<ApiResponse>(`/profiles/${encodeURIComponent(name)}`, {
    method: 'PUT',
    body: JSON.stringify(profile),
  });
}

export async function deleteProfile(name: string): Promise<ApiResponse> {
  return adminFetch<ApiResponse>(`/profiles/${encodeURIComponent(name)}`, {
    method: 'DELETE',
  });
}

export async function activateProfile(name: string): Promise<ApiResponseWithRestart> {
  return adminFetch<ApiResponseWithRestart>(`/profiles/${encodeURIComponent(name)}/activate`, {
    method: 'POST',
  });
}

// ============================================================================
// OmniParser API
// ============================================================================

export async function getOmniParserSettings(): Promise<OmniParserSettings> {
  return adminFetch<OmniParserSettings>('/omniparser');
}

export async function updateOmniParserSettings(
  settings: Partial<OmniParserSettings>
): Promise<ApiResponseWithRestart> {
  return adminFetch<ApiResponseWithRestart>('/omniparser', {
    method: 'PUT',
    body: JSON.stringify(settings),
  });
}

export async function testOmniParserServer(url: string): Promise<OmniParserTestResult> {
  return adminFetch<OmniParserTestResult>('/omniparser/test', {
    method: 'POST',
    body: JSON.stringify({ url }),
    timeout: 15000, // Allow more time for remote servers
  });
}

// ============================================================================
// Steam Accounts API
// ============================================================================

export async function getSteamAccounts(): Promise<SteamAccountsResponse> {
  return adminFetch<SteamAccountsResponse>('/steam-accounts');
}

export async function updateSteamAccounts(data: {
  pairs?: SteamAccountPair[];
  login_timeout?: number;
}): Promise<ApiResponse> {
  return adminFetch<ApiResponse>('/steam-accounts', {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

// ============================================================================
// Discovery Settings API
// ============================================================================

export async function getDiscoverySettings(): Promise<DiscoverySettings> {
  return adminFetch<DiscoverySettings>('/discovery');
}

export async function updateDiscoverySettings(
  settings: Partial<DiscoverySettings>
): Promise<ApiResponseWithRestart> {
  return adminFetch<ApiResponseWithRestart>('/discovery', {
    method: 'PUT',
    body: JSON.stringify(settings),
  });
}

// ============================================================================
// Automation Settings API
// ============================================================================

export async function getAutomationSettings(): Promise<AutomationSettings> {
  return adminFetch<AutomationSettings>('/automation');
}

export async function updateAutomationSettings(
  settings: Partial<AutomationSettings>
): Promise<ApiResponse> {
  return adminFetch<ApiResponse>('/automation', {
    method: 'PUT',
    body: JSON.stringify(settings),
  });
}

// ============================================================================
// Game Configuration API
// ============================================================================

export async function getGamesList(): Promise<GamesListResponse> {
  return adminFetch<GamesListResponse>('/games');
}

export async function getGameYaml(name: string): Promise<GameYamlResponse> {
  return adminFetch<GameYamlResponse>(`/games/${encodeURIComponent(name)}/yaml`);
}

export async function updateGameYaml(
  name: string,
  content: string
): Promise<GameUpdateResponse> {
  return adminFetch<GameUpdateResponse>(`/games/${encodeURIComponent(name)}/yaml`, {
    method: 'PUT',
    body: JSON.stringify({ content }),
  });
}

export async function createGame(data: {
  name: string;
  content?: string;
  game_name?: string;
  steam_app_id?: string;
  preset_id?: string;
  display_name?: string;
}): Promise<GameCreateResponse> {
  return adminFetch<GameCreateResponse>('/games', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function deleteGame(name: string): Promise<GameDeleteResponse> {
  return adminFetch<GameDeleteResponse>(`/games/${encodeURIComponent(name)}`, {
    method: 'DELETE',
  });
}

export async function validateYaml(content: string): Promise<YamlValidationResult> {
  return adminFetch<YamlValidationResult>('/validate-yaml', {
    method: 'POST',
    body: JSON.stringify({ content }),
  });
}

// ============================================================================
// Export all functions
// ============================================================================

export const adminApi = {
  // Config
  getConfig,
  updateConfig,
  resetConfig,

  // Services
  getServices,
  getService,
  updateService,
  restartService,
  getServiceStatus,

  // Profiles
  getProfiles,
  updateProfile,
  deleteProfile,
  activateProfile,

  // OmniParser
  getOmniParserSettings,
  updateOmniParserSettings,
  testOmniParserServer,

  // Steam
  getSteamAccounts,
  updateSteamAccounts,

  // Discovery
  getDiscoverySettings,
  updateDiscoverySettings,

  // Automation
  getAutomationSettings,
  updateAutomationSettings,

  // Games
  getGamesList,
  getGameYaml,
  updateGameYaml,
  createGame,
  deleteGame,
  validateYaml,
};

export default adminApi;
