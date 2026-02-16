/**
 * TracingSettings - Tracing agent configuration tab
 */

import { useState, useEffect, useMemo } from 'react';
import { adminApi } from '../../api/adminApi';
import { useToast } from '../../contexts/ToastContext';
import type { TracingConfig, TracingAgent } from '../../types/admin';
import { Loader2, ChevronDown, ChevronRight, X, Plus, Terminal } from 'lucide-react';

interface TracingSettingsProps {
  config: TracingConfig | null;
  loading: boolean;
  onUnsavedChange: () => void;
  onSaved: () => void;
}

function buildCommandPreview(agent: TracingAgent): string {
  const parts: string[] = [];
  // Quote path if it contains spaces
  const exePath = agent.path.includes(' ') ? `"${agent.path}"` : agent.path;
  parts.push(exePath);
  parts.push(...agent.args);
  if (agent.has_duration) {
    if (agent.duration_style === 'equals') {
      parts.push(`${agent.duration_arg}<duration>`);
    } else {
      parts.push(agent.duration_arg, '<duration>');
    }
  }
  if (agent.output_style === 'equals') {
    parts.push(`${agent.output_arg}<filename>`);
  } else {
    parts.push(agent.output_arg, '<filename>');
  }
  return parts.join(' ');
}

const DEFAULT_CONFIG: TracingConfig = {
  output_dir: 'C:\\Traces',
  post_trace_buffer: 30,
  ssh: { timeout: 60, max_retries: 3, retry_delay: 5, user: '' },
  agents: {},
};

