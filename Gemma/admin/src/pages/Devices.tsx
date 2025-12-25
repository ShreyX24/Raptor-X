import { useState } from 'react';
import { useDevices } from '../hooks';
import { SUTCard } from '../components';
import { triggerDiscoveryScan } from '../api';

export function Devices() {
  const { devices, loading, pair, unpair, refetch } = useDevices();
  const [scanning, setScanning] = useState(false);
  const [filter, setFilter] = useState<'all' | 'online' | 'paired'>('all');

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
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Devices</h1>
          <p className="text-gray-500">Manage your SUTs (Systems Under Test)</p>
        </div>
        <button
          onClick={handleScan}
          disabled={scanning}
          className="px-4 py-2 bg-blue-500 text-white rounded-lg font-medium hover:bg-blue-600 disabled:bg-blue-300"
        >
          {scanning ? 'Scanning...' : 'Scan Network'}
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <p className="text-sm text-gray-500">Total Devices</p>
          <p className="text-2xl font-bold text-gray-900">{stats.total}</p>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <p className="text-sm text-gray-500">Online</p>
          <p className="text-2xl font-bold text-green-600">{stats.online}</p>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <p className="text-sm text-gray-500">Paired</p>
          <p className="text-2xl font-bold text-blue-600">{stats.paired}</p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-2">
        {(['all', 'online', 'paired'] as const).map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`px-4 py-2 rounded-lg font-medium transition-colors ${
              filter === f
                ? 'bg-gray-900 text-white'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            {f.charAt(0).toUpperCase() + f.slice(1)}
          </button>
        ))}
      </div>

      {/* Device Grid */}
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="bg-white rounded-lg border border-gray-200 p-4 animate-pulse">
              <div className="h-4 bg-gray-200 rounded w-2/3 mb-4"></div>
              <div className="h-3 bg-gray-200 rounded w-1/2 mb-2"></div>
              <div className="h-3 bg-gray-200 rounded w-1/3"></div>
            </div>
          ))}
        </div>
      ) : filteredDevices.length === 0 ? (
        <div className="text-center py-12 bg-white rounded-lg border border-gray-200">
          <p className="text-gray-500">No devices found</p>
          <button
            onClick={handleScan}
            className="mt-4 text-blue-500 hover:text-blue-600"
          >
            Scan for devices
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredDevices.map((device) => (
            <SUTCard
              key={device.device_id}
              sut={device}
              onPair={(id) => pair(id).catch(console.error)}
              onUnpair={(id) => unpair(id).catch(console.error)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
