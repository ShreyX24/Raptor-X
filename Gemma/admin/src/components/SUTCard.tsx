import type { SUT } from '../types';

interface SUTCardProps {
  sut: SUT;
  onPair?: (deviceId: string) => void;
  onUnpair?: (deviceId: string) => void;
  onSelect?: (sut: SUT) => void;
  isSelected?: boolean;
}

export function SUTCard({ sut, onPair, onUnpair, onSelect, isSelected }: SUTCardProps) {
  const statusColors: Record<string, string> = {
    online: 'bg-green-500',
    offline: 'bg-gray-400',
    busy: 'bg-yellow-500',
    error: 'bg-red-500',
  };

  const statusColor = statusColors[sut.status] || 'bg-gray-400';

  const formatTime = (isoString: string | null) => {
    if (!isoString) return 'Never';
    const date = new Date(isoString);
    return date.toLocaleTimeString();
  };

  return (
    <div
      className={`rounded-lg border p-4 transition-all cursor-pointer hover:shadow-md ${
        isSelected ? 'border-blue-500 bg-blue-50' : 'border-gray-200 bg-white'
      }`}
      onClick={() => onSelect?.(sut)}
    >
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className={`h-3 w-3 rounded-full ${statusColor}`} />
          <div>
            <h3 className="font-semibold text-gray-900">
              {sut.hostname || sut.ip}
            </h3>
            <p className="text-sm text-gray-500">{sut.ip}:{sut.port}</p>
          </div>
        </div>
        {sut.is_paired && (
          <span className="rounded-full bg-blue-100 px-2 py-1 text-xs font-medium text-blue-700">
            Paired
          </span>
        )}
      </div>

      <div className="mt-4 grid grid-cols-2 gap-2 text-sm">
        <div>
          <span className="text-gray-500">Status:</span>
          <span className="ml-2 capitalize font-medium">{sut.status}</span>
        </div>
        <div>
          <span className="text-gray-500">Success:</span>
          <span className="ml-2 font-medium">{sut.success_rate.toFixed(1)}%</span>
        </div>
        <div>
          <span className="text-gray-500">Last Seen:</span>
          <span className="ml-2">{formatTime(sut.last_seen)}</span>
        </div>
        <div>
          <span className="text-gray-500">Errors:</span>
          <span className="ml-2">{sut.error_count}</span>
        </div>
      </div>

      {sut.current_task && (
        <div className="mt-3 rounded bg-yellow-50 p-2 text-sm text-yellow-700">
          {sut.current_task}
        </div>
      )}

      <div className="mt-4 flex gap-2">
        {sut.is_paired ? (
          <button
            onClick={(e) => {
              e.stopPropagation();
              onUnpair?.(sut.device_id);
            }}
            className="flex-1 rounded bg-gray-100 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-200"
          >
            Unpair
          </button>
        ) : (
          <button
            onClick={(e) => {
              e.stopPropagation();
              onPair?.(sut.device_id);
            }}
            className="flex-1 rounded bg-blue-500 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-600"
            disabled={sut.status !== 'online'}
          >
            Pair
          </button>
        )}
      </div>
    </div>
  );
}
