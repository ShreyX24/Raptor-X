/**
 * Queue Service API Client
 * Connects to the Queue Service via Vite proxy (/queue-api -> localhost:9000)
 */

import type { QueueStats, QueueJob, QueueDepthPoint, QueueHealth } from '../types';

// Use proxy path for cross-device compatibility (mobile, desktop)
const QUEUE_SERVICE_URL = '/queue-api';

class QueueServiceError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = 'QueueServiceError';
  }
}

async function fetchQueueJson<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${QUEUE_SERVICE_URL}${endpoint}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ error: response.statusText }));
    throw new QueueServiceError(response.status, error.error || error.detail || response.statusText);
  }

  return response.json();
}

/**
 * Get current queue statistics
 */
export async function getQueueStats(): Promise<QueueStats> {
  return fetchQueueJson<QueueStats>('/stats');
}

/**
 * Get recent job history
 * @param limit Number of jobs to return (1-100, default 20)
 */
export async function getQueueJobs(limit: number = 20): Promise<QueueJob[]> {
  const clampedLimit = Math.min(100, Math.max(1, limit));
  const result = await fetchQueueJson<QueueJob[] | { jobs?: QueueJob[] }>(`/jobs?limit=${clampedLimit}`);
  // Handle both array response and object with jobs property
  if (Array.isArray(result)) return result;
  if (result && Array.isArray(result.jobs)) return result.jobs;
  return [];
}

/**
 * Get queue depth history for charts
 * @param points Number of data points to return (1-200, default 50)
 */
export async function getQueueDepth(points: number = 50): Promise<QueueDepthPoint[]> {
  const clampedPoints = Math.min(200, Math.max(1, points));
  const result = await fetchQueueJson<QueueDepthPoint[] | { history?: QueueDepthPoint[] }>(`/queue-depth?points=${clampedPoints}`);
  // Handle both array response and object with history property
  if (Array.isArray(result)) return result;
  if (result && Array.isArray(result.history)) return result.history;
  return [];
}

/**
 * Get queue service health status
 */
export async function getQueueHealth(): Promise<QueueHealth> {
  return fetchQueueJson<QueueHealth>('/health');
}

/**
 * OmniParser server status from probe response
 */
export interface OmniParserServerStatus {
  url: string;
  status: 'healthy' | 'unhealthy' | 'error' | 'unknown';
  last_used?: string;
  requests_served?: number;
}

/**
 * Probe response from queue service
 */
export interface QueueProbeResponse {
  status: string;
  overall_omniparser_status: string;
  omniparser_status: OmniParserServerStatus[];
  stats: QueueStats;
}

/**
 * Probe the queue service (includes OmniParser status)
 */
export async function probeQueueService(): Promise<QueueProbeResponse> {
  return fetchQueueJson('/probe');
}

/**
 * Check if queue service is available
 */
export async function isQueueServiceAvailable(): Promise<boolean> {
  try {
    await getQueueHealth();
    return true;
  } catch {
    return false;
  }
}

export { QueueServiceError };