export function TracingSettings({
  config,
  loading,
  onUnsavedChange,
  onSaved,
}: TracingSettingsProps) {
  const [local, setLocal] = useState<TracingConfig>(DEFAULT_CONFIG);
  const [saving, setSaving] = useState(false);
  const [toggling, setToggling] = useState<string | null>(null);
  const [expandedSsh, setExpandedSsh] = useState(false);
  const [expandedAdvanced, setExpandedAdvanced] = useState<Set<string>>(new Set());
  const [newArgInputs, setNewArgInputs] = useState<Record<string, string>>({});

  const toast = useToast();

  useEffect(() => {
    if (config) {
      setLocal(config);
    }
  }, [config]);

  const handleSave = async () => {
    setSaving(true);
    try {
      await adminApi.updateTracingConfig(local);
      toast.success('Saved', 'Tracing configuration saved');
      onSaved();
    } catch (err) {
      toast.error('Save Failed', err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setSaving(false);
    }
  };

  const handleToggle = async (name: string) => {
    setToggling(name);
    try {
      await adminApi.toggleTracingAgent(name);
      // Optimistically update local state
      setLocal(prev => ({
        ...prev,
        agents: {
          ...prev.agents,
          [name]: { ...prev.agents[name], enabled: !prev.agents[name].enabled },
        },
      }));
      toast.success('Toggled', `${name} ${local.agents[name].enabled ? 'disabled' : 'enabled'}`);
    } catch (err) {
      toast.error('Toggle Failed', err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setToggling(null);
    }
  };

  const updateGlobal = <K extends keyof TracingConfig>(key: K, value: TracingConfig[K]) => {
    setLocal(prev => ({ ...prev, [key]: value }));
    onUnsavedChange();
  };

  const updateSsh = (key: keyof TracingConfig['ssh'], value: string | number) => {
    setLocal(prev => ({ ...prev, ssh: { ...prev.ssh, [key]: value } }));
    onUnsavedChange();
  };

  const updateAgent = (name: string, key: keyof TracingAgent, value: unknown) => {
    setLocal(prev => ({
      ...prev,
      agents: {
        ...prev.agents,
        [name]: { ...prev.agents[name], [key]: value },
      },
    }));
    onUnsavedChange();
  };

  const removeArg = (agentName: string, index: number) => {
    const agent = local.agents[agentName];
    const newArgs = agent.args.filter((_, i) => i !== index);
    updateAgent(agentName, 'args', newArgs);
  };

  const addArg = (agentName: string) => {
    const val = (newArgInputs[agentName] || '').trim();
    if (!val) return;
    const agent = local.agents[agentName];
    updateAgent(agentName, 'args', [...agent.args, val]);
    setNewArgInputs(prev => ({ ...prev, [agentName]: '' }));
  };

  const toggleAdvanced = (name: string) => {
    setExpandedAdvanced(prev => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  };

  // Safe accessors for potentially missing nested objects
  const agents = local.agents ?? {};
  const ssh = local.ssh ?? { timeout: 60, max_retries: 3, retry_delay: 5, user: '' };
  const previews = useMemo(() => {
    const result: Record<string, string> = {};
    for (const [name, agent] of Object.entries(agents)) {
      result[name] = buildCommandPreview(agent);
    }
    return result;
  }, [agents]);

  if (loading && !config) {
    return (
      <div className="p-6">
        <div className="h-64 bg-surface animate-pulse rounded-lg" />
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-lg font-semibold text-text-primary">Tracing Configuration</h2>
        <p className="text-sm text-text-muted">
          Configure tracing agents (PTAT, SoC Watch) that capture performance data during automation runs
        </p>
      </div>

      {/* Section 1: Global Settings */}
      <div className="bg-surface border border-border rounded-lg p-4 space-y-4">
        <h3 className="text-sm font-medium text-text-primary">Global Settings</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-text-primary mb-1">
              Output Directory
            </label>
            <p className="text-xs text-text-muted mb-2">
              Base directory on SUTs where trace files are saved
            </p>
            <input
              type="text"
              value={local.output_dir}
              onChange={e => updateGlobal('output_dir', e.target.value)}
              className="w-full px-3 py-2 text-sm bg-surface-elevated border border-border rounded-lg focus:outline-none focus:border-primary"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-text-primary mb-1">
              Post-Trace Buffer
            </label>
            <p className="text-xs text-text-muted mb-2">
              Seconds to wait before polling for agent completion
            </p>
            <div className="flex items-center gap-3">
              <input
                type="range"
                min={5}
                max={120}
                value={local.post_trace_buffer}
                onChange={e => updateGlobal('post_trace_buffer', parseInt(e.target.value))}
                className="flex-1"
              />
              <div className="flex items-center gap-1 min-w-[80px]">
                <input
                  type="number"
                  min={5}
                  max={120}
                  value={local.post_trace_buffer}
                  onChange={e => updateGlobal('post_trace_buffer', parseInt(e.target.value) || 5)}
                  className="w-16 px-2 py-1 text-sm text-center bg-surface-elevated border border-border rounded focus:outline-none focus:border-primary"
                />
                <span className="text-xs text-text-muted">sec</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Section 2: SSH Settings (collapsible) */}
      <div className="bg-surface border border-border rounded-lg">
        <button
          onClick={() => setExpandedSsh(!expandedSsh)}
          className="w-full flex items-center justify-between p-4 text-left hover:bg-surface-hover transition-colors rounded-lg"
        >
          <div>
            <h3 className="text-sm font-medium text-text-primary">SSH Settings</h3>
            <p className="text-xs text-text-muted">Connection settings for pulling trace files from SUTs</p>
          </div>
          {expandedSsh ? <ChevronDown className="w-4 h-4 text-text-muted" /> : <ChevronRight className="w-4 h-4 text-text-muted" />}
        </button>
        {expandedSsh && (
          <div className="px-4 pb-4 grid grid-cols-1 md:grid-cols-2 gap-4 border-t border-border pt-4">
            <div>
              <label className="block text-sm font-medium text-text-primary mb-1">Timeout</label>
              <div className="flex items-center gap-2">
                <input
                  type="number"
                  min={5}
                  max={300}
                  value={ssh.timeout}
                  onChange={e => updateSsh('timeout', parseInt(e.target.value) || 60)}
                  className="w-20 px-2 py-1 text-sm bg-surface-elevated border border-border rounded focus:outline-none focus:border-primary"
                />
                <span className="text-xs text-text-muted">seconds</span>
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-text-primary mb-1">Max Retries</label>
              <input
                type="number"
                min={0}
                max={10}
                value={ssh.max_retries}
                onChange={e => updateSsh('max_retries', parseInt(e.target.value) || 0)}
                className="w-20 px-2 py-1 text-sm bg-surface-elevated border border-border rounded focus:outline-none focus:border-primary"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-text-primary mb-1">Retry Delay</label>
              <div className="flex items-center gap-2">
                <input
                  type="number"
                  min={1}
                  max={60}
                  value={ssh.retry_delay}
                  onChange={e => updateSsh('retry_delay', parseInt(e.target.value) || 5)}
                  className="w-20 px-2 py-1 text-sm bg-surface-elevated border border-border rounded focus:outline-none focus:border-primary"
                />
                <span className="text-xs text-text-muted">seconds (exponential backoff)</span>
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-text-primary mb-1">SSH User</label>
              <input
                type="text"
                value={ssh.user}
                onChange={e => updateSsh('user', e.target.value)}
                placeholder="(current Windows user)"
                className="w-full px-3 py-2 text-sm bg-surface-elevated border border-border rounded-lg focus:outline-none focus:border-primary"
              />
            </div>
          </div>
        )}
      </div>

      {/* Section 3: Agent Cards */}
      <div className="space-y-4">
        <h3 className="text-sm font-medium text-text-primary">Tracing Agents</h3>
        {Object.entries(agents).map(([name, agent]) => (
          <div key={name} className="bg-surface border border-border rounded-lg overflow-hidden">
            {/* Agent Header */}
            <div className="flex items-center justify-between p-4">
              <div className="flex items-center gap-3">
                <span className="text-sm font-semibold text-text-primary uppercase tracking-wide">
                  {name}
                </span>
                <span className="text-xs text-text-muted">{agent.description}</span>
              </div>
              <button
                onClick={() => handleToggle(name)}
                disabled={toggling === name}
                className={`
                  relative w-11 h-6 rounded-full transition-colors
                  ${agent.enabled ? 'bg-primary' : 'bg-border'}
                  ${toggling === name ? 'opacity-50' : ''}
                `}
              >
                <span
                  className={`
                    absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform
                    ${agent.enabled ? 'translate-x-5' : 'translate-x-0'}
                  `}
                />
              </button>
            </div>

            <div className="px-4 pb-4 space-y-4 border-t border-border pt-4">
              {/* Exe Path */}
              <div>
                <label className="block text-xs font-medium text-text-secondary mb-1">
                  Executable Path
                </label>
                <input
                  type="text"
                  value={agent.path}
                  onChange={e => updateAgent(name, 'path', e.target.value)}
                  className="w-full px-3 py-2 text-sm font-mono bg-surface-elevated border border-border rounded-lg focus:outline-none focus:border-primary"
                />
              </div>

              {/* CLI Arguments */}
              <div>
                <label className="block text-xs font-medium text-text-secondary mb-1">
                  CLI Arguments
                </label>
                <div className="flex flex-wrap gap-2 mb-2">
                  {agent.args.map((arg, i) => (
                    <span
                      key={i}
                      className="inline-flex items-center gap-1 px-2 py-1 text-xs font-mono bg-surface-elevated border border-border rounded"
                    >
                      {arg}
                      <button
                        onClick={() => removeArg(name, i)}
                        className="text-text-muted hover:text-danger transition-colors"
                      >
                        <X className="w-3 h-3" />
                      </button>
                    </span>
                  ))}
                </div>
                <div className="flex items-center gap-2">
                  <input
                    type="text"
                    value={newArgInputs[name] || ''}
                    onChange={e => setNewArgInputs(prev => ({ ...prev, [name]: e.target.value }))}
                    onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addArg(name); } }}
                    placeholder="Add argument..."
                    className="flex-1 px-3 py-1.5 text-sm font-mono bg-surface-elevated border border-border rounded-lg focus:outline-none focus:border-primary"
                  />
                  <button
                    onClick={() => addArg(name)}
                    className="flex items-center gap-1 px-3 py-1.5 text-xs bg-surface-elevated hover:bg-surface-hover border border-border rounded-lg transition-colors"
                  >
                    <Plus className="w-3 h-3" /> Add
                  </button>
                </div>
              </div>

              {/* Advanced (collapsible) */}
              <div>
                <button
                  onClick={() => toggleAdvanced(name)}
                  className="flex items-center gap-1 text-xs text-text-muted hover:text-text-secondary transition-colors"
                >
                  {expandedAdvanced.has(name) ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
                  Advanced
                </button>
                {expandedAdvanced.has(name) && (
                  <div className="mt-2 grid grid-cols-2 md:grid-cols-3 gap-3">
                    <div>
                      <label className="block text-xs text-text-muted mb-1">Duration Arg</label>
                      <input
                        type="text"
                        value={agent.duration_arg}
                        onChange={e => updateAgent(name, 'duration_arg', e.target.value)}
                        className="w-full px-2 py-1 text-xs font-mono bg-surface-elevated border border-border rounded focus:outline-none focus:border-primary"
                      />
                    </div>
                    <div>
                      <label className="block text-xs text-text-muted mb-1">Duration Style</label>
                      <select
                        value={agent.duration_style}
                        onChange={e => updateAgent(name, 'duration_style', e.target.value)}
                        className="w-full px-2 py-1 text-xs bg-surface-elevated border border-border rounded focus:outline-none focus:border-primary"
                      >
                        <option value="space">space (-t 60)</option>
                        <option value="equals">equals (-t=60)</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-xs text-text-muted mb-1">Output Arg</label>
                      <input
                        type="text"
                        value={agent.output_arg}
                        onChange={e => updateAgent(name, 'output_arg', e.target.value)}
                        className="w-full px-2 py-1 text-xs font-mono bg-surface-elevated border border-border rounded focus:outline-none focus:border-primary"
                      />
                    </div>
                    <div>
                      <label className="block text-xs text-text-muted mb-1">Output Style</label>
                      <select
                        value={agent.output_style}
                        onChange={e => updateAgent(name, 'output_style', e.target.value)}
                        className="w-full px-2 py-1 text-xs bg-surface-elevated border border-border rounded focus:outline-none focus:border-primary"
                      >
                        <option value="space">space (-o file)</option>
                        <option value="equals">equals (-o=file)</option>
                      </select>
                    </div>
                    <div className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        checked={agent.has_duration}
                        onChange={e => updateAgent(name, 'has_duration', e.target.checked)}
                        className="rounded border-border"
                      />
                      <label className="text-xs text-text-muted">Has Duration</label>
                    </div>
                    <div className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        checked={agent.output_filename_only ?? false}
                        onChange={e => updateAgent(name, 'output_filename_only', e.target.checked)}
                        className="rounded border-border"
                      />
                      <label className="text-xs text-text-muted">Filename Only</label>
                    </div>
                  </div>
                )}
              </div>

              {/* Command Preview */}
              <div>
                <div className="flex items-center gap-1 mb-1">
                  <Terminal className="w-3 h-3 text-text-muted" />
                  <span className="text-xs font-medium text-text-muted">Command Preview</span>
                </div>
                <div className="px-3 py-2 text-xs font-mono bg-black/40 text-green-400 rounded-lg overflow-x-auto whitespace-nowrap">
                  {previews[name]}
                </div>
              </div>
            </div>
          </div>
        ))}
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

export default TracingSettings;
