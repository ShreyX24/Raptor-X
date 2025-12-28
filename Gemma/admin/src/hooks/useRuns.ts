import { useState, useEffect, useCallback } from 'react';
import { getRuns, startRun, stopRun } from '../api';
import type { AutomationRun } from '../types';

export function useRuns(pollInterval: number = 2000) {
  const [activeRuns, setActiveRuns] = useState<Record<string, AutomationRun>>({});
  const [history, setHistory] = useState<AutomationRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchRuns = useCallback(async () => {
    try {
      const data = await getRuns();
      setActiveRuns(data.active);
      setHistory(data.history);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch runs');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchRuns();
    const interval = setInterval(fetchRuns, pollInterval);
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
  };
}
