import { useState, useEffect, useCallback, useRef } from 'react';
import { getSystemStatus } from '../api';
import { getQueueHealth, probeQueueService } from '../api/queueService';
import { getSyncStats } from '../api/presetManager';
import type { AllServicesHealth, ServiceHealthStatus } from '../types';

interface UseServiceHealthResult {
  services: AllServicesHealth | null;
  loading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
}

// Use proxy paths for cross-device compatibility (mobile, desktop)
const DISCOVERY_SERVICE_URL = '/discovery-health';
const QUEUE_SERVICE_URL = '/queue-api';
const PRESET_MANAGER_URL = '/preset-api';

async function checkServiceHealth(
  name: string,
  displayName: string,
  url: string,
  port: number,
  healthEndpoint: string = '/health',
  timeoutMs: number = 5000
): Promise<ServiceHealthStatus> {
  try {
    const response = await fetch(`${url}${healthEndpoint}`, {
      signal: AbortSignal.timeout(timeoutMs),
    });

    if (response.ok) {
      const data = await response.json().catch(() => ({}));
      return {
        name,
        displayName,
        status: 'online',
        url,
        port,
        details: data,
        lastChecked: new Date().toISOString(),
      };
    }

    return {
      name,
      displayName,
      status: 'error',
      url,
      port,
      lastChecked: new Date().toISOString(),
    };
  } catch {
    return {
      name,
      displayName,
      status: 'offline',
      url,
      port,
      lastChecked: new Date().toISOString(),
    };
  }
}

// Number of consecutive failures before marking service as offline
const FAILURE_THRESHOLD = 3;

