import { useState } from 'react';
import { useDevices } from '../hooks';
import { SUTCard, SUTDetailPanel } from '../components';
import { triggerDiscoveryScan } from '../api';
import type { SUT } from '../types';

export function Devices() {
  const { devices, loading, pair, unpair, refetch } = useDevices();
  const [scanning, setScanning] = useState(false);
  const [filter, setFilter] = useState<'all' | 'online' | 'paired'>('all');
  const [selectedSut, setSelectedSut] = useState<SUT | null>(null);

  const handleScan = async () => {
    setScanning(true);
    try {
      await triggerDiscoveryScan();
      await refetch();
    } catch (error) {
      console.error('Scan failed:', error);
    } finally {
      setScanning(false);
    }
  };

  const filteredDevices = devices.filter((device) => {
    if (filter === 'online') return device.status === 'online';
    if (filter === 'paired') return device.is_paired;
    return true;
  });

  const stats = {
    total: devices.length,
    online: devices.filter(d => d.status === 'online').length,
    paired: devices.filter(d => d.is_paired).length,
  };

  return (
    <div className="space-y-6 p-4 lg:p-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">SUTs</h1>
          <p className="text-text-muted">Manage your Systems Under Test</p>
        </div>
        <button
          onClick={handleScan}
          disabled={scanning}
          className="px-4 py-2 bg-primary text-white rounded-lg font-medium hover:bg-primary/90 disabled:opacity-50 transition-colors w-full sm:w-auto"
        >
          {scanning ? 'Scanning...' : 'Scan Network'}
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="card p-4">
          <p className="text-sm text-text-muted">Total Devices</p>
          <p className="text-2xl font-bold text-text-primary">{stats.total}</p>
        </div>
        <div className="card p-4">
          <p className="text-sm text-text-muted">Online</p>
          <p className="text-2xl font-bold text-success">{stats.online}</p>
        </div>
        <div className="card p-4">
          <p className="text-sm text-text-muted">Paired</p>
          <p className="text-2xl font-bold text-primary">{stats.paired}</p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-2">
        {(['all', 'online', 'paired'] as const).map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`px-4 py-2 rounded-lg font-medium transition-colors ${
              filter === f
                ? 'bg-primary text-white'
                : 'bg-surface-elevated text-text-secondary hover:bg-surface-hover'
            }`}
          >
            {f.charAt(0).toUpperCase() + f.slice(1)}
          </button>
        ))}
      </div>

      {/* Main Content - Grid + Detail Panel */}
      <div className="flex flex-col lg:flex-row gap-6">
        {/* Device Grid */}
        <div className={`flex-1 ${selectedSut ? 'lg:w-2/3' : 'w-full'}`}>
          {loading ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
              {[...Array(6)].map((_, i) => (
                <div key={i} className="card p-4 animate-pulse">
                  <div className="h-4 bg-surface-elevated rounded w-2/3 mb-4"></div>
                  <div className="h-3 bg-surface-elevated rounded w-1/2 mb-2"></div>
                  <div className="h-3 bg-surface-elevated rounded w-1/3"></div>
                </div>
              ))}
            </div>
          ) : filteredDevices.length === 0 ? (
            <div className="text-center py-12 card">
              <p className="text-text-muted">No devices found</p>
              <button
                onClick={handleScan}
                className="mt-4 text-primary hover:text-primary/80 transition-colors"
              >
                Scan for devices
              </button>
            </div>
          ) : (
            <div className={`grid gap-4 ${
              selectedSut
                ? 'grid-cols-1 sm:grid-cols-2'
                : 'grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4'
            }`}>
              {filteredDevices.map((device) => (
                <SUTCard
                  key={device.device_id}
                  sut={device}
                  isSelected={selectedSut?.device_id === device.device_id}
                  onSelect={(sut) => setSelectedSut(
                    selectedSut?.device_id === sut.device_id ? null : sut
                  )}
                  onPair={(id) => pair(id).catch(console.error)}
                  onUnpair={(id) => unpair(id).catch(console.error)}
                />
              ))}
            </div>
          )}
        </div>

        {/* Detail Panel - Slides in when SUT selected */}
        {selectedSut && (
          <div className="lg:w-1/3 lg:min-w-[360px] lg:max-w-[480px]">
            <SUTDetailPanel
              sut={selectedSut}
              onClose={() => setSelectedSut(null)}
            />
          </div>
        )}
      </div>
    </div>
  );
}
