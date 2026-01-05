/**
 * AdminPanel - Main container for admin settings with tabs
 */

import { useState, useCallback, useEffect } from 'react';
import { TabNavigation } from './TabNavigation';
import { ServiceConfigTab } from './ServiceConfigTab';
import { OmniParserSettings } from './OmniParserSettings';
import { DiscoverySettings } from './DiscoverySettings';
import { GameConfigEditor } from './GameConfigEditor';
import { AutomationSettings } from './AutomationSettings';
import { SteamAccountsManager } from './SteamAccountsManager';
import { ProfileManager } from './ProfileManager';
import { useAdminConfig } from '../../hooks/useAdminConfig';
import type { AdminTab } from '../../types/admin';
import { RefreshCw } from 'lucide-react';

interface AdminPanelProps {
  initialTab?: AdminTab;
}

export function AdminPanel({ initialTab = 'services' }: AdminPanelProps) {
  const [activeTab, setActiveTab] = useState<AdminTab>(initialTab);
  const [unsavedTabs, setUnsavedTabs] = useState<Set<AdminTab>>(new Set());
  const [_saving, _setSaving] = useState(false);

  const {
    services,
    profiles,
    omniparser,
    steamAccounts,
    discovery,
    automation,
    loading,
    error,
    refreshAll,
    refreshServices,
  } = useAdminConfig();

  // Handle tab change with unsaved changes warning
  const handleTabChange = useCallback((tab: AdminTab) => {
    if (unsavedTabs.has(activeTab)) {
      // For now, just allow switching - could add confirmation dialog
      // toast.warning('Unsaved Changes', `You have unsaved changes in ${activeTab}`);
    }
    setActiveTab(tab);
  }, [activeTab, unsavedTabs]);

  // Mark tab as having unsaved changes
  const markUnsaved = useCallback((tab: AdminTab) => {
    setUnsavedTabs(prev => new Set([...prev, tab]));
  }, []);

  // Clear unsaved mark for a tab
  const clearUnsaved = useCallback((tab: AdminTab) => {
    setUnsavedTabs(prev => {
      const next = new Set(prev);
      next.delete(tab);
      return next;
    });
  }, []);

  // Handle Ctrl+S for save
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault();
        // Trigger save on current tab
        // This will be handled by individual tab components
        const event = new CustomEvent('admin-save', { detail: { tab: activeTab } });
        window.dispatchEvent(event);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [activeTab]);

  // Render tab content
  const renderTabContent = () => {
    switch (activeTab) {
      case 'services':
        return (
          <ServiceConfigTab
            services={services}
            loading={loading}
            onRefresh={refreshServices}
            onUnsavedChange={() => markUnsaved('services')}
            onSaved={() => clearUnsaved('services')}
          />
        );
      case 'omniparser':
        return (
          <OmniParserSettings
            settings={omniparser}
            loading={loading}
            onUnsavedChange={() => markUnsaved('omniparser')}
            onSaved={() => clearUnsaved('omniparser')}
          />
        );
      case 'discovery':
        return (
          <DiscoverySettings
            settings={discovery}
            loading={loading}
            onUnsavedChange={() => markUnsaved('discovery')}
            onSaved={() => clearUnsaved('discovery')}
          />
        );
      case 'games':
        return (
          <GameConfigEditor
            onUnsavedChange={() => markUnsaved('games')}
            onSaved={() => clearUnsaved('games')}
          />
        );
      case 'automation':
        return (
          <AutomationSettings
            settings={automation}
            loading={loading}
            onUnsavedChange={() => markUnsaved('automation')}
            onSaved={() => clearUnsaved('automation')}
          />
        );
      case 'steam':
        return (
          <SteamAccountsManager
            accounts={steamAccounts}
            loading={loading}
            onUnsavedChange={() => markUnsaved('steam')}
            onSaved={() => clearUnsaved('steam')}
          />
        );
      case 'profiles':
        return (
          <ProfileManager
            profiles={profiles}
            loading={loading}
            onUnsavedChange={() => markUnsaved('profiles')}
            onSaved={() => clearUnsaved('profiles')}
          />
        );
      default:
        return (
          <div className="p-8 text-center text-text-muted">
            Tab not implemented yet
          </div>
        );
    }
  };

  return (
    <div className="flex flex-col h-full bg-background">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-border bg-surface">
        <div>
          <h1 className="text-xl font-bold text-text-primary">Settings</h1>
          <p className="text-sm text-text-muted">Configure all Raptor X services and settings</p>
        </div>
        <div className="flex items-center gap-2">
          {unsavedTabs.size > 0 && (
            <span className="px-2 py-1 text-xs bg-warning/20 text-warning rounded">
              {unsavedTabs.size} unsaved
            </span>
          )}
          <button
            onClick={() => refreshAll()}
            disabled={loading}
            className="flex items-center gap-2 px-3 py-2 text-sm bg-surface-elevated hover:bg-surface-hover border border-border rounded-lg transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>
      </div>

      {/* Tab Navigation */}
      <TabNavigation
        activeTab={activeTab}
        onTabChange={handleTabChange}
        unsavedTabs={unsavedTabs}
      />

      {/* Error Banner */}
      {error && (
        <div className="mx-6 mt-4 p-3 bg-danger/10 border border-danger/20 rounded-lg text-danger text-sm">
          {error}
        </div>
      )}

      {/* Tab Content */}
      <div className="flex-1 overflow-y-auto">
        {renderTabContent()}
      </div>
    </div>
  );
}

export default AdminPanel;
