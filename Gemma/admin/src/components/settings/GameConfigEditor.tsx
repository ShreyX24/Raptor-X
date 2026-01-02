/**
 * GameConfigEditor - YAML editor for game configurations
 * TODO: Install @monaco-editor/react for syntax highlighting
 * npm install @monaco-editor/react
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { adminApi } from '../../api/adminApi';
import { useToast } from '../../contexts/ToastContext';
import type { GameListItem, YamlValidationResult } from '../../types/admin';
import {
  FileText,
  Plus,
  Trash2,
  Save,
  AlertTriangle,
  CheckCircle,
  Loader2,
  RefreshCw,
  Upload,
  Image,
  ExternalLink,
} from 'lucide-react';

// Steam CDN URL for header images
const STEAM_CDN_URL = 'https://cdn.cloudflare.steamstatic.com/steam/apps';

interface GameConfigEditorProps {
  onUnsavedChange: () => void;
  onSaved: () => void;
}

export function GameConfigEditor({ onUnsavedChange, onSaved }: GameConfigEditorProps) {
  const [games, setGames] = useState<GameListItem[]>([]);
  const [selectedGame, setSelectedGame] = useState<string | null>(null);
  const [yamlContent, setYamlContent] = useState('');
  const [originalContent, setOriginalContent] = useState('');
  const [validation, setValidation] = useState<YamlValidationResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingYaml, setLoadingYaml] = useState(false);
  const [saving, setSaving] = useState(false);
  const [validating, setValidating] = useState(false);
  const [showNewGameForm, setShowNewGameForm] = useState(false);
  const [newGameName, setNewGameName] = useState('');
  const [showImagePanel, setShowImagePanel] = useState(false);
  const [uploadingImage, setUploadingImage] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const toast = useToast();
  // Use ref to avoid re-creating callbacks when toast changes
  const toastRef = useRef(toast);
  toastRef.current = toast;

  // Get current game's steam_app_id from games list
  const currentGameInfo = games.find(g => g.name === selectedGame);
  const steamAppId = currentGameInfo?.steam_app_id;

  // Load games list
  const loadGames = useCallback(async () => {
    setLoading(true);
    try {
      const result = await adminApi.getGamesList();
      setGames(result.games);
    } catch (err) {
      toastRef.current.error('Load Failed', err instanceof Error ? err.message : 'Failed to load games');
    } finally {
      setLoading(false);
    }
  }, []); // No dependencies - uses ref for toast

  // Load games once on mount
  useEffect(() => {
    loadGames();
  }, []); // Empty dependency - only run once

  // Load selected game's YAML
  const loadGameYaml = useCallback(async (name: string) => {
    setLoadingYaml(true);
    setValidation(null);
    try {
      const result = await adminApi.getGameYaml(name);
      setYamlContent(result.content);
      setOriginalContent(result.content);
    } catch (err) {
      toastRef.current.error('Load Failed', err instanceof Error ? err.message : 'Failed to load game config');
      setYamlContent('');
      setOriginalContent('');
    } finally {
      setLoadingYaml(false);
    }
  }, []); // No dependencies - uses ref for toast

  useEffect(() => {
    if (selectedGame) {
      loadGameYaml(selectedGame);
    }
  }, [selectedGame]); // Only re-run when selectedGame changes

  // Track unsaved changes
  const hasUnsavedChanges = yamlContent !== originalContent;

  useEffect(() => {
    if (hasUnsavedChanges) {
      onUnsavedChange();
    }
  }, [hasUnsavedChanges, onUnsavedChange]);

  // Validate YAML
  const handleValidate = async () => {
    setValidating(true);
    try {
      const result = await adminApi.validateYaml(yamlContent);
      setValidation(result);
      if (result.valid) {
        if (result.warnings && result.warnings.length > 0) {
          toastRef.current.warning('Valid with Warnings', result.warnings.join(', '));
        } else {
          toastRef.current.success('Valid', 'YAML syntax is correct');
        }
      } else {
        toastRef.current.error('Invalid YAML', result.error || 'Syntax error');
      }
    } catch (err) {
      toastRef.current.error('Validation Failed', err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setValidating(false);
    }
  };

  // Save YAML
  const handleSave = async () => {
    if (!selectedGame) return;

    setSaving(true);
    try {
      // Validate first
      const validationResult = await adminApi.validateYaml(yamlContent);
      if (!validationResult.valid) {
        toastRef.current.error('Invalid YAML', validationResult.error || 'Fix syntax errors before saving');
        setValidation(validationResult);
        return;
      }

      await adminApi.updateGameYaml(selectedGame, yamlContent);
      setOriginalContent(yamlContent);
      // Reload games list to pick up any metadata changes (steam_app_id, etc.)
      await loadGames();
      toastRef.current.success('Saved', `${selectedGame} configuration saved`);
      onSaved();
    } catch (err) {
      toastRef.current.error('Save Failed', err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setSaving(false);
    }
  };

  // Create new game
  const handleCreateGame = async () => {
    if (!newGameName.trim()) {
      toastRef.current.error('Invalid Name', 'Game name cannot be empty');
      return;
    }

    try {
      const result = await adminApi.createGame({ name: newGameName });
      if (result.name) {
        await loadGames();
        setSelectedGame(result.name);
        setShowNewGameForm(false);
        setNewGameName('');
        toastRef.current.success('Created', `${result.name} created`);
      }
    } catch (err) {
      toastRef.current.error('Create Failed', err instanceof Error ? err.message : 'Unknown error');
    }
  };

  // Delete game
  const handleDeleteGame = async () => {
    if (!selectedGame) return;

    if (!confirm(`Are you sure you want to delete "${selectedGame}"? This action cannot be undone.`)) {
      return;
    }

    try {
      await adminApi.deleteGame(selectedGame);
      await loadGames();
      setSelectedGame(null);
      setYamlContent('');
      setOriginalContent('');
      toastRef.current.success('Deleted', `${selectedGame} deleted`);
    } catch (err) {
      toastRef.current.error('Delete Failed', err instanceof Error ? err.message : 'Unknown error');
    }
  };

  // Handle image upload
  const handleImageUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file || !selectedGame) return;

    // Validate file type
    if (!file.type.startsWith('image/')) {
      toastRef.current.error('Invalid File', 'Please select an image file');
      return;
    }

    // Validate file size (max 5MB)
    if (file.size > 5 * 1024 * 1024) {
      toastRef.current.error('File Too Large', 'Max file size is 5MB');
      return;
    }

    setUploadingImage(true);
    try {
      const formData = new FormData();
      formData.append('image', file);

      const response = await fetch(`/api/admin/games/${encodeURIComponent(selectedGame)}/image`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        throw new Error('Upload failed');
      }

      toastRef.current.success('Uploaded', 'Game image uploaded successfully');
      // Force refresh the image by reloading games
      await loadGames();
    } catch (err) {
      toastRef.current.error('Upload Failed', err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setUploadingImage(false);
      // Reset file input
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  // Use Steam image
  const handleUseSteamImage = async () => {
    if (!selectedGame || !steamAppId) {
      toastRef.current.error('No Steam ID', 'This game does not have a Steam App ID configured');
      return;
    }

    setUploadingImage(true);
    try {
      const response = await fetch(`/api/admin/games/${encodeURIComponent(selectedGame)}/image/steam`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ steam_app_id: steamAppId }),
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.error || 'Failed to fetch Steam image');
      }

      toastRef.current.success('Downloaded', 'Steam image downloaded successfully');
      await loadGames();
    } catch (err) {
      toastRef.current.error('Steam Image Failed', err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setUploadingImage(false);
    }
  };

  // Get game image URL
  const getGameImageUrl = () => {
    if (!selectedGame) return null;
    // Check for custom image first, then fall back to Steam CDN
    const customImagePath = `/game-images/${selectedGame}.jpg`;
    // We'll try the custom path first, and if it fails, use Steam CDN
    return customImagePath;
  };

  const getSteamImageUrl = () => {
    if (!steamAppId) return null;
    return `${STEAM_CDN_URL}/${steamAppId}/header.jpg`;
  };

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 's' && selectedGame && hasUnsavedChanges) {
        e.preventDefault();
        handleSave();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [selectedGame, hasUnsavedChanges, yamlContent]);

  return (
    <div className="flex h-full">
      {/* Game List Sidebar */}
      <div className="w-64 border-r border-border bg-surface flex flex-col">
        <div className="p-3 border-b border-border flex items-center justify-between">
          <h3 className="text-sm font-medium text-text-primary">Games</h3>
          <div className="flex items-center gap-1">
            <button
              onClick={loadGames}
              disabled={loading}
              className="p-1.5 text-text-muted hover:text-text-primary hover:bg-surface-elevated rounded transition-colors"
              title="Refresh"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            </button>
            <button
              onClick={() => setShowNewGameForm(true)}
              className="p-1.5 text-text-muted hover:text-primary hover:bg-primary/10 rounded transition-colors"
              title="New game"
            >
              <Plus className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* New Game Form */}
        {showNewGameForm && (
          <div className="p-3 border-b border-border bg-surface-elevated">
            <input
              type="text"
              value={newGameName}
              onChange={e => setNewGameName(e.target.value)}
              placeholder="game-name-slug"
              className="w-full px-2 py-1.5 text-sm bg-surface border border-border rounded focus:outline-none focus:border-primary mb-2"
              onKeyDown={e => e.key === 'Enter' && handleCreateGame()}
              autoFocus
            />
            <div className="flex gap-2">
              <button
                onClick={handleCreateGame}
                className="flex-1 px-2 py-1 text-xs bg-primary text-white rounded hover:bg-primary-hover"
              >
                Create
              </button>
              <button
                onClick={() => { setShowNewGameForm(false); setNewGameName(''); }}
                className="flex-1 px-2 py-1 text-xs bg-surface-elevated text-text-secondary rounded hover:bg-surface-hover"
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        {/* Game List */}
        <div className="flex-1 overflow-y-auto">
          {loading ? (
            <div className="p-4 text-center text-text-muted text-sm">Loading...</div>
          ) : games.length === 0 ? (
            <div className="p-4 text-center text-text-muted text-sm">No games found</div>
          ) : (
            games.map(game => (
              <button
                key={game.name}
                onClick={() => setSelectedGame(game.name)}
                className={`
                  w-full text-left px-3 py-2 border-b border-border/50 transition-colors
                  ${selectedGame === game.name
                    ? 'bg-primary/10 text-primary'
                    : 'text-text-secondary hover:bg-surface-elevated'
                  }
                `}
              >
                <div className="flex items-center gap-2">
                  <FileText className="w-4 h-4 flex-shrink-0" />
                  <div className="min-w-0">
                    <p className="text-sm font-medium truncate">{game.game_name || game.name}</p>
                    <p className="text-xs text-text-muted truncate">{game.filename}</p>
                  </div>
                </div>
              </button>
            ))
          )}
        </div>
      </div>

      {/* Editor Panel */}
      <div className="flex-1 flex flex-col">
        {selectedGame ? (
          <>
            {/* Editor Header */}
            <div className="p-3 border-b border-border flex items-center justify-between bg-surface">
              <div className="flex items-center gap-3">
                <h3 className="text-sm font-medium text-text-primary">{selectedGame}.yaml</h3>
                {hasUnsavedChanges && (
                  <span className="px-2 py-0.5 text-xs bg-warning/20 text-warning rounded">
                    Unsaved
                  </span>
                )}
                {validation && (
                  <span className={`flex items-center gap-1 px-2 py-0.5 text-xs rounded ${
                    validation.valid ? 'bg-success/20 text-success' : 'bg-danger/20 text-danger'
                  }`}>
                    {validation.valid ? <CheckCircle className="w-3 h-3" /> : <AlertTriangle className="w-3 h-3" />}
                    {validation.valid ? 'Valid' : `Error line ${validation.line || '?'}`}
                  </span>
                )}
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setShowImagePanel(!showImagePanel)}
                  className={`flex items-center gap-1.5 px-2.5 py-1.5 text-xs border rounded transition-colors ${
                    showImagePanel
                      ? 'bg-primary/20 text-primary border-primary'
                      : 'bg-surface-elevated hover:bg-surface-hover border-border'
                  }`}
                  title="Manage game image"
                >
                  <Image className="w-3 h-3" />
                  Image
                </button>
                <button
                  onClick={handleValidate}
                  disabled={validating}
                  className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs bg-surface-elevated hover:bg-surface-hover border border-border rounded transition-colors"
                >
                  {validating ? <Loader2 className="w-3 h-3 animate-spin" /> : <CheckCircle className="w-3 h-3" />}
                  Validate
                </button>
                <button
                  onClick={handleSave}
                  disabled={saving || !hasUnsavedChanges}
                  className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs bg-primary text-white rounded hover:bg-primary-hover disabled:opacity-50 transition-colors"
                >
                  {saving ? <Loader2 className="w-3 h-3 animate-spin" /> : <Save className="w-3 h-3" />}
                  Save
                </button>
                <button
                  onClick={handleDeleteGame}
                  className="p-1.5 text-text-muted hover:text-danger hover:bg-danger/10 rounded transition-colors"
                  title="Delete game"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>

            {/* Image Panel */}
            {showImagePanel && (
              <div className="p-4 border-b border-border bg-surface-elevated">
                <div className="flex items-start gap-4">
                  {/* Image Preview */}
                  <div className="flex-shrink-0">
                    <div className="w-48 h-24 bg-surface rounded-lg overflow-hidden border border-border">
                      <img
                        src={getGameImageUrl() || ''}
                        alt={selectedGame || 'Game'}
                        className="w-full h-full object-cover"
                        onError={(e) => {
                          // Fall back to Steam image if custom image not found
                          const steamUrl = getSteamImageUrl();
                          if (steamUrl && e.currentTarget.src !== steamUrl) {
                            e.currentTarget.src = steamUrl;
                          } else {
                            e.currentTarget.style.display = 'none';
                          }
                        }}
                      />
                    </div>
                  </div>

                  {/* Image Actions */}
                  <div className="flex-1">
                    <h4 className="text-sm font-medium text-text-primary mb-2">Game Image</h4>
                    <p className="text-xs text-text-muted mb-3">
                      Upload a custom image or use Steam's header image.
                      {steamAppId && (
                        <span className="ml-1 text-text-secondary">
                          Steam ID: <code className="bg-surface px-1 rounded">{steamAppId}</code>
                        </span>
                      )}
                    </p>

                    <div className="flex items-center gap-2">
                      {/* Hidden file input */}
                      <input
                        ref={fileInputRef}
                        type="file"
                        accept="image/*"
                        onChange={handleImageUpload}
                        className="hidden"
                      />

                      {/* Upload button */}
                      <button
                        onClick={() => fileInputRef.current?.click()}
                        disabled={uploadingImage}
                        className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-surface hover:bg-surface-hover border border-border rounded transition-colors"
                      >
                        {uploadingImage ? (
                          <Loader2 className="w-3 h-3 animate-spin" />
                        ) : (
                          <Upload className="w-3 h-3" />
                        )}
                        Upload Image
                      </button>

                      {/* Use Steam Image button */}
                      <button
                        onClick={handleUseSteamImage}
                        disabled={uploadingImage || !steamAppId}
                        className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-[#1b2838] text-white hover:bg-[#2a475e] rounded transition-colors disabled:opacity-50"
                        title={steamAppId ? `Fetch from Steam (App ID: ${steamAppId})` : 'No Steam App ID configured'}
                      >
                        {uploadingImage ? (
                          <Loader2 className="w-3 h-3 animate-spin" />
                        ) : (
                          <ExternalLink className="w-3 h-3" />
                        )}
                        Use Steam Image
                      </button>
                    </div>

                    <p className="text-[10px] text-text-muted mt-2">
                      Recommended: 460×215 or 920×430 pixels (Steam header format)
                    </p>
                  </div>
                </div>
              </div>
            )}

            {/* Editor Content */}
            {loadingYaml ? (
              <div className="flex-1 flex items-center justify-center text-text-muted">
                <Loader2 className="w-6 h-6 animate-spin" />
              </div>
            ) : (
              <div className="flex-1 relative">
                <textarea
                  value={yamlContent}
                  onChange={e => setYamlContent(e.target.value)}
                  className="absolute inset-0 w-full h-full p-4 font-mono text-sm bg-surface-elevated text-text-primary resize-none focus:outline-none"
                  spellCheck={false}
                  placeholder="# YAML content..."
                />
                {/* TODO: Replace with Monaco Editor for syntax highlighting */}
                {/* npm install @monaco-editor/react */}
              </div>
            )}

            {/* Validation Warnings */}
            {validation?.warnings && validation.warnings.length > 0 && (
              <div className="p-3 border-t border-border bg-warning/5">
                <p className="text-xs font-medium text-warning mb-1">Warnings:</p>
                <ul className="text-xs text-text-muted list-disc list-inside">
                  {validation.warnings.map((w, i) => (
                    <li key={i}>{w}</li>
                  ))}
                </ul>
              </div>
            )}
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center text-text-muted">
            <div className="text-center">
              <FileText className="w-12 h-12 mx-auto mb-3 opacity-30" />
              <p className="text-sm">Select a game to edit its configuration</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default GameConfigEditor;
