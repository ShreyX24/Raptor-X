/**
 * ServiceConfigTab - Services configuration tab
 */

import { useState, useCallback, useEffect } from 'react';
import { adminApi } from '../../api/adminApi';
import { useToast } from '../../contexts/ToastContext';
import type { ServiceWithStatus, ServiceSettings } from '../../types/admin';
import {
  RefreshCw,
  Settings2,
  CheckCircle,
  XCircle,
  Clock,
  AlertCircle,
  Power,
  PowerOff,
} from 'lucide-react';

interface ServiceConfigTabProps {
  services: Record<string, ServiceWithStatus> | null;
  loading: boolean;
  onRefresh: () => Promise<void>;
  onUnsavedChange: () => void;
  onSaved: () => void;
}

const SERVICE_DISPLAY_NAMES: Record<string, string> = {
  'sut-discovery': 'SUT Discovery',
  'queue-service': 'Queue Service',
  'gemma-backend': 'Gemma Backend',
  'gemma-frontend': 'Gemma Frontend',
  'preset-manager': 'Preset Manager',
  'pm-frontend': 'PM Frontend',
  'sut-client': 'SUT Client',
};

const STATUS_ICONS: Record<string, React.ReactNode> = {
  online: <CheckCircle className="w-4 h-4 text-success" />,
  offline: <XCircle className="w-4 h-4 text-text-muted" />,
  disabled: <PowerOff className="w-4 h-4 text-text-muted" />,
  error: <AlertCircle className="w-4 h-4 text-danger" />,
  timeout: <Clock className="w-4 h-4 text-warning" />,
  unknown: <AlertCircle className="w-4 h-4 text-warning" />,
  no_port: <AlertCircle className="w-4 h-4 text-warning" />,
};

const STATUS_COLORS: Record<string, string> = {
  online: 'bg-success',
  offline: 'bg-text-muted',
  disabled: 'bg-text-muted',
  error: 'bg-danger',
  timeout: 'bg-warning',
  unknown: 'bg-warning',
  no_port: 'bg-warning',
};

interface ServiceCardProps {
  name: string;
  service: ServiceWithStatus;
  onUpdate: (name: string, settings: Partial<ServiceSettings>) => Promise<void>;
  onRestart: (name: string) => Promise<void>;
}

