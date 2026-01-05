import { useState, useEffect, useCallback } from 'react';
import {
  getMultiSUTCampaigns,
  stopMultiSUTCampaign,
  getAccountStatus,
  createMultiSUTCampaign,
} from '../api';
import type {
  MultiSUTCampaign,
  AccountStatusResponse,
} from '../api';

export function useMultiSUTCampaigns(pollInterval: number = 3000) {
  const [activeCampaigns, setActiveCampaigns] = useState<MultiSUTCampaign[]>([]);
  const [historyCampaigns, setHistoryCampaigns] = useState<MultiSUTCampaign[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchCampaigns = useCallback(async () => {
    try {
      const data = await getMultiSUTCampaigns();
      setActiveCampaigns(data.active || []);
      setHistoryCampaigns(data.history || []);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch multi-SUT campaigns');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchCampaigns();
    const interval = setInterval(fetchCampaigns, pollInterval);
    return () => clearInterval(interval);
  }, [fetchCampaigns, pollInterval]);

  const stop = useCallback(async (campaignId: string) => {
    try {
      await stopMultiSUTCampaign(campaignId);
      await fetchCampaigns();
    } catch (err) {
      throw err;
    }
  }, [fetchCampaigns]);

  const create = useCallback(async (
    suts: string[],
    games: string[],
    iterations: number,
    name?: string,
    quality?: string,
    resolution?: string
  ) => {
    try {
      const result = await createMultiSUTCampaign(suts, games, iterations, name, quality, resolution);
      await fetchCampaigns();
      return result;
    } catch (err) {
      throw err;
    }
  }, [fetchCampaigns]);

  const hasActiveCampaigns = activeCampaigns.length > 0;

  return {
    activeCampaigns,
    historyCampaigns,
    hasActiveCampaigns,
    loading,
    error,
    refetch: fetchCampaigns,
    stop,
    create,
  };
}

export function useAccountStatus(pollInterval: number = 2000) {
  const [accountStatus, setAccountStatus] = useState<AccountStatusResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchStatus = useCallback(async () => {
    try {
      const data = await getAccountStatus();
      setAccountStatus(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch account status');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, pollInterval);
    return () => clearInterval(interval);
  }, [fetchStatus, pollInterval]);

  return {
    accountStatus,
    loading,
    error,
    refetch: fetchStatus,
  };
}
