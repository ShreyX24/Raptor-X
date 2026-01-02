/**
 * SteamAccountsManager - Steam account pairs management
 */

import { useState, useEffect } from 'react';
import { adminApi } from '../../api/adminApi';
import { useToast } from '../../contexts/ToastContext';
import type { SteamAccountsResponse, SteamAccountPair } from '../../types/admin';
import { Plus, Trash2, Eye, EyeOff, Loader2 } from 'lucide-react';

interface SteamAccountsManagerProps {
  accounts: SteamAccountsResponse | null;
  loading: boolean;
  onUnsavedChange: () => void;
  onSaved: () => void;
}

export function SteamAccountsManager({
  accounts,
  loading,
  onUnsavedChange,
  onSaved,
}: SteamAccountsManagerProps) {
  const [pairs, setPairs] = useState<SteamAccountPair[]>([]);
  const [loginTimeout, setLoginTimeout] = useState(180);
  const [showPasswords, setShowPasswords] = useState<Record<number, boolean>>({});
  const [saving, setSaving] = useState(false);

  const toast = useToast();

  useEffect(() => {
    if (accounts) {
      setPairs(accounts.pairs);
      setLoginTimeout(accounts.login_timeout);
    }
  }, [accounts]);

  const handleSave = async () => {
    setSaving(true);
    try {
      await adminApi.updateSteamAccounts({ pairs, login_timeout: loginTimeout });
      toast.success('Saved', 'Steam accounts saved');
      onSaved();
    } catch (err) {
      toast.error('Save Failed', err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setSaving(false);
    }
  };

  const addPair = () => {
    setPairs(prev => [
      ...prev,
      {
        name: `Pair ${prev.length + 1}`,
        af_username: '',
        af_password: '',
        gz_username: '',
        gz_password: '',
        enabled: true,
      },
    ]);
    onUnsavedChange();
  };

  const removePair = (index: number) => {
    setPairs(prev => prev.filter((_, i) => i !== index));
    onUnsavedChange();
  };

  const updatePair = (index: number, updates: Partial<SteamAccountPair>) => {
    setPairs(prev => prev.map((p, i) => (i === index ? { ...p, ...updates } : p)));
    onUnsavedChange();
  };

  const togglePasswordVisibility = (index: number) => {
    setShowPasswords(prev => ({ ...prev, [index]: !prev[index] }));
  };

  if (loading && !accounts) {
    return (
      <div className="p-6">
        <div className="h-64 bg-surface animate-pulse rounded-lg" />
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-text-primary">Steam Accounts</h2>
        <p className="text-sm text-text-muted">
          Manage Steam account pairs for multi-SUT concurrent automation
        </p>
      </div>

      {/* Info Box */}
      <div className="bg-primary/5 border border-primary/20 rounded-lg p-4">
        <h3 className="text-sm font-medium text-primary mb-2">Account Pairs Explained</h3>
        <p className="text-xs text-text-secondary">
          Each pair contains two Steam accounts: one for games A-F and one for games G-Z.
          This allows running automation on two different games simultaneously without
          Steam login conflicts.
        </p>
      </div>

      {/* Login Timeout */}
      <div className="bg-surface border border-border rounded-lg p-4">
        <label className="block text-sm font-medium text-text-primary mb-1">
          Login Timeout
        </label>
        <p className="text-xs text-text-muted mb-2">
          Maximum time to wait for Steam login to complete
        </p>
        <div className="flex items-center gap-3">
          <input
            type="range"
            min={30}
            max={600}
            value={loginTimeout}
            onChange={e => { setLoginTimeout(parseInt(e.target.value)); onUnsavedChange(); }}
            className="flex-1"
          />
          <div className="flex items-center gap-1">
            <input
              type="number"
              min={30}
              max={600}
              value={loginTimeout}
              onChange={e => { setLoginTimeout(parseInt(e.target.value) || 180); onUnsavedChange(); }}
              className="w-20 px-2 py-1 text-sm text-center bg-surface-elevated border border-border rounded focus:outline-none focus:border-primary"
            />
            <span className="text-xs text-text-muted">sec</span>
          </div>
        </div>
      </div>

      {/* Account Pairs */}
      <div className="bg-surface border border-border rounded-lg p-4">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-medium text-text-primary">Account Pairs</h3>
          <button
            onClick={addPair}
            className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs bg-primary/20 text-primary rounded hover:bg-primary/30 transition-colors"
          >
            <Plus className="w-3 h-3" />
            Add Pair
          </button>
        </div>

        {pairs.length === 0 ? (
          <p className="text-sm text-text-muted py-4 text-center">
            No account pairs configured. Add a pair to get started.
          </p>
        ) : (
          <div className="space-y-4">
            {pairs.map((pair, index) => (
              <div
                key={index}
                className="bg-surface-elevated rounded-lg p-4 border border-border"
              >
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-3">
                    <input
                      type="checkbox"
                      checked={pair.enabled}
                      onChange={e => updatePair(index, { enabled: e.target.checked })}
                      className="w-4 h-4"
                    />
                    <input
                      type="text"
                      value={pair.name}
                      onChange={e => updatePair(index, { name: e.target.value })}
                      className="px-2 py-1 text-sm font-medium bg-transparent border-b border-transparent hover:border-border focus:border-primary focus:outline-none"
                    />
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => togglePasswordVisibility(index)}
                      className="p-1.5 text-text-muted hover:text-text-primary hover:bg-surface-hover rounded transition-colors"
                      title={showPasswords[index] ? 'Hide passwords' : 'Show passwords'}
                    >
                      {showPasswords[index] ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                    <button
                      onClick={() => removePair(index)}
                      className="p-1.5 text-text-muted hover:text-danger hover:bg-danger/10 rounded transition-colors"
                      title="Remove pair"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  {/* A-F Account */}
                  <div>
                    <h4 className="text-xs font-medium text-emerald-400 mb-2">Games A-F Account</h4>
                    <div className="space-y-2">
                      <input
                        type="text"
                        value={pair.af_username}
                        onChange={e => updatePair(index, { af_username: e.target.value })}
                        placeholder="Username"
                        className="w-full px-3 py-2 text-sm bg-surface border border-border rounded focus:outline-none focus:border-primary"
                      />
                      <input
                        type={showPasswords[index] ? 'text' : 'password'}
                        value={pair.af_password}
                        onChange={e => updatePair(index, { af_password: e.target.value })}
                        placeholder="Password"
                        className="w-full px-3 py-2 text-sm bg-surface border border-border rounded focus:outline-none focus:border-primary"
                      />
                    </div>
                  </div>

                  {/* G-Z Account */}
                  <div>
                    <h4 className="text-xs font-medium text-cyan-400 mb-2">Games G-Z Account</h4>
                    <div className="space-y-2">
                      <input
                        type="text"
                        value={pair.gz_username}
                        onChange={e => updatePair(index, { gz_username: e.target.value })}
                        placeholder="Username"
                        className="w-full px-3 py-2 text-sm bg-surface border border-border rounded focus:outline-none focus:border-primary"
                      />
                      <input
                        type={showPasswords[index] ? 'text' : 'password'}
                        value={pair.gz_password}
                        onChange={e => updatePair(index, { gz_password: e.target.value })}
                        placeholder="Password"
                        className="w-full px-3 py-2 text-sm bg-surface border border-border rounded focus:outline-none focus:border-primary"
                      />
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
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

export default SteamAccountsManager;
