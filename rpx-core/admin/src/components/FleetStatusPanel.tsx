/**
 * FleetStatusPanel - SUT fleet overview
 */

import { useState } from 'react';
import { RefreshCw, Key, Pencil, Check, X } from 'lucide-react';
import { StatusDot } from './DataTable';
import { setSutDisplayName } from '../api';
import type { SUT } from '../types';

/** Get display label for a SUT (display_name > hostname > ip) */
function getSutLabel(sut: SUT): string {
  return sut.display_name || sut.hostname || sut.ip;
}

/** Whether to show IP separately (not redundant with the label) */
function shouldShowIp(sut: SUT): boolean {
  const label = getSutLabel(sut);
  return label !== sut.ip;
}

interface FleetStatusPanelProps {
  devices: SUT[];
  onlineDevices: SUT[];
  selectedSutId?: string;
  onSelectSut: (sut: SUT) => void;
  onDevicesRefresh?: () => void;
  className?: string;
  compact?: boolean;
}

export function FleetStatusPanel({
  devices,
  onlineDevices,
  selectedSutId,
  onSelectSut,
  onDevicesRefresh,
  className = '',
  compact = false,
}: FleetStatusPanelProps) {
  const [scanning, setScanning] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState('');

  const handleScan = async () => {
    setScanning(true);
    try {
      await fetch('/api/discovery/scan', { method: 'POST' });
    } catch (error) {
      console.error('Scan failed:', error);
    } finally {
      setTimeout(() => setScanning(false), 2000);
    }
  };

  const handleStartEdit = (sut: SUT, e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingId(sut.device_id);
    setEditValue(sut.display_name || '');
  };

  const handleSaveEdit = async (sut: SUT, e?: React.MouseEvent) => {
    e?.stopPropagation();
    try {
      await setSutDisplayName(sut.device_id, editValue.trim());
      onDevicesRefresh?.();
    } catch (error) {
      console.error('Failed to set display name:', error);
    }
    setEditingId(null);
    setEditValue('');
  };

  const handleCancelEdit = (e?: React.MouseEvent) => {
    e?.stopPropagation();
    setEditingId(null);
    setEditValue('');
  };

  // Compact mode - just a dropdown-style selector
  if (compact) {
    return (
      <div className={`bg-surface border border-border rounded-lg p-3 h-full flex flex-col ${className}`}>
        {/* Header row */}
        <div className="flex items-center justify-between mb-2 flex-shrink-0">
          <span className="text-xs font-semibold text-text-secondary uppercase">Fleet</span>
          <div className="flex items-center gap-1.5">
            <button
              onClick={handleScan}
              disabled={scanning}
              className="p-1 text-text-muted hover:text-text-primary rounded transition-colors disabled:opacity-50"
              title="Scan"
            >
              <RefreshCw className={`w-3 h-3 ${scanning ? 'animate-spin' : ''}`} />
            </button>
            <span className="text-xs text-text-muted font-numbers">
              {onlineDevices.length}/{devices.length}
            </span>
          </div>
        </div>

        {/* Compact SUT list - fills remaining space */}
        <div className="space-y-1 flex-1 overflow-y-auto">
          {onlineDevices.length === 0 ? (
            <div className="text-center py-2 text-text-muted text-xs">No devices online</div>
          ) : (
            onlineDevices.map((sut) => (
              <button
                key={sut.device_id}
                onClick={() => onSelectSut(sut)}
                className={`
                  w-full flex items-center justify-between px-2 py-1.5 rounded text-xs text-left
                  ${selectedSutId === sut.device_id
                    ? 'bg-primary/20 border border-primary'
                    : 'bg-surface-elevated hover:bg-surface-hover border border-transparent'
                  }
                `}
              >
                <div className="flex items-center gap-1.5 min-w-0">
                  <StatusDot status="online" />
                  {editingId === sut.device_id ? (
                    <div className="flex items-center gap-1" onClick={e => e.stopPropagation()}>
                      <input
                        type="text"
                        value={editValue}
                        onChange={(e) => setEditValue(e.target.value)}
                        onKeyDown={(e) => { if (e.key === 'Enter') handleSaveEdit(sut); if (e.key === 'Escape') handleCancelEdit(); }}
                        className="px-1 py-0.5 text-[10px] bg-surface border border-primary rounded w-20 focus:outline-none"
                        autoFocus
                      />
                      <button onClick={(e) => handleSaveEdit(sut, e)} className="p-0.5 text-success hover:text-success/80">
                        <Check className="w-2.5 h-2.5" />
                      </button>
                      <button onClick={(e) => handleCancelEdit(e)} className="p-0.5 text-danger hover:text-danger/80">
                        <X className="w-2.5 h-2.5" />
                      </button>
                    </div>
                  ) : (
                    <div className="flex flex-col leading-tight min-w-0">
                      <div className="flex items-center gap-1">
                        <span className="truncate">{getSutLabel(sut)}</span>
                        <button
                          onClick={(e) => handleStartEdit(sut, e)}
                          className="p-0.5 text-text-muted hover:text-primary opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0"
                          title="Edit display name"
                        >
                          <Pencil className="w-2 h-2" />
                        </button>
                        {sut.master_key_installed && (
                          <span title="SSH Ready"><Key className="w-2.5 h-2.5 text-success flex-shrink-0" /></span>
                        )}
                      </div>
                      {shouldShowIp(sut) && (
                        <span className="text-[10px] text-text-muted font-mono">{sut.ip}</span>
                      )}
                    </div>
                  )}
                </div>
                {sut.current_task && (
                  <span className="text-[10px] text-warning flex-shrink-0">BUSY</span>
                )}
              </button>
            ))
          )}
        </div>

        {/* Offline count */}
        {devices.length > onlineDevices.length && (
          <div className="mt-2 pt-2 border-t border-border/50 text-[10px] text-text-muted text-center flex-shrink-0">
            +{devices.length - onlineDevices.length} offline
          </div>
        )}
      </div>
    );
  }

  return (
    <div className={`bg-surface border border-border rounded-lg p-3 ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-text-secondary uppercase tracking-wide">
          Fleet Status
        </h3>
        <div className="flex items-center gap-2">
          <button
            onClick={handleScan}
            disabled={scanning}
            className="flex items-center gap-1.5 px-2 py-1 text-xs font-medium bg-surface-elevated hover:bg-surface-hover text-text-secondary border border-border rounded transition-colors disabled:opacity-50"
            title="Scan for SUTs"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${scanning ? 'animate-spin' : ''}`} />
            <span>Scan</span>
          </button>
          <span className="text-sm text-text-muted font-numbers">
            {onlineDevices.length}/{devices.length}
          </span>
        </div>
      </div>

      {/* Stats Row */}
      <div className="flex items-center gap-4 mb-3 px-2 py-2 bg-surface-elevated/50 rounded">
        <div className="flex items-center gap-2">
          <span className="text-sm text-text-muted">Online:</span>
          <span className="text-sm font-bold font-numbers text-success">{onlineDevices.length}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-sm text-text-muted">Offline:</span>
          <span className="text-sm font-bold font-numbers text-danger">{devices.length - onlineDevices.length}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-sm text-text-muted">Paired:</span>
          <span className="text-sm font-bold font-numbers text-primary">{devices.filter(d => d.is_paired).length}</span>
        </div>
      </div>

      {/* SUT List */}
      <div className="space-y-1.5 max-h-[200px] overflow-y-auto">
        {onlineDevices.length === 0 ? (
          <div className="text-center py-3 text-text-muted text-sm">
            No devices online
          </div>
        ) : (
          onlineDevices.map((sut) => (
            <CompactSutCard
              key={sut.device_id}
              sut={sut}
              isSelected={selectedSutId === sut.device_id}
              onClick={() => onSelectSut(sut)}
              isEditing={editingId === sut.device_id}
              editValue={editValue}
              onEditValueChange={setEditValue}
              onStartEdit={(e) => handleStartEdit(sut, e)}
              onSaveEdit={(e) => handleSaveEdit(sut, e)}
              onCancelEdit={handleCancelEdit}
            />
          ))
        )}
      </div>

      {/* Show offline count if any */}
      {devices.length > onlineDevices.length && (
        <div className="mt-2 pt-2 border-t border-border text-sm text-text-muted text-center">
          +{devices.length - onlineDevices.length} offline
        </div>
      )}
    </div>
  );
}

