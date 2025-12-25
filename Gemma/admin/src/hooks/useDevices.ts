import { useState, useEffect, useCallback, useRef } from 'react';
import { getDevices, pairSut, unpairSut } from '../api';
import type { SUT } from '../types';

// Discovery Service SSE URL (direct connection for real-time updates)
const DISCOVERY_SSE_URL = 'http://localhost:5001/api/suts/events';

export function useDevices(pollInterval: number = 10000) {
  const [devices, setDevices] = useState<SUT[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sseConnected, setSseConnected] = useState(false);
  const eventSourceRef = useRef<EventSource | null>(null);

  const fetchDevices = useCallback(async () => {
    try {
      const data = await getDevices();
      setDevices(data.devices);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch devices');
    } finally {
      setLoading(false);
    }
  }, []);

  // Connect to SSE for real-time updates
  useEffect(() => {
    const connectSSE = () => {
      try {
        const eventSource = new EventSource(DISCOVERY_SSE_URL);
        eventSourceRef.current = eventSource;

        eventSource.onopen = () => {
          console.log('[SSE] Connected to Discovery Service');
          setSseConnected(true);
        };

        eventSource.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            console.log('[SSE] Event:', data.type);

            if (data.type === 'sut_online' || data.type === 'sut_offline') {
              // Refresh device list on any SUT status change
              fetchDevices();
            }
          } catch (e) {
            console.error('[SSE] Parse error:', e);
          }
        };

        eventSource.onerror = () => {
          console.log('[SSE] Connection error, reconnecting...');
          setSseConnected(false);
          eventSource.close();
          // Reconnect after delay
          setTimeout(connectSSE, 2000);
        };
      } catch (e) {
        console.error('[SSE] Failed to connect:', e);
        setTimeout(connectSSE, 2000);
      }
    };

    // Initial fetch
    fetchDevices();

    // Connect to SSE
    connectSSE();

    // Fallback polling (slower since we have SSE)
    const interval = setInterval(fetchDevices, pollInterval);

    return () => {
      clearInterval(interval);
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, [fetchDevices, pollInterval]);

  const pair = useCallback(async (deviceId: string) => {
    try {
      await pairSut(deviceId);
      await fetchDevices();
    } catch (err) {
      throw err;
    }
  }, [fetchDevices]);

  const unpair = useCallback(async (deviceId: string) => {
    try {
      await unpairSut(deviceId);
      await fetchDevices();
    } catch (err) {
      throw err;
    }
  }, [fetchDevices]);

  const onlineDevices = devices.filter(d => d.status === 'online');
  const pairedDevices = devices.filter(d => d.is_paired);

  return {
    devices,
    onlineDevices,
    pairedDevices,
    loading,
    error,
    sseConnected,
    refetch: fetchDevices,
    pair,
    unpair,
  };
}
