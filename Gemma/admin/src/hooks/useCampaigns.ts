import { useState, useEffect, useCallback, useRef } from 'react';
import { getCampaigns, stopCampaign } from '../api';
import type { Campaign } from '../types';
import { useWebSocket, CampaignEvent } from './useWebSocket';

export function useCampaigns(pollInterval: number = 3000) {
  const [activeCampaigns, setActiveCampaigns] = useState<Campaign[]>([]);
  const [historyCampaigns, setHistoryCampaigns] = useState<Campaign[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // WebSocket for real-time updates
  const { isConnected, onCampaignEvent } = useWebSocket();
  const wsConnectedRef = useRef(false);
  wsConnectedRef.current = isConnected;

  const fetchCampaigns = useCallback(async () => {
    try {
      const data = await getCampaigns();
      setActiveCampaigns(data.active || []);
      setHistoryCampaigns(data.history || []);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch campaigns');
    } finally {
      setLoading(false);
    }
  }, []);

  // Handle WebSocket campaign events for real-time updates
  useEffect(() => {
    const unsubscribe = onCampaignEvent((event: CampaignEvent) => {
      console.log('[useCampaigns] WebSocket event:', event.event, event.data?.campaign_id);

      // Refresh campaigns on any campaign event
      switch (event.event) {
        case 'campaign_created':
        case 'campaign_progress':
        case 'campaign_completed':
        case 'campaign_failed':
          fetchCampaigns();
          break;
        default:
          break;
      }
    });

    return unsubscribe;
  }, [onCampaignEvent, fetchCampaigns]);

  // Polling - use longer interval when WebSocket is connected
  useEffect(() => {
    fetchCampaigns();
    // Poll every 3s normally, or every 10s when WebSocket is connected
    const actualInterval = wsConnectedRef.current ? 10000 : pollInterval;
    const interval = setInterval(fetchCampaigns, actualInterval);
    return () => clearInterval(interval);
  }, [fetchCampaigns, pollInterval]);

  const stop = useCallback(async (campaignId: string) => {
    try {
      await stopCampaign(campaignId);
      await fetchCampaigns();
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
    // WebSocket status
    isWebSocketConnected: isConnected,
  };
}