/**
 * CompactSutCard - Minimal SUT card for fleet panel
 */
interface CompactSutCardProps {
  sut: SUT;
  isSelected: boolean;
  onClick: () => void;
  isEditing?: boolean;
  editValue?: string;
  onEditValueChange?: (value: string) => void;
  onStartEdit?: (e: React.MouseEvent) => void;
  onSaveEdit?: (e?: React.MouseEvent) => void;
  onCancelEdit?: (e?: React.MouseEvent) => void;
}

export function CompactSutCard({
  sut,
  isSelected,
  onClick,
  isEditing = false,
  editValue = '',
  onEditValueChange,
  onStartEdit,
  onSaveEdit,
  onCancelEdit,
}: CompactSutCardProps) {
  return (
    <button
      onClick={onClick}
      className={`
        w-full flex items-center justify-between px-3 py-2 rounded-md
        transition-all text-left group
        ${isSelected
          ? 'bg-primary/20 border border-primary'
          : 'bg-surface-elevated hover:bg-surface-hover border border-transparent'
        }
      `}
    >
      <div className="flex items-center gap-2 min-w-0">
        <StatusDot status={sut.status === 'online' ? 'online' : 'offline'} />
        {isEditing ? (
          <div className="flex items-center gap-1" onClick={e => e.stopPropagation()}>
            <input
              type="text"
              value={editValue}
              onChange={(e) => onEditValueChange?.(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') onSaveEdit?.(); if (e.key === 'Escape') onCancelEdit?.(); }}
              placeholder={sut.hostname || sut.ip}
              className="px-1.5 py-0.5 text-xs bg-surface border border-primary rounded w-28 focus:outline-none"
              autoFocus
            />
            <button onClick={(e) => onSaveEdit?.(e)} className="p-0.5 text-success hover:text-success/80">
              <Check className="w-3 h-3" />
            </button>
            <button onClick={(e) => onCancelEdit?.(e)} className="p-0.5 text-danger hover:text-danger/80">
              <X className="w-3 h-3" />
            </button>
          </div>
        ) : (
          <div className="flex flex-col leading-tight min-w-0">
            <div className="flex items-center gap-1.5">
              <span className="text-sm font-medium text-text-primary truncate">
                {getSutLabel(sut)}
              </span>
              {onStartEdit && (
                <button
                  onClick={(e) => onStartEdit(e)}
                  className="p-0.5 text-text-muted hover:text-primary opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0"
                  title="Edit display name"
                >
                  <Pencil className="w-2.5 h-2.5" />
                </button>
              )}
              {sut.master_key_installed && (
                <span title="SSH Ready"><Key className="w-3 h-3 text-success flex-shrink-0" /></span>
              )}
            </div>
            {shouldShowIp(sut) && (
              <span className="text-[10px] text-text-muted font-mono">{sut.ip}</span>
            )}
          </div>
        )}
      </div>

      <div className="flex items-center gap-2 flex-shrink-0">
        {sut.current_task && (
          <span className="text-xs text-warning animate-pulse font-medium">BUSY</span>
        )}
        {sut.success_rate !== undefined && sut.success_rate > 0 && (
          <span className="text-xs text-text-muted font-numbers">
            {Math.round(sut.success_rate * 100)}%
          </span>
        )}
      </div>
    </button>
  );
}
