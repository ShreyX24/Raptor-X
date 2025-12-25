import { StatusBadge } from './StatusBadge';
import type { SystemStatus } from '../types';

interface ServiceStatusProps {
  systemStatus: SystemStatus | null;
}

export function ServiceStatus({ systemStatus }: ServiceStatusProps) {
  if (!systemStatus) {
    return (
      <div className="rounded-lg border border-gray-200 bg-white p-4">
        <div className="animate-pulse">
          <div className="h-4 bg-gray-200 rounded w-1/3 mb-4"></div>
          <div className="space-y-3">
            <div className="h-3 bg-gray-200 rounded"></div>
            <div className="h-3 bg-gray-200 rounded"></div>
            <div className="h-3 bg-gray-200 rounded"></div>
          </div>
        </div>
      </div>
    );
  }

  const isExternalMode = systemStatus.backend.mode === 'external_services';

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4">
      <h3 className="font-semibold text-gray-900 mb-4">System Status</h3>

      <div className="space-y-3">
        {/* Backend */}
        <div className="flex items-center justify-between">
          <span className="text-sm text-gray-600">Gemma Backend</span>
          <StatusBadge status={systemStatus.backend.running ? 'online' : 'offline'} size="sm" />
        </div>

        {/* Mode */}
        <div className="flex items-center justify-between">
          <span className="text-sm text-gray-600">Mode</span>
          <span className="text-sm font-medium text-gray-900">
            {isExternalMode ? 'Microservices' : 'Internal'}
          </span>
        </div>

        {/* OmniParser / Queue Service */}
        <div className="flex items-center justify-between">
          <span className="text-sm text-gray-600">
            {isExternalMode ? 'Queue Service' : 'OmniParser'}
          </span>
          <StatusBadge
            status={systemStatus.omniparser.status as 'online' | 'offline' | 'error'}
            size="sm"
          />
        </div>

        {/* External Services */}
        {isExternalMode && systemStatus.services && (
          <>
            <div className="border-t border-gray-100 pt-3 mt-3">
              <p className="text-xs text-gray-500 mb-2">External Services</p>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-600">Discovery Service</span>
              <StatusBadge status={systemStatus.services.discovery_service.available} size="sm" />
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-600">Queue Service</span>
              <StatusBadge status={systemStatus.services.queue_service.available} size="sm" />
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-600">Preset Manager</span>
              <StatusBadge status={systemStatus.services.preset_manager.available} size="sm" />
            </div>
          </>
        )}

        {/* Device Stats */}
        <div className="border-t border-gray-100 pt-3 mt-3">
          <p className="text-xs text-gray-500 mb-2">Devices</p>
        </div>
        <div className="grid grid-cols-2 gap-2 text-sm">
          <div className="flex items-center justify-between bg-gray-50 rounded p-2">
            <span className="text-gray-600">Online</span>
            <span className="font-semibold text-green-600">
              {systemStatus.devices.online_devices}
            </span>
          </div>
          <div className="flex items-center justify-between bg-gray-50 rounded p-2">
            <span className="text-gray-600">Total</span>
            <span className="font-semibold">
              {systemStatus.devices.total_devices}
            </span>
          </div>
          <div className="flex items-center justify-between bg-gray-50 rounded p-2">
            <span className="text-gray-600">Paired</span>
            <span className="font-semibold text-blue-600">
              {systemStatus.devices.paired_devices}
            </span>
          </div>
          <div className="flex items-center justify-between bg-gray-50 rounded p-2">
            <span className="text-gray-600">Offline</span>
            <span className="font-semibold text-gray-500">
              {systemStatus.devices.offline_devices}
            </span>
          </div>
        </div>

        {/* WebSocket Clients */}
        <div className="flex items-center justify-between text-sm">
          <span className="text-gray-600">Connected Clients</span>
          <span className="font-medium">{systemStatus.backend.websocket_clients}</span>
        </div>
      </div>
    </div>
  );
}