export function useServiceHealth(pollInterval: number = 5000): UseServiceHealthResult {
  const [services, setServices] = useState<AllServicesHealth | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const isMounted = useRef(true);

  // Track consecutive failures per service to prevent flickering
  const failureCountsRef = useRef<Record<string, number>>({
    'raptor-x-backend': 0,
    'discovery-service': 0,
    'queue-service': 0,
    'preset-manager': 0,
  });

  // Keep last known good status
  const lastKnownStatusRef = useRef<Record<string, ServiceHealthStatus['status']>>({});

  const fetchAll = useCallback(async () => {
    try {
      // Check all services in parallel
      const [
        gemmaBackendStatus,
        discoveryStatus,
        queueStatus,
        presetStatus,
      ] = await Promise.all([
        // Raptor X Backend - use longer timeout since /api/status does internal health checks
        getSystemStatus()
          .then((data) => {
            failureCountsRef.current['raptor-x-backend'] = 0;
            lastKnownStatusRef.current['raptor-x-backend'] = 'online';
            return {
              name: 'raptor-x-backend',
              displayName: 'Raptor X Backend',
              status: 'online' as const,
              url: '/api',
              port: 5000,
              details: {
                mode: data.backend.mode,
                uptime: data.backend.uptime,
                websocket_clients: data.backend.websocket_clients,
              },
              lastChecked: new Date().toISOString(),
            };
          })
          .catch((err) => {
            failureCountsRef.current['raptor-x-backend']++;
            const failCount = failureCountsRef.current['raptor-x-backend'];
            const lastStatus = lastKnownStatusRef.current['raptor-x-backend'];

            // Only mark offline after FAILURE_THRESHOLD consecutive failures
            // If we were previously online, stay online until threshold reached
            const shouldStayOnline = lastStatus === 'online' && failCount < FAILURE_THRESHOLD;
            const newStatus = shouldStayOnline ? 'online' : 'offline';

            // Update last known status if going offline
            if (newStatus === 'offline') {
              lastKnownStatusRef.current['raptor-x-backend'] = 'offline';
            }

            console.debug(`[ServiceHealth] Gemma check failed (${failCount}/${FAILURE_THRESHOLD}), status: ${newStatus}`, err);

            return {
              name: 'raptor-x-backend',
              displayName: 'Raptor X Backend',
              status: newStatus as 'online' | 'offline',
              url: '/api',
              port: 5000,
              lastChecked: new Date().toISOString(),
            };
          }),

        // Discovery Service
        checkServiceHealth(
          'discovery-service',
          'SUT Discovery',
          DISCOVERY_SERVICE_URL,
          5001,
          '/health'
        ),

        // Queue Service with queue depth
        getQueueHealth()
          .then((health) => ({
            name: 'queue-service',
            displayName: 'Queue Service',
            status: health.status === 'healthy' ? 'online' as const : 'error' as const,
            url: QUEUE_SERVICE_URL,
            port: 9000,
            queueDepth: health.queue_size,
            details: {
              worker_running: health.worker_running,
              uptime: health.uptime_seconds,
              omniparser: health.omniparser_status,
            },
            lastChecked: new Date().toISOString(),
          }))
          .catch(() => ({
            name: 'queue-service',
            displayName: 'Queue Service',
            status: 'offline' as const,
            url: QUEUE_SERVICE_URL,
            port: 9000,
            queueDepth: undefined,
            lastChecked: new Date().toISOString(),
          })),

        // Preset Manager
        getSyncStats()
          .then((stats) => ({
            name: 'preset-manager',
            displayName: 'Preset Manager',
            status: stats.sync_manager_ready ? 'online' as const : 'error' as const,
            url: PRESET_MANAGER_URL,
            port: 5002,
            details: {
              total_games: stats.total_games,
              total_presets: stats.total_presets,
              online_suts: stats.online_suts,
            },
            lastChecked: new Date().toISOString(),
          }))
          .catch(() => ({
            name: 'preset-manager',
            displayName: 'Preset Manager',
            status: 'offline' as const,
            url: PRESET_MANAGER_URL,
            port: 5002,
            lastChecked: new Date().toISOString(),
          })),
      ]);

      if (!isMounted.current) return;

      // Get OmniParser instances from Queue Service probe endpoint
      let omniparserInstances: Array<ServiceHealthStatus & { instanceId: number; enabled: boolean }> = [];

      try {
        const probeData = await probeQueueService();
        if (probeData.omniparser_status && Array.isArray(probeData.omniparser_status)) {
          omniparserInstances = probeData.omniparser_status.map((server, index) => {
            // Extract port from URL
            let port = 8000;
            try {
              const url = new URL(server.url);
              port = parseInt(url.port) || 8000;
            } catch {
              // Use default port
            }

            return {
              name: `omniparser-${index}`,
              displayName: `OmniParser ${index + 1}`,
              instanceId: index,
              enabled: true,
              status: server.status === 'healthy' ? 'online' as const : 'offline' as const,
              url: server.url,
              port,
              details: {
                requests_served: server.requests_served,
                last_used: server.last_used,
              },
              lastChecked: new Date().toISOString(),
            };
          });
        }
      } catch {
        // OmniParser check failed via probe, try system status as fallback
        try {
          const systemStatus = await getSystemStatus();
          if (systemStatus.omniparser) {
            omniparserInstances = [{
              name: 'omniparser-0',
              displayName: 'OmniParser 1',
              instanceId: 0,
              enabled: true,
              status: systemStatus.omniparser.status === 'online' ? 'online' : 'offline',
              url: systemStatus.omniparser.url,
              port: 8000,
              details: {
                queue_size: systemStatus.omniparser.queue_size,
              },
              lastChecked: new Date().toISOString(),
            }];
          }
        } catch {
          // Both failed, leave empty
        }
      }

      setServices({
        gemmaBackend: gemmaBackendStatus,
        discoveryService: discoveryStatus,
        queueService: queueStatus,
        presetManager: presetStatus,
        omniparserInstances,
      });

      setError(null);
    } catch (err) {
      if (!isMounted.current) return;
      setError(err instanceof Error ? err.message : 'Failed to check service health');
    } finally {
      if (isMounted.current) {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    isMounted.current = true;
    fetchAll();

    const interval = setInterval(fetchAll, pollInterval);

    return () => {
      isMounted.current = false;
      clearInterval(interval);
    };
  }, [fetchAll, pollInterval]);

  return {
    services,
    loading,
    error,
    refetch: fetchAll,
  };
}
