import { useState, useEffect, useCallback, useRef } from 'react';
import { getRuns, startRun, stopRun } from '../api';
import type { AutomationRun, PaginationInfo } from '../types';
import { useWebSocket, AutomationEvent } from './useWebSocket';

const DEFAULT_PAGINATION: PaginationInfo = {
  page: 1,
  per_page: 50,
  total: 0,
  total_pages: 1,
  has_more: false,
};

export function useRuns(pollInterval: number = 2000) {
  const [activeRuns, setActiveRuns] = useState<Record<string, AutomationRun>>({});
  const [history, setHistory] = useState<AutomationRun[]>([]);
  const [pagination, setPagination] = useState<PaginationInfo>(DEFAULT_PAGINATION);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // WebSocket for real-time updates
  const { isConnected, onAutomationEvent } = useWebSocket();
  const wsConnectedRef = useRef(false);
  wsConnectedRef.current = isConnected;

  // Fetch first page (also used for polling refresh)
  const fetchRuns = useCallback(async () => {
    try {
      const data = await getRuns(1, 50);
      setActiveRuns(data.active);
      setHistory(data.history);
      setPagination(data.pagination || DEFAULT_PAGINATION);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch runs');
    } finally {
      setLoading(false);
    }
  }, []);

  // Load more history (append to existing)
  const loadMore = useCallback(async () => {
    if (!pagination.has_more || loadingMore) return;

    setLoadingMore(true);
    try {
      const nextPage = pagination.page + 1;
      const data = await getRuns(nextPage, pagination.per_page);

      // Append new history to existing (avoid duplicates)
      setHistory((prev) => {
        const existingIds = new Set(prev.map((r) => r.run_id));
        const newRuns = data.history.filter((r) => !existingIds.has(r.run_id));
        return [...prev, ...newRuns];
      });

      setPagination(data.pagination || DEFAULT_PAGINATION);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load more runs');
    } finally {
      setLoadingMore(false);
    }
  }, [pagination, loadingMore]);

  // Handle WebSocket automation events for real-time updates
  useEffect(() => {
    const unsubscribe = onAutomationEvent((event: AutomationEvent) => {
      const runData = event.data;
      const runId = runData.run_id;

      if (!runId) return;

      switch (event.event) {
        case 'automation_started':
          // Add or update in active runs - fetch full data to get complete run object
          fetchRuns();
          break;

        case 'automation_completed':
        case 'automation_failed':
          // Move from active to history - fetch to get updated data
          fetchRuns();
          break;

        default:
          break;
      }
    });

    return unsubscribe;
  }, [onAutomationEvent, fetchRuns]);

  // Polling - use longer interval when WebSocket is connected
  useEffect(() => {
    fetchRuns();
    // Poll every 2s normally, or every 10s when WebSocket is connected
    const actualInterval = wsConnectedRef.current ? 10000 : pollInterval;
    const interval = setInterval(fetchRuns, actualInterval);
    return () => clearInterval(interval);
  }, [fetchRuns, pollInterval]);

  const start = useCallback(async (sutIp: string, gameName: string, iterations: number = 1) => {
    try {
      const result = await startRun(sutIp, gameName, iterations);
      await fetchRuns();
      return result;
    } catch (err) {
      throw err;
    }
  }, [fetchRuns]);

  const stop = useCallback(async (runId: string, killGame: boolean = false) => {
    try {
      await stopRun(runId, killGame);
      await fetchRuns();
    } catch (err) {
      throw err;
    }
  }, [fetchRuns]);

  const activeRunsList = Object.values(activeRuns);
  const hasActiveRuns = activeRunsList.length > 0;

  return {
    activeRuns,
    activeRunsList,
    history,
    hasActiveRuns,
    loading,
    error,
    refetch: fetchRuns,
    start,
    stop,
    // Pagination
    pagination,
    loadMore,
    loadingMore,
    // WebSocket status
    isWebSocketConnected: isConnected,
  };
}
