import type {
  DevicesResponse,
  GamesResponse,
  RunsResponse,
  RunsStats,
  SystemStatus,
  SUT,
  AutomationRun,
} from '../types';

const API_BASE = '/api';

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = 'ApiError';
  }
}

async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, {
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

// Automation Run APIs
export async function getRuns(): Promise<RunsResponse> {
  return fetchJson<RunsResponse>(`${API_BASE}/runs`);
}

export async function getRun(runId: string): Promise<AutomationRun> {
  return fetchJson<AutomationRun>(`${API_BASE}/runs/${runId}`);
}

export async function startRun(
  sutIp: string,
  gameName: string,
  iterations: number = 1
): Promise<{ status: string; run_id: string; message: string }> {
  return fetchJson<{ status: string; run_id: string; message: string }>(`${API_BASE}/runs`, {
    method: 'POST',
    body: JSON.stringify({ sut_ip: sutIp, game_name: gameName, iterations }),
  });
}

export async function stopRun(runId: string): Promise<{ status: string; message: string }> {
  return fetchJson<{ status: string; message: string }>(`${API_BASE}/runs/${runId}/stop`, {
    method: 'POST',
  });
}

export async function getRunsStats(): Promise<RunsStats> {
  return fetchJson<RunsStats>(`${API_BASE}/runs/stats`);
}

// SUT Action APIs
export async function getSutStatus(deviceId: string): Promise<unknown> {
  return fetchJson<unknown>(`${API_BASE}/sut/${deviceId}/status`);
}

export async function takeSutScreenshot(deviceId: string): Promise<Blob> {
  const response = await fetch(`${API_BASE}/sut/${deviceId}/screenshot`);
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

export { ApiError };