function ServiceCard({ name, service, onUpdate, onRestart }: ServiceCardProps) {
  const [editing, setEditing] = useState(false);
  const [localSettings, setLocalSettings] = useState({
    host: service.host,
    port: service.port,
    enabled: service.enabled,
    remote: service.remote,
  });
  const [saving, setSaving] = useState(false);
  const [restarting, setRestarting] = useState(false);
  const toast = useToast();

  // Update local state when service changes
  useEffect(() => {
    setLocalSettings({
      host: service.host,
      port: service.port,
      enabled: service.enabled,
      remote: service.remote,
    });
  }, [service]);

  const handleSave = async () => {
    setSaving(true);
    try {
      await onUpdate(name, localSettings);
      setEditing(false);
      toast.success('Service Updated', `${SERVICE_DISPLAY_NAMES[name] || name} settings saved`);
    } catch (err) {
      toast.error('Save Failed', err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setSaving(false);
    }
  };

  const handleRestart = async () => {
    setRestarting(true);
    try {
      await onRestart(name);
      toast.info('Restart Requested', `${SERVICE_DISPLAY_NAMES[name] || name} restart queued`);
    } catch (err) {
      toast.error('Restart Failed', err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setRestarting(false);
    }
  };

  const handleToggleEnabled = async () => {
    await onUpdate(name, { enabled: !service.enabled });
  };

  return (
    <div className="bg-surface border border-border rounded-lg p-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-3">
          <div className={`w-3 h-3 rounded-full ${STATUS_COLORS[service.status]}`} />
          <div>
            <h3 className="font-semibold text-text-primary">
              {SERVICE_DISPLAY_NAMES[name] || name}
            </h3>
            <p className="text-xs text-text-muted">
              {service.host}:{service.port}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {STATUS_ICONS[service.status]}
          <span className="text-xs text-text-secondary capitalize">{service.status}</span>
        </div>
      </div>

      {/* Content */}
      {editing ? (
        <div className="space-y-3 mt-4">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-text-muted mb-1">Host</label>
              <input
                type="text"
                value={localSettings.host}
                onChange={e => setLocalSettings(prev => ({ ...prev, host: e.target.value }))}
                className="w-full px-3 py-2 text-sm bg-surface-elevated border border-border rounded focus:outline-none focus:border-primary"
              />
            </div>
            <div>
              <label className="block text-xs text-text-muted mb-1">Port</label>
              <input
                type="number"
                value={localSettings.port}
                onChange={e => setLocalSettings(prev => ({ ...prev, port: parseInt(e.target.value) || 0 }))}
                className="w-full px-3 py-2 text-sm bg-surface-elevated border border-border rounded focus:outline-none focus:border-primary"
              />
            </div>
          </div>

          <div className="flex items-center gap-4">
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={localSettings.enabled}
                onChange={e => setLocalSettings(prev => ({ ...prev, enabled: e.target.checked }))}
                className="w-4 h-4 rounded border-border"
              />
              <span className="text-text-secondary">Enabled</span>
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={localSettings.remote}
                onChange={e => setLocalSettings(prev => ({ ...prev, remote: e.target.checked }))}
                className="w-4 h-4 rounded border-border"
              />
              <span className="text-text-secondary">Remote</span>
            </label>
          </div>

          <div className="flex items-center justify-end gap-2 pt-2">
            <button
              onClick={() => setEditing(false)}
              className="px-3 py-1.5 text-sm text-text-secondary hover:text-text-primary"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={saving}
              className="px-3 py-1.5 text-sm bg-primary text-white rounded hover:bg-primary-hover disabled:opacity-50"
            >
              {saving ? 'Saving...' : 'Save'}
            </button>
          </div>
        </div>
      ) : (
        <div className="flex items-center justify-between mt-4">
          <div className="flex items-center gap-3">
            <button
              onClick={handleToggleEnabled}
              className={`flex items-center gap-1.5 px-2.5 py-1.5 text-xs rounded transition-colors ${
                service.enabled
                  ? 'bg-success/20 text-success hover:bg-success/30'
                  : 'bg-surface-elevated text-text-muted hover:bg-surface-hover'
              }`}
            >
              {service.enabled ? <Power className="w-3 h-3" /> : <PowerOff className="w-3 h-3" />}
              {service.enabled ? 'Enabled' : 'Disabled'}
            </button>
            {service.remote && (
              <span className="px-2 py-1 text-xs bg-primary/20 text-primary rounded">
                Remote
              </span>
            )}
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setEditing(true)}
              className="p-2 text-text-muted hover:text-text-primary hover:bg-surface-elevated rounded transition-colors"
              title="Edit settings"
            >
              <Settings2 className="w-4 h-4" />
            </button>
            <button
              onClick={handleRestart}
              disabled={restarting || !service.enabled}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-surface-elevated hover:bg-surface-hover border border-border rounded transition-colors disabled:opacity-50"
              title="Restart service"
            >
              <RefreshCw className={`w-3 h-3 ${restarting ? 'animate-spin' : ''}`} />
              Restart
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export function ServiceConfigTab({
  services,
  loading,
  onRefresh,
  onUnsavedChange: _onUnsavedChange,
  onSaved,
}: ServiceConfigTabProps) {
  const handleUpdate = useCallback(async (name: string, settings: Partial<ServiceSettings>) => {
    await adminApi.updateService(name, settings);
    onSaved();
    await onRefresh();
  }, [onRefresh, onSaved]);

  const handleRestart = useCallback(async (name: string) => {
    await adminApi.restartService(name);
  }, []);

  if (loading && !services) {
    return (
      <div className="p-6">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1, 2, 3, 4, 5, 6].map(i => (
            <div key={i} className="h-32 bg-surface animate-pulse rounded-lg" />
          ))}
        </div>
      </div>
    );
  }

  if (!services) {
    return (
      <div className="p-8 text-center text-text-muted">
        Failed to load services. Click refresh to try again.
      </div>
    );
  }

  const serviceEntries = Object.entries(services);

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-lg font-semibold text-text-primary">Service Configuration</h2>
          <p className="text-sm text-text-muted">
            Configure hosts, ports, and manage service lifecycle
          </p>
        </div>
        <button
          onClick={onRefresh}
          disabled={loading}
          className="flex items-center gap-2 px-3 py-2 text-sm bg-surface-elevated hover:bg-surface-hover border border-border rounded-lg transition-colors"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          Refresh Status
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {serviceEntries.map(([name, service]) => (
          <ServiceCard
            key={name}
            name={name}
            service={service}
            onUpdate={handleUpdate}
            onRestart={handleRestart}
          />
        ))}
      </div>

      <div className="mt-6 p-4 bg-surface-elevated rounded-lg">
        <h3 className="text-sm font-medium text-text-primary mb-2">Service Restart Note</h3>
        <p className="text-xs text-text-muted">
          Service restart requests are queued and processed by Service Manager.
          Ensure Service Manager is running for restarts to take effect.
        </p>
      </div>
    </div>
  );
}

export default ServiceConfigTab;
