/**
 * ProfileManager - Environment profiles management
 */

import { useState, useEffect } from 'react';
import { adminApi } from '../../api/adminApi';
import { useToast } from '../../contexts/ToastContext';
import type { ProfilesResponse, Profile } from '../../types/admin';
import { Plus, Trash2, Check, Loader2 } from 'lucide-react';

interface ProfileManagerProps {
  profiles: ProfilesResponse | null;
  loading: boolean;
  onUnsavedChange: () => void;
  onSaved: () => void;
}

export function ProfileManager({
  profiles,
  loading,
  onUnsavedChange: _onUnsavedChange,
  onSaved,
}: ProfileManagerProps) {
  const [profileList, setProfileList] = useState<Profile[]>([]);
  const [activeProfile, setActiveProfile] = useState('local');
  const [editingProfile, setEditingProfile] = useState<string | null>(null);
  const [newProfileName, setNewProfileName] = useState('');
  const [saving, setSaving] = useState(false);
  const [activating, setActivating] = useState<string | null>(null);

  const toast = useToast();

  useEffect(() => {
    if (profiles) {
      setProfileList(profiles.profiles);
      setActiveProfile(profiles.active_profile);
    }
  }, [profiles]);

  const handleActivate = async (name: string) => {
    setActivating(name);
    try {
      const result = await adminApi.activateProfile(name);
      setActiveProfile(name);
      if (result.restart_required) {
        toast.warning('Restart Required', 'Profile activated. Restart services to apply changes.');
      } else {
        toast.success('Activated', `Profile "${name}" is now active`);
      }
      onSaved();
    } catch (err) {
      toast.error('Activation Failed', err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setActivating(null);
    }
  };

  const handleDelete = async (name: string) => {
    if (name === 'local') {
      toast.error('Cannot Delete', 'The default "local" profile cannot be deleted');
      return;
    }

    try {
      await adminApi.deleteProfile(name);
      setProfileList(prev => prev.filter(p => p.name !== name));
      toast.success('Deleted', `Profile "${name}" deleted`);
      onSaved();
    } catch (err) {
      toast.error('Delete Failed', err instanceof Error ? err.message : 'Unknown error');
    }
  };

  const handleCreateProfile = async () => {
    if (!newProfileName.trim()) {
      toast.error('Invalid Name', 'Profile name cannot be empty');
      return;
    }

    const slug = newProfileName.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, '');

    if (profileList.some(p => p.name === slug)) {
      toast.error('Already Exists', `Profile "${slug}" already exists`);
      return;
    }

    setSaving(true);
    try {
      await adminApi.updateProfile(slug, {
        description: `Custom profile: ${newProfileName}`,
        overrides: {},
      });
      setProfileList(prev => [
        ...prev,
        { name: slug, description: `Custom profile: ${newProfileName}`, overrides: {}, is_active: false, is_default: false },
      ]);
      setNewProfileName('');
      toast.success('Created', `Profile "${slug}" created`);
      onSaved();
    } catch (err) {
      toast.error('Create Failed', err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setSaving(false);
    }
  };

  const handleUpdateDescription = async (name: string, description: string) => {
    const profile = profileList.find(p => p.name === name);
    if (!profile) return;

    try {
      await adminApi.updateProfile(name, {
        description,
        overrides: profile.overrides,
      });
      setProfileList(prev => prev.map(p => (p.name === name ? { ...p, description } : p)));
      setEditingProfile(null);
      toast.success('Updated', 'Profile description updated');
      onSaved();
    } catch (err) {
      toast.error('Update Failed', err instanceof Error ? err.message : 'Unknown error');
    }
  };

  if (loading && !profiles) {
    return (
      <div className="p-6">
        <div className="h-64 bg-surface animate-pulse rounded-lg" />
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-text-primary">Environment Profiles</h2>
        <p className="text-sm text-text-muted">
          Switch between different environment configurations
        </p>
      </div>

      {/* Create New Profile */}
      <div className="bg-surface border border-border rounded-lg p-4">
        <h3 className="text-sm font-medium text-text-primary mb-3">Create New Profile</h3>
        <div className="flex gap-2">
          <input
            type="text"
            value={newProfileName}
            onChange={e => setNewProfileName(e.target.value)}
            placeholder="Profile name"
            className="flex-1 px-3 py-2 text-sm bg-surface-elevated border border-border rounded focus:outline-none focus:border-primary"
            onKeyDown={e => e.key === 'Enter' && handleCreateProfile()}
          />
          <button
            onClick={handleCreateProfile}
            disabled={saving || !newProfileName.trim()}
            className="flex items-center gap-1.5 px-3 py-2 text-sm bg-primary text-white rounded hover:bg-primary-hover disabled:opacity-50 transition-colors"
          >
            {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
            Create
          </button>
        </div>
      </div>

      {/* Profile List */}
      <div className="bg-surface border border-border rounded-lg p-4">
        <h3 className="text-sm font-medium text-text-primary mb-4">Profiles</h3>
        <div className="space-y-3">
          {profileList.map(profile => (
            <div
              key={profile.name}
              className={`
                p-4 rounded-lg border transition-colors
                ${profile.name === activeProfile
                  ? 'bg-primary/10 border-primary/30'
                  : 'bg-surface-elevated border-border hover:border-border-hover'
                }
              `}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  {profile.name === activeProfile && (
                    <span className="flex items-center justify-center w-5 h-5 bg-primary rounded-full">
                      <Check className="w-3 h-3 text-white" />
                    </span>
                  )}
                  <div>
                    <h4 className="font-medium text-text-primary">{profile.name}</h4>
                    {editingProfile === profile.name ? (
                      <input
                        type="text"
                        defaultValue={profile.description}
                        onBlur={e => handleUpdateDescription(profile.name, e.target.value)}
                        onKeyDown={e => {
                          if (e.key === 'Enter') {
                            handleUpdateDescription(profile.name, e.currentTarget.value);
                          } else if (e.key === 'Escape') {
                            setEditingProfile(null);
                          }
                        }}
                        autoFocus
                        className="text-xs bg-transparent border-b border-primary focus:outline-none text-text-secondary"
                      />
                    ) : (
                      <p
                        className="text-xs text-text-muted cursor-pointer hover:text-text-secondary"
                        onClick={() => setEditingProfile(profile.name)}
                      >
                        {profile.description || 'Click to add description'}
                      </p>
                    )}
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  {profile.name !== activeProfile && (
                    <button
                      onClick={() => handleActivate(profile.name)}
                      disabled={activating === profile.name}
                      className="px-3 py-1.5 text-xs bg-primary/20 text-primary rounded hover:bg-primary/30 disabled:opacity-50 transition-colors"
                    >
                      {activating === profile.name ? (
                        <Loader2 className="w-3 h-3 animate-spin" />
                      ) : (
                        'Activate'
                      )}
                    </button>
                  )}
                  {!profile.is_default && (
                    <button
                      onClick={() => handleDelete(profile.name)}
                      className="p-1.5 text-text-muted hover:text-danger hover:bg-danger/10 rounded transition-colors"
                      title="Delete profile"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  )}
                </div>
              </div>

              {/* Show overrides count if any */}
              {Object.keys(profile.overrides).length > 0 && (
                <div className="mt-2 pt-2 border-t border-border/50">
                  <p className="text-xs text-text-muted">
                    {Object.keys(profile.overrides).length} service override(s)
                  </p>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Info Box */}
      <div className="bg-surface-elevated border border-border rounded-lg p-4">
        <h3 className="text-sm font-medium text-text-primary mb-2">Profile Overrides</h3>
        <p className="text-xs text-text-muted">
          Profiles can override service settings. When a profile is active, its overrides
          are applied on top of the base configuration. Configure overrides in the Services tab
          or edit the config file directly at <code className="text-primary">~/.gemma/service_manager_config.json</code>
        </p>
      </div>
    </div>
  );
}

export default ProfileManager;
