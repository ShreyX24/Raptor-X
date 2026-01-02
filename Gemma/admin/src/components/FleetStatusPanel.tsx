/**
 * FleetStatusPanel - SUT fleet overview
 */

import { useState } from 'react';
import { RefreshCw } from 'lucide-react';
import { StatusDot } from './DataTable';
import type { SUT } from '../types';

interface FleetStatusPanelProps {
  devices: SUT[];
  onlineDevices: SUT[];
  selectedSutId?: string;
  onSelectSut: (sut: SUT) => void;
  className?: string;
  compact?: boolean;
}

export function FleetStatusPanel({
  devices,
  onlineDevices,
  selectedSutId,
  onSelectSut,
  className = '',
  compact = false,
}: FleetStatusPanelProps) {
  const [scanning, setScanning] = useState(false);

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
                  w-full flex items-center justify-between px-2 py-1.5 rounded text-xs
                  ${selectedSutId === sut.device_id
                    ? 'bg-primary/20 border border-primary'
                    : 'bg-surface-elevated hover:bg-surface-hover border border-transparent'
                  }
                `}
              >
                <div className="flex items-center gap-1.5">
                  <StatusDot status="online" />
                  <span className="truncate">{sut.hostname || sut.ip}</span>
                </div>
                {sut.current_task && (
                  <span className="text-[10px] text-warning">BUSY</span>
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
}

export function CompactSutCard({ sut, isSelected, onClick }: CompactSutCardProps) {
  return (
    <button
      onClick={onClick}
      className={`
        w-full flex items-center justify-between px-3 py-2 rounded-md
        transition-all text-left
        ${isSelected
          ? 'bg-primary/20 border border-primary'
          : 'bg-surface-elevated hover:bg-surface-hover border border-transparent'
        }
      `}
    >
      <div className="flex items-center gap-2 min-w-0">
        <StatusDot status={sut.status === 'online' ? 'online' : 'offline'} />
        <span className="text-sm font-medium text-text-primary truncate">
          {sut.hostname || sut.ip}
        </span>
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
