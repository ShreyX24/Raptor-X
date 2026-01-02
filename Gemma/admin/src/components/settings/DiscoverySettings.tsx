/**
 * DiscoverySettings - SUT Discovery configuration tab
 */

import { useState, useEffect } from 'react';
import { adminApi } from '../../api/adminApi';
import { useToast } from '../../contexts/ToastContext';
import type { DiscoverySettings as DiscoverySettingsType } from '../../types/admin';
import { Loader2, Plus, Trash2 } from 'lucide-react';

interface DiscoverySettingsProps {
  settings: DiscoverySettingsType | null;
  loading: boolean;
  onUnsavedChange: () => void;
  onSaved: () => void;
}

export function DiscoverySettings({
  settings,
  loading,
  onUnsavedChange,
  onSaved,
}: DiscoverySettingsProps) {
  const [localSettings, setLocalSettings] = useState<DiscoverySettingsType>({
    scan_interval: 60,
    timeout: 3,
    offline_timeout: 30,
    stale_timeout: 300,
    udp_port: 9999,
    paired_interval: 0.5,
    network_ranges: [],
    manual_targets: [],
  });
  const [saving, setSaving] = useState(false);
  const [newTarget, setNewTarget] = useState('');
  const [newRange, setNewRange] = useState('');

  const toast = useToast();

  useEffect(() => {
    if (settings) {
      setLocalSettings(settings);
    }
  }, [settings]);

  const handleSave = async () => {
    setSaving(true);
    try {
      await adminApi.updateDiscoverySettings(localSettings);
      toast.success('Saved', 'Discovery settings saved. Restart SUT Discovery to apply.');
      onSaved();
    } catch (err) {
      toast.error('Save Failed', err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setSaving(false);
    }
  };

  const updateSetting = <K extends keyof DiscoverySettingsType>(
    key: K,
    value: DiscoverySettingsType[K]
  ) => {
    setLocalSettings(prev => ({ ...prev, [key]: value }));
    onUnsavedChange();
  };

  const addManualTarget = () => {
    if (newTarget && !localSettings.manual_targets.includes(newTarget)) {
      updateSetting('manual_targets', [...localSettings.manual_targets, newTarget]);
      setNewTarget('');
    }
  };

  const removeManualTarget = (ip: string) => {
    updateSetting('manual_targets', localSettings.manual_targets.filter(t => t !== ip));
  };

  const addNetworkRange = () => {
    if (newRange && !localSettings.network_ranges.includes(newRange)) {
      updateSetting('network_ranges', [...localSettings.network_ranges, newRange]);
      setNewRange('');
    }
  };

  const removeNetworkRange = (range: string) => {
    updateSetting('network_ranges', localSettings.network_ranges.filter(r => r !== range));
  };

  if (loading && !settings) {
    return (
      <div className="p-6">
        <div className="h-64 bg-surface animate-pulse rounded-lg" />
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-text-primary">Discovery Settings</h2>
        <p className="text-sm text-text-muted">
          Configure how SUTs are discovered on the network
        </p>
      </div>

      {/* Timing Settings */}
      <div className="bg-surface border border-border rounded-lg p-4">
        <h3 className="text-sm font-medium text-text-primary mb-4">Timing</h3>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-xs text-text-muted mb-1">Scan Interval (sec)</label>
            <input
              type="number"
              value={localSettings.scan_interval}
              onChange={e => updateSetting('scan_interval', parseInt(e.target.value) || 60)}
              className="w-full px-3 py-2 text-sm bg-surface-elevated border border-border rounded focus:outline-none focus:border-primary"
            />
          </div>
          <div>
            <label className="block text-xs text-text-muted mb-1">Connection Timeout (sec)</label>
            <input
              type="number"
              value={localSettings.timeout}
              onChange={e => updateSetting('timeout', parseInt(e.target.value) || 3)}
              className="w-full px-3 py-2 text-sm bg-surface-elevated border border-border rounded focus:outline-none focus:border-primary"
            />
          </div>
          <div>
            <label className="block text-xs text-text-muted mb-1">Offline Timeout (sec)</label>
            <input
              type="number"
              value={localSettings.offline_timeout}
              onChange={e => updateSetting('offline_timeout', parseInt(e.target.value) || 30)}
              className="w-full px-3 py-2 text-sm bg-surface-elevated border border-border rounded focus:outline-none focus:border-primary"
            />
          </div>
          <div>
            <label className="block text-xs text-text-muted mb-1">Stale Timeout (sec)</label>
            <input
              type="number"
              value={localSettings.stale_timeout}
              onChange={e => updateSetting('stale_timeout', parseInt(e.target.value) || 300)}
              className="w-full px-3 py-2 text-sm bg-surface-elevated border border-border rounded focus:outline-none focus:border-primary"
            />
          </div>
          <div>
            <label className="block text-xs text-text-muted mb-1">Paired Scan Interval (sec)</label>
            <input
              type="number"
              step="0.1"
              value={localSettings.paired_interval}
              onChange={e => updateSetting('paired_interval', parseFloat(e.target.value) || 0.5)}
              className="w-full px-3 py-2 text-sm bg-surface-elevated border border-border rounded focus:outline-none focus:border-primary"
            />
          </div>
          <div>
            <label className="block text-xs text-text-muted mb-1">UDP Port</label>
            <input
              type="number"
              value={localSettings.udp_port}
              onChange={e => updateSetting('udp_port', parseInt(e.target.value) || 9999)}
              className="w-full px-3 py-2 text-sm bg-surface-elevated border border-border rounded focus:outline-none focus:border-primary"
            />
          </div>
        </div>
      </div>

      {/* Manual Targets */}
      <div className="bg-surface border border-border rounded-lg p-4">
        <h3 className="text-sm font-medium text-text-primary mb-3">Manual Targets</h3>
        <p className="text-xs text-text-muted mb-3">
          Specific IP addresses to check for SUTs
        </p>
        <div className="flex gap-2 mb-3">
          <input
            type="text"
            value={newTarget}
            onChange={e => setNewTarget(e.target.value)}
            placeholder="192.168.1.100"
            className="flex-1 px-3 py-2 text-sm bg-surface-elevated border border-border rounded focus:outline-none focus:border-primary"
            onKeyDown={e => e.key === 'Enter' && addManualTarget()}
          />
          <button
            onClick={addManualTarget}
            className="flex items-center gap-1.5 px-3 py-2 text-sm bg-primary/20 text-primary rounded hover:bg-primary/30"
          >
            <Plus className="w-4 h-4" />
            Add
          </button>
        </div>
        <div className="flex flex-wrap gap-2">
          {localSettings.manual_targets.map(target => (
            <span
              key={target}
              className="flex items-center gap-1.5 px-2.5 py-1 bg-surface-elevated rounded text-sm"
            >
              {target}
              <button
                onClick={() => removeManualTarget(target)}
                className="text-text-muted hover:text-danger"
              >
                <Trash2 className="w-3 h-3" />
              </button>
            </span>
          ))}
          {localSettings.manual_targets.length === 0 && (
            <span className="text-sm text-text-muted">No manual targets configured</span>
          )}
        </div>
      </div>

      {/* Network Ranges */}
      <div className="bg-surface border border-border rounded-lg p-4">
        <h3 className="text-sm font-medium text-text-primary mb-3">Network Ranges</h3>
        <p className="text-xs text-text-muted mb-3">
          CIDR ranges to scan for SUTs (leave empty for auto-detection)
        </p>
        <div className="flex gap-2 mb-3">
          <input
            type="text"
            value={newRange}
            onChange={e => setNewRange(e.target.value)}
            placeholder="192.168.1.0/24"
            className="flex-1 px-3 py-2 text-sm bg-surface-elevated border border-border rounded focus:outline-none focus:border-primary"
            onKeyDown={e => e.key === 'Enter' && addNetworkRange()}
          />
          <button
            onClick={addNetworkRange}
            className="flex items-center gap-1.5 px-3 py-2 text-sm bg-primary/20 text-primary rounded hover:bg-primary/30"
          >
            <Plus className="w-4 h-4" />
            Add
          </button>
        </div>
        <div className="flex flex-wrap gap-2">
          {localSettings.network_ranges.map(range => (
            <span
              key={range}
              className="flex items-center gap-1.5 px-2.5 py-1 bg-surface-elevated rounded text-sm"
            >
              {range}
              <button
                onClick={() => removeNetworkRange(range)}
                className="text-text-muted hover:text-danger"
              >
                <Trash2 className="w-3 h-3" />
              </button>
            </span>
          ))}
          {localSettings.network_ranges.length === 0 && (
            <span className="text-sm text-text-muted">Auto-detect network ranges</span>
          )}
        </div>
      </div>

      {/* Save Button */}
      <div className="flex justify-end">
        <button
          onClick={handleSave}
          disabled={saving}
          className="flex items-center gap-2 px-4 py-2 bg-primary text-white rounded-lg hover:bg-primary-hover disabled:opacity-50 transition-colors"
        >
          {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
          Save Changes
        </button>
      </div>
    </div>
  );
}

export default DiscoverySettings;
