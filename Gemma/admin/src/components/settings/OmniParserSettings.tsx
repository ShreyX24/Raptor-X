/**
 * OmniParserSettings - OmniParser configuration tab
 */

import { useState, useEffect } from 'react';
import { adminApi } from '../../api/adminApi';
import { useToast } from '../../contexts/ToastContext';
import type { OmniParserSettings as OmniParserSettingsType, OmniParserServer } from '../../types/admin';
import {
  Plus,
  Trash2,
  TestTube,
  CheckCircle,
  XCircle,
  Loader2,
  Server,
  Cpu,
} from 'lucide-react';

interface OmniParserSettingsProps {
  settings: OmniParserSettingsType | null;
  loading: boolean;
  onUnsavedChange: () => void;
  onSaved: () => void;
}

type Mode = 'local' | 'remote';

export function OmniParserSettings({
  settings,
  loading,
  onUnsavedChange,
  onSaved,
}: OmniParserSettingsProps) {
  const [mode, setMode] = useState<Mode>('remote');
  const [instanceCount, setInstanceCount] = useState(0);
  const [servers, setServers] = useState<OmniParserServer[]>([]);
  const [omniparserDir, setOmniparserDir] = useState('');
  const [saving, setSaving] = useState(false);
  const [testingServer, setTestingServer] = useState<string | null>(null);
  const [serverStatus, setServerStatus] = useState<Record<string, 'online' | 'offline' | 'testing'>>({});

  const toast = useToast();

  // Initialize from settings
  useEffect(() => {
    if (settings) {
      setInstanceCount(settings.instance_count);
      setServers(settings.servers);
      setOmniparserDir(settings.omniparser_dir);
      setMode(settings.instance_count > 0 ? 'local' : 'remote');
    }
  }, [settings]);

  const handleSave = async () => {
    setSaving(true);
    try {
      await adminApi.updateOmniParserSettings({
        instance_count: mode === 'local' ? instanceCount : 0,
        servers: mode === 'remote' ? servers : [],
        omniparser_dir: omniparserDir,
      });
      toast.success('Saved', 'OmniParser settings saved. Restart Queue Service to apply.');
      onSaved();
    } catch (err) {
      toast.error('Save Failed', err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setSaving(false);
    }
  };

  const handleTestServer = async (url: string) => {
    setTestingServer(url);
    setServerStatus(prev => ({ ...prev, [url]: 'testing' }));
    try {
      const result = await adminApi.testOmniParserServer(url);
      setServerStatus(prev => ({ ...prev, [url]: result.status === 'online' ? 'online' : 'offline' }));
      if (result.status === 'online') {
        toast.success('Server Online', `Response time: ${result.response_time}ms`);
      } else {
        toast.error('Server Offline', result.error || 'Connection failed');
      }
    } catch (err) {
      setServerStatus(prev => ({ ...prev, [url]: 'offline' }));
      toast.error('Test Failed', err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setTestingServer(null);
    }
  };

  const addServer = () => {
    setServers(prev => [
      ...prev,
      { name: `Server ${prev.length + 1}`, url: 'http://localhost:8000', enabled: true },
    ]);
    onUnsavedChange();
  };

  const removeServer = (index: number) => {
    setServers(prev => prev.filter((_, i) => i !== index));
    onUnsavedChange();
  };

  const updateServer = (index: number, updates: Partial<OmniParserServer>) => {
    setServers(prev => prev.map((s, i) => (i === index ? { ...s, ...updates } : s)));
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
        <h2 className="text-lg font-semibold text-text-primary">OmniParser Settings</h2>
        <p className="text-sm text-text-muted">
          Configure vision AI servers for UI element detection
        </p>
      </div>

      {/* Mode Selection */}
      <div className="bg-surface border border-border rounded-lg p-4">
        <h3 className="text-sm font-medium text-text-primary mb-3">Mode</h3>
        <div className="flex gap-4">
          <label className="flex items-center gap-3 p-3 border border-border rounded-lg cursor-pointer hover:bg-surface-elevated transition-colors">
            <input
              type="radio"
              checked={mode === 'local'}
              onChange={() => { setMode('local'); onUnsavedChange(); }}
              className="w-4 h-4"
            />
            <div className="flex items-center gap-2">
              <Cpu className="w-5 h-5 text-primary" />
              <div>
                <p className="font-medium text-text-primary">Local Instances</p>
                <p className="text-xs text-text-muted">Run OmniParser on this machine (ports 8000-8004)</p>
              </div>
            </div>
          </label>

          <label className="flex items-center gap-3 p-3 border border-border rounded-lg cursor-pointer hover:bg-surface-elevated transition-colors">
            <input
              type="radio"
              checked={mode === 'remote'}
              onChange={() => { setMode('remote'); onUnsavedChange(); }}
              className="w-4 h-4"
            />
            <div className="flex items-center gap-2">
              <Server className="w-5 h-5 text-primary" />
              <div>
                <p className="font-medium text-text-primary">Remote Servers</p>
                <p className="text-xs text-text-muted">Connect to external OmniParser servers</p>
              </div>
            </div>
          </label>
        </div>
      </div>

      {/* Local Instances Config */}
      {mode === 'local' && (
        <div className="bg-surface border border-border rounded-lg p-4">
          <h3 className="text-sm font-medium text-text-primary mb-3">Local Instances</h3>
          <div className="space-y-4">
            <div>
              <label className="block text-xs text-text-muted mb-1">Instance Count (0-5)</label>
              <div className="flex items-center gap-4">
                <input
                  type="range"
                  min="0"
                  max="5"
                  value={instanceCount}
                  onChange={e => { setInstanceCount(parseInt(e.target.value)); onUnsavedChange(); }}
                  className="flex-1"
                />
                <span className="w-8 text-center font-mono text-text-primary">{instanceCount}</span>
              </div>
              <p className="text-xs text-text-muted mt-1">
                Instances will run on ports 8000-{8000 + Math.max(0, instanceCount - 1)}
              </p>
            </div>

            <div>
              <label className="block text-xs text-text-muted mb-1">OmniParser Directory</label>
              <input
                type="text"
                value={omniparserDir}
                onChange={e => { setOmniparserDir(e.target.value); onUnsavedChange(); }}
                placeholder="C:\path\to\omniparserserver"
                className="w-full px-3 py-2 text-sm bg-surface-elevated border border-border rounded focus:outline-none focus:border-primary"
              />
            </div>
          </div>
        </div>
      )}

      {/* Remote Servers Config */}
      {mode === 'remote' && (
        <div className="bg-surface border border-border rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-medium text-text-primary">Remote Servers</h3>
            <button
              onClick={addServer}
              className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs bg-primary/20 text-primary rounded hover:bg-primary/30 transition-colors"
            >
              <Plus className="w-3 h-3" />
              Add Server
            </button>
          </div>

          {servers.length === 0 ? (
            <p className="text-sm text-text-muted py-4 text-center">
              No servers configured. Add a server to get started.
            </p>
          ) : (
            <div className="space-y-3">
              {servers.map((server, index) => (
                <div
                  key={index}
                  className="flex items-center gap-3 p-3 bg-surface-elevated rounded-lg"
                >
                  <input
                    type="checkbox"
                    checked={server.enabled}
                    onChange={e => updateServer(index, { enabled: e.target.checked })}
                    className="w-4 h-4"
                  />
                  <input
                    type="text"
                    value={server.name}
                    onChange={e => updateServer(index, { name: e.target.value })}
                    placeholder="Server name"
                    className="w-32 px-2 py-1.5 text-sm bg-surface border border-border rounded focus:outline-none focus:border-primary"
                  />
                  <input
                    type="text"
                    value={server.url}
                    onChange={e => updateServer(index, { url: e.target.value })}
                    placeholder="http://localhost:8000"
                    className="flex-1 px-2 py-1.5 text-sm bg-surface border border-border rounded focus:outline-none focus:border-primary"
                  />
                  <div className="flex items-center gap-2">
                    {serverStatus[server.url] === 'online' && (
                      <CheckCircle className="w-4 h-4 text-success" />
                    )}
                    {serverStatus[server.url] === 'offline' && (
                      <XCircle className="w-4 h-4 text-danger" />
                    )}
                    <button
                      onClick={() => handleTestServer(server.url)}
                      disabled={testingServer === server.url}
                      className="p-1.5 text-text-muted hover:text-text-primary hover:bg-surface-hover rounded transition-colors disabled:opacity-50"
                      title="Test connection"
                    >
                      {testingServer === server.url ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        <TestTube className="w-4 h-4" />
                      )}
                    </button>
                    <button
                      onClick={() => removeServer(index)}
                      className="p-1.5 text-text-muted hover:text-danger hover:bg-danger/10 rounded transition-colors"
                      title="Remove server"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

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

export default OmniParserSettings;
