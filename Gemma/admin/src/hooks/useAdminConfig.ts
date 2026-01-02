/**
 * useAdminConfig - Hook for managing admin configuration
 */

import { useState, useEffect, useCallback } from 'react';
import { adminApi } from '../api/adminApi';
import type {
  AdminConfig,
  ServiceWithStatus,
  DiscoverySettings,
  AutomationSettings,
  OmniParserSettings,
  SteamAccountsResponse,
  ProfilesResponse,
} from '../types/admin';

interface UseAdminConfigReturn {
  // State
  config: AdminConfig | null;
  services: Record<string, ServiceWithStatus> | null;
  profiles: ProfilesResponse | null;
  omniparser: OmniParserSettings | null;
  steamAccounts: SteamAccountsResponse | null;
  discovery: DiscoverySettings | null;
  automation: AutomationSettings | null;

  // Loading states
  loading: boolean;
  servicesLoading: boolean;
  profilesLoading: boolean;
  omniparserLoading: boolean;
  steamLoading: boolean;
  discoveryLoading: boolean;
  automationLoading: boolean;

  // Errors
  error: string | null;

  // Actions
  refreshConfig: () => Promise<void>;
  refreshServices: () => Promise<void>;
  refreshProfiles: () => Promise<void>;
  refreshOmniParser: () => Promise<void>;
  refreshSteamAccounts: () => Promise<void>;
  refreshDiscovery: () => Promise<void>;
  refreshAutomation: () => Promise<void>;
  refreshAll: () => Promise<void>;
}

export function useAdminConfig(): UseAdminConfigReturn {
  // State
  const [config, setConfig] = useState<AdminConfig | null>(null);
  const [services, setServices] = useState<Record<string, ServiceWithStatus> | null>(null);
  const [profiles, setProfiles] = useState<ProfilesResponse | null>(null);
  const [omniparser, setOmniParser] = useState<OmniParserSettings | null>(null);
  const [steamAccounts, setSteamAccounts] = useState<SteamAccountsResponse | null>(null);
  const [discovery, setDiscovery] = useState<DiscoverySettings | null>(null);
  const [automation, setAutomation] = useState<AutomationSettings | null>(null);

  // Loading states
  const [loading, setLoading] = useState(true);
  const [servicesLoading, setServicesLoading] = useState(false);
  const [profilesLoading, setProfilesLoading] = useState(false);
  const [omniparserLoading, setOmniParserLoading] = useState(false);
  const [steamLoading, setSteamLoading] = useState(false);
  const [discoveryLoading, setDiscoveryLoading] = useState(false);
  const [automationLoading, setAutomationLoading] = useState(false);

  // Error state
  const [error, setError] = useState<string | null>(null);

  // Refresh functions
  const refreshConfig = useCallback(async () => {
    try {
      setLoading(true);
      const data = await adminApi.getConfig();
      setConfig(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load config');
    } finally {
      setLoading(false);
    }
  }, []);

  const refreshServices = useCallback(async () => {
    try {
      setServicesLoading(true);
      const data = await adminApi.getServices();
      setServices(data);
    } catch (err) {
      console.error('Failed to load services:', err);
    } finally {
      setServicesLoading(false);
    }
  }, []);

  const refreshProfiles = useCallback(async () => {
    try {
      setProfilesLoading(true);
      const data = await adminApi.getProfiles();
      setProfiles(data);
    } catch (err) {
      console.error('Failed to load profiles:', err);
    } finally {
      setProfilesLoading(false);
    }
  }, []);

  const refreshOmniParser = useCallback(async () => {
    try {
      setOmniParserLoading(true);
      const data = await adminApi.getOmniParserSettings();
      setOmniParser(data);
    } catch (err) {
      console.error('Failed to load OmniParser settings:', err);
    } finally {
      setOmniParserLoading(false);
    }
  }, []);

  const refreshSteamAccounts = useCallback(async () => {
    try {
      setSteamLoading(true);
      const data = await adminApi.getSteamAccounts();
      setSteamAccounts(data);
    } catch (err) {
      console.error('Failed to load Steam accounts:', err);
    } finally {
      setSteamLoading(false);
    }
  }, []);

  const refreshDiscovery = useCallback(async () => {
    try {
      setDiscoveryLoading(true);
      const data = await adminApi.getDiscoverySettings();
      setDiscovery(data);
    } catch (err) {
      console.error('Failed to load discovery settings:', err);
    } finally {
      setDiscoveryLoading(false);
    }
  }, []);

  const refreshAutomation = useCallback(async () => {
    try {
      setAutomationLoading(true);
      const data = await adminApi.getAutomationSettings();
      setAutomation(data);
    } catch (err) {
      console.error('Failed to load automation settings:', err);
    } finally {
      setAutomationLoading(false);
    }
  }, []);

  const refreshAll = useCallback(async () => {
    await Promise.all([
      refreshConfig(),
      refreshServices(),
      refreshProfiles(),
      refreshOmniParser(),
      refreshSteamAccounts(),
      refreshDiscovery(),
      refreshAutomation(),
    ]);
  }, [
    refreshConfig,
    refreshServices,
    refreshProfiles,
    refreshOmniParser,
    refreshSteamAccounts,
    refreshDiscovery,
    refreshAutomation,
  ]);

  // Initial load
  useEffect(() => {
    refreshAll();
  }, [refreshAll]);

  return {
    // State
    config,
    services,
    profiles,
    omniparser,
    steamAccounts,
    discovery,
    automation,

    // Loading states
    loading,
    servicesLoading,
    profilesLoading,
    omniparserLoading,
    steamLoading,
    discoveryLoading,
    automationLoading,

    // Error
    error,

    // Actions
    refreshConfig,
    refreshServices,
    refreshProfiles,
    refreshOmniParser,
    refreshSteamAccounts,
    refreshDiscovery,
    refreshAutomation,
    refreshAll,
  };
}

export default useAdminConfig;
