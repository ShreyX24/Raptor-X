/**
 * AutomationSettings - Automation timing and behavior settings
 */

import { useState, useEffect } from 'react';
import { adminApi } from '../../api/adminApi';
import { useToast } from '../../contexts/ToastContext';
import type { AutomationSettings as AutomationSettingsType } from '../../types/admin';
import { Loader2 } from 'lucide-react';

interface AutomationSettingsProps {
  settings: AutomationSettingsType | null;
  loading: boolean;
  onUnsavedChange: () => void;
  onSaved: () => void;
}

interface SettingField {
  key: keyof AutomationSettingsType;
  label: string;
  description: string;
  unit: string;
  min: number;
  max: number;
}

const SETTINGS_FIELDS: SettingField[] = [
  {
    key: 'startup_wait',
    label: 'Startup Wait',
    description: 'Time to wait for game to fully load after launch',
    unit: 'seconds',
    min: 10,
    max: 300,
  },
  {
    key: 'benchmark_duration',
    label: 'Benchmark Duration',
    description: 'Default benchmark run time if not specified by game config',
    unit: 'seconds',
    min: 30,
    max: 600,
  },
  {
    key: 'screenshot_interval',
    label: 'Screenshot Interval',
    description: 'Time between screenshots during automation',
    unit: 'seconds',
    min: 1,
    max: 60,
  },
  {
    key: 'retry_count',
    label: 'Retry Count',
    description: 'Number of retries on automation failure',
    unit: 'retries',
    min: 0,
    max: 10,
  },
  {
    key: 'step_timeout',
    label: 'Step Timeout',
    description: 'Maximum time to wait for each automation step',
    unit: 'seconds',
    min: 10,
    max: 300,
  },
  {
    key: 'process_detection_timeout',
    label: 'Process Detection Timeout',
    description: 'Maximum time to wait for game process to appear',
    unit: 'seconds',
    min: 30,
    max: 600,
  },
];

export function AutomationSettings({
  settings,
  loading,
  onUnsavedChange,
  onSaved,
}: AutomationSettingsProps) {
  const [localSettings, setLocalSettings] = useState<AutomationSettingsType>({
    startup_wait: 80,
    benchmark_duration: 100,
    screenshot_interval: 5,
    retry_count: 3,
    step_timeout: 60,
    process_detection_timeout: 120,
  });
  const [saving, setSaving] = useState(false);

  const toast = useToast();

  useEffect(() => {
    if (settings) {
      setLocalSettings(settings);
    }
  }, [settings]);

  const handleSave = async () => {
    setSaving(true);
    try {
      await adminApi.updateAutomationSettings(localSettings);
      toast.success('Saved', 'Automation settings saved');
      onSaved();
    } catch (err) {
      toast.error('Save Failed', err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setSaving(false);
    }
  };

  const updateSetting = (key: keyof AutomationSettingsType, value: number) => {
    setLocalSettings(prev => ({ ...prev, [key]: value }));
    onUnsavedChange();
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
        <h2 className="text-lg font-semibold text-text-primary">Automation Settings</h2>
        <p className="text-sm text-text-muted">
          Configure timing and behavior for game automation
        </p>
      </div>

      <div className="bg-surface border border-border rounded-lg p-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {SETTINGS_FIELDS.map(field => (
            <div key={field.key}>
              <label className="block text-sm font-medium text-text-primary mb-1">
                {field.label}
              </label>
              <p className="text-xs text-text-muted mb-2">{field.description}</p>
              <div className="flex items-center gap-3">
                <input
                  type="range"
                  min={field.min}
                  max={field.max}
                  value={localSettings[field.key]}
                  onChange={e => updateSetting(field.key, parseInt(e.target.value))}
                  className="flex-1"
                />
                <div className="flex items-center gap-1 min-w-[80px]">
                  <input
                    type="number"
                    min={field.min}
                    max={field.max}
                    value={localSettings[field.key]}
                    onChange={e => updateSetting(field.key, parseInt(e.target.value) || field.min)}
                    className="w-16 px-2 py-1 text-sm text-center bg-surface-elevated border border-border rounded focus:outline-none focus:border-primary"
                  />
                  <span className="text-xs text-text-muted">{field.unit.slice(0, 3)}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Quick Presets */}
      <div className="bg-surface border border-border rounded-lg p-4">
        <h3 className="text-sm font-medium text-text-primary mb-3">Quick Presets</h3>
        <div className="flex gap-3">
          <button
            onClick={() => {
              setLocalSettings({
                startup_wait: 60,
                benchmark_duration: 60,
                screenshot_interval: 3,
                retry_count: 2,
                step_timeout: 45,
                process_detection_timeout: 90,
              });
              onUnsavedChange();
            }}
            className="px-3 py-2 text-sm bg-surface-elevated hover:bg-surface-hover border border-border rounded transition-colors"
          >
            Fast (for SSDs)
          </button>
          <button
            onClick={() => {
              setLocalSettings({
                startup_wait: 80,
                benchmark_duration: 100,
                screenshot_interval: 5,
                retry_count: 3,
                step_timeout: 60,
                process_detection_timeout: 120,
              });
              onUnsavedChange();
            }}
            className="px-3 py-2 text-sm bg-surface-elevated hover:bg-surface-hover border border-border rounded transition-colors"
          >
            Balanced (Default)
          </button>
          <button
            onClick={() => {
              setLocalSettings({
                startup_wait: 120,
                benchmark_duration: 150,
                screenshot_interval: 10,
                retry_count: 5,
                step_timeout: 90,
                process_detection_timeout: 180,
              });
              onUnsavedChange();
            }}
            className="px-3 py-2 text-sm bg-surface-elevated hover:bg-surface-hover border border-border rounded transition-colors"
          >
            Slow (for HDDs)
          </button>
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

export default AutomationSettings;
