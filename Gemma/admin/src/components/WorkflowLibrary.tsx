/**
 * WorkflowLibrary - Collapsible sidebar for browsing and managing game workflows
 */

import { useState, useEffect, useMemo, useCallback } from 'react';
import {
  listWorkflows,
  deleteWorkflow,
  getWorkflowYaml,
  createWorkflow,
  generateWorkflowTemplate,
  type WorkflowSummary,
} from '../api/workflowBuilder';

interface WorkflowLibraryProps {
  /** Currently loaded workflow name */
  currentWorkflow: string | null;
  /** Called when user selects a workflow to load */
  onLoadWorkflow: (name: string, yaml: string) => void;
  /** Called when user creates a new workflow */
  onNewWorkflow: (name: string, yaml: string) => void;
  /** Whether the sidebar is collapsed */
  collapsed?: boolean;
  /** Callback to toggle collapsed state */
  onToggleCollapse?: () => void;
  /** Whether there are unsaved changes */
  hasUnsavedChanges?: boolean;
}

export function WorkflowLibrary({
  currentWorkflow,
  onLoadWorkflow,
  onNewWorkflow,
  collapsed = false,
  onToggleCollapse,
  hasUnsavedChanges = false,
}: WorkflowLibraryProps) {
  const [workflows, setWorkflows] = useState<WorkflowSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [showNewDialog, setShowNewDialog] = useState(false);
  const [newWorkflowName, setNewWorkflowName] = useState('');
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  // Fetch workflows on mount
  const fetchWorkflows = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await listWorkflows();
      setWorkflows(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load workflows');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchWorkflows();
  }, [fetchWorkflows]);

  // Filter workflows by search
  const filteredWorkflows = useMemo(() => {
    if (!searchQuery.trim()) return workflows;
    const query = searchQuery.toLowerCase();
    return workflows.filter(
      (w) =>
        w.name.toLowerCase().includes(query) ||
        w.filename.toLowerCase().includes(query)
    );
  }, [workflows, searchQuery]);

  // Handle loading a workflow
  const handleLoadWorkflow = async (name: string) => {
    if (hasUnsavedChanges) {
      const confirmLoad = window.confirm(
        'You have unsaved changes. Load a different workflow anyway?'
      );
      if (!confirmLoad) return;
    }

    try {
      setActionLoading(name);
      const yaml = await getWorkflowYaml(name);
      onLoadWorkflow(name, yaml);
    } catch (err) {
      alert(`Failed to load workflow: ${err instanceof Error ? err.message : 'Unknown error'}`);
    } finally {
      setActionLoading(null);
    }
  };

  // Handle creating new workflow
  const handleCreateWorkflow = async () => {
    if (!newWorkflowName.trim()) {
      alert('Please enter a workflow name');
      return;
    }

    if (hasUnsavedChanges) {
      const confirmNew = window.confirm(
        'You have unsaved changes. Create a new workflow anyway?'
      );
      if (!confirmNew) return;
    }

    try {
      setActionLoading('new');
      const yaml = generateWorkflowTemplate(newWorkflowName.trim());
      await createWorkflow(newWorkflowName.trim(), yaml);
      setShowNewDialog(false);
      setNewWorkflowName('');
      await fetchWorkflows();
      onNewWorkflow(newWorkflowName.trim(), yaml);
    } catch (err) {
      alert(`Failed to create workflow: ${err instanceof Error ? err.message : 'Unknown error'}`);
    } finally {
      setActionLoading(null);
    }
  };

  // Handle duplicating a workflow
  const handleDuplicateWorkflow = async (name: string) => {
    try {
      setActionLoading(`dup-${name}`);
      const yaml = await getWorkflowYaml(name);
      const newName = `${name} (Copy)`;
      await createWorkflow(newName, yaml);
      await fetchWorkflows();
    } catch (err) {
      alert(`Failed to duplicate workflow: ${err instanceof Error ? err.message : 'Unknown error'}`);
    } finally {
      setActionLoading(null);
    }
  };

  // Handle deleting a workflow
  const handleDeleteWorkflow = async (name: string) => {
    const confirmDelete = window.confirm(
      `Are you sure you want to delete "${name}"? This cannot be undone.`
    );
    if (!confirmDelete) return;

    try {
      setActionLoading(`del-${name}`);
      await deleteWorkflow(name);
      await fetchWorkflows();
    } catch (err) {
      alert(`Failed to delete workflow: ${err instanceof Error ? err.message : 'Unknown error'}`);
    } finally {
      setActionLoading(null);
    }
  };

  // Format date for display
  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return '-';
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  // Get short name for collapsed view (e.g., "HITMAN 3" -> "HIT", "Far Cry 6" -> "FC6")
  const getShortName = (name: string): string => {
    // Common abbreviations
    const abbrevMap: Record<string, string> = {
      "HITMAN 3": "H3",
      "Far Cry 6": "FC6",
      "Cyberpunk 2077": "CP77",
      "Red Dead Redemption 2": "RDR2",
      "Shadow of the Tomb Raider": "SOTR",
      "Assassin's Creed Mirage": "ACM",
      "Black Myth: Wukong": "BMW",
      "Counter-Strike 2": "CS2",
      "Dota 2": "D2",
      "F1 24": "F1",
      "Horizon Zero Dawn Remastered": "HZD",
      "Final Fantasy XIV: Dawntrail": "FF14",
      "Sid Meier's Civilization VI": "CIV6",
      "Tiny Tina Wonderlands": "TTW",
    };
    if (abbrevMap[name]) return abbrevMap[name];
    // Fallback: first 3 chars
    return name.slice(0, 3).toUpperCase();
  };

  // Collapsed state - show compact game list
  if (collapsed) {
    return (
      <div className="w-12 flex flex-col bg-surface border-r border-border h-full">
        {/* Toggle button */}
        <button
          onClick={onToggleCollapse}
          className="p-2 text-text-muted hover:text-text-primary hover:bg-surface-elevated transition-colors border-b border-border"
          title="Expand Library"
        >
          <svg className="w-5 h-5 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
        </button>

        {/* Compact game list */}
        <div className="flex-1 overflow-y-auto py-1">
          {loading ? (
            <div className="flex justify-center py-4">
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-primary"></div>
            </div>
          ) : (
            workflows.map((workflow) => (
              <button
                key={workflow.name}
                onClick={() => handleLoadWorkflow(workflow.name)}
                className={`w-full py-2 px-1 text-center transition-colors ${
                  currentWorkflow === workflow.name
                    ? 'bg-primary/20 text-primary border-l-2 border-primary'
                    : 'text-text-muted hover:text-text-primary hover:bg-surface-elevated'
                }`}
                title={workflow.name}
              >
                <span className="text-[10px] font-bold leading-none">
                  {getShortName(workflow.name)}
                </span>
              </button>
            ))
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="w-64 flex flex-col bg-surface border-r border-border h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-border bg-surface-elevated/50">
        <div className="flex items-center gap-2">
          <svg className="w-4 h-4 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
          </svg>
          <span className="text-xs font-semibold text-text-secondary uppercase tracking-wide">
            Workflows
          </span>
          <span className="px-1.5 py-0.5 text-xs font-medium rounded bg-primary/20 text-primary">
            {workflows.length}
          </span>
        </div>
        <button
          onClick={onToggleCollapse}
          className="p-1 text-text-muted hover:text-text-primary hover:bg-surface-elevated rounded transition-colors"
          title="Collapse"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
        </button>
      </div>

      {/* Search & New Button */}
      <div className="p-2 border-b border-border space-y-2">
        <div className="relative">
          <input
            type="text"
            placeholder="Search workflows..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-8 pr-3 py-1.5 text-sm bg-surface-elevated border border-border rounded focus:outline-none focus:ring-1 focus:ring-primary"
          />
          <svg
            className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-text-muted"
            fill="none" stroke="currentColor" viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
        </div>
        <button
          onClick={() => setShowNewDialog(true)}
          className="w-full flex items-center justify-center gap-2 px-3 py-1.5 text-sm font-medium bg-primary hover:bg-primary-hover text-white rounded transition-colors"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          New Workflow
        </button>
      </div>

      {/* Workflow List */}
      <div className="flex-1 overflow-y-auto">
        {loading ? (
          <div className="flex items-center justify-center py-8">
            <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary"></div>
          </div>
        ) : error ? (
          <div className="p-4 text-center">
            <p className="text-sm text-danger mb-2">{error}</p>
            <button
              onClick={fetchWorkflows}
              className="text-xs text-primary hover:underline"
            >
              Retry
            </button>
          </div>
        ) : filteredWorkflows.length === 0 ? (
          <div className="p-4 text-center text-sm text-text-muted">
            {searchQuery ? 'No matching workflows' : 'No workflows found'}
          </div>
        ) : (
          <div className="divide-y divide-border">
            {filteredWorkflows.map((workflow) => (
              <div
                key={workflow.name}
                className={`group relative ${
                  currentWorkflow === workflow.name
                    ? 'bg-primary/10 border-l-2 border-l-primary'
                    : 'hover:bg-surface-elevated'
                }`}
              >
                {/* Main clickable area */}
                <button
                  onClick={() => handleLoadWorkflow(workflow.name)}
                  disabled={actionLoading !== null}
                  className="w-full text-left p-2 pr-8"
                >
                  <div className="flex items-start justify-between">
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-1.5">
                        <span className={`text-sm font-medium truncate ${
                          currentWorkflow === workflow.name ? 'text-primary' : 'text-text-primary'
                        }`}>
                          {workflow.name}
                        </span>
                        {currentWorkflow === workflow.name && hasUnsavedChanges && (
                          <span className="w-2 h-2 rounded-full bg-warning" title="Unsaved changes" />
                        )}
                      </div>
                      <div className="flex items-center gap-2 mt-0.5">
                        <span className="text-xs text-text-muted">
                          {workflow.step_count} steps
                        </span>
                        <span className="text-xs text-text-muted">
                          {formatDate(workflow.last_modified)}
                        </span>
                      </div>
                    </div>
                  </div>
                </button>

                {/* Action buttons (visible on hover) */}
                <div className="absolute right-1 top-1/2 -translate-y-1/2 flex gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
                  {/* Duplicate */}
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDuplicateWorkflow(workflow.name);
                    }}
                    disabled={actionLoading !== null}
                    className="p-1 text-text-muted hover:text-text-primary hover:bg-surface-elevated rounded"
                    title="Duplicate"
                  >
                    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                        d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                    </svg>
                  </button>
                  {/* Delete */}
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDeleteWorkflow(workflow.name);
                    }}
                    disabled={actionLoading !== null}
                    className="p-1 text-text-muted hover:text-danger hover:bg-danger/10 rounded"
                    title="Delete"
                  >
                    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                        d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                    </svg>
                  </button>
                </div>

                {/* Loading overlay */}
                {(actionLoading === workflow.name ||
                  actionLoading === `dup-${workflow.name}` ||
                  actionLoading === `del-${workflow.name}`) && (
                  <div className="absolute inset-0 bg-surface/80 flex items-center justify-center">
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-primary"></div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* New Workflow Dialog */}
      {showNewDialog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-surface border border-border rounded-lg shadow-xl w-80 p-4">
            <h3 className="text-sm font-semibold text-text-primary mb-3">New Workflow</h3>
            <input
              type="text"
              placeholder="Workflow name (e.g., My Game)"
              value={newWorkflowName}
              onChange={(e) => setNewWorkflowName(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleCreateWorkflow()}
              autoFocus
              className="w-full px-3 py-2 text-sm bg-surface-elevated border border-border rounded focus:outline-none focus:ring-1 focus:ring-primary mb-3"
            />
            <div className="flex justify-end gap-2">
              <button
                onClick={() => {
                  setShowNewDialog(false);
                  setNewWorkflowName('');
                }}
                className="px-3 py-1.5 text-sm text-text-muted hover:text-text-primary hover:bg-surface-elevated rounded transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleCreateWorkflow}
                disabled={!newWorkflowName.trim() || actionLoading === 'new'}
                className="px-3 py-1.5 text-sm font-medium bg-primary hover:bg-primary-hover disabled:opacity-50 text-white rounded transition-colors"
              >
                {actionLoading === 'new' ? 'Creating...' : 'Create'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
