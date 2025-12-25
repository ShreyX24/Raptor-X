import { useState, useEffect, useCallback } from 'react';
import { getGames, reloadGames } from '../api';
import type { GameConfig } from '../types';

export function useGames() {
  const [games, setGames] = useState<Record<string, GameConfig>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchGames = useCallback(async () => {
    try {
      const data = await getGames();
      setGames(data.games);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch games');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchGames();
  }, [fetchGames]);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      await reloadGames();
      await fetchGames();
    } catch (err) {
      throw err;
    }
  }, [fetchGames]);

  const gamesList = Object.values(games);

  return {
    games,
    gamesList,
    loading,
    error,
    refetch: fetchGames,
    reload,
  };
}
