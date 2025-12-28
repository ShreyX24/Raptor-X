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
    online: 'bg-success',
    offline: 'bg-text-muted',
    busy: 'bg-warning',
    error: 'bg-danger',
  };

  const statusColor = statusColors[sut.status] || 'bg-text-muted';

  const formatTime = (isoString: string | null) => {
    if (!isoString) return 'Never';
    const date = new Date(isoString);
    return date.toLocaleTimeString();
  };

  return (
    <div
      className={`card p-4 transition-all cursor-pointer hover:border-primary/50 ${
        isSelected ? 'border-primary bg-primary/5' : ''
      }`}
      onClick={() => onSelect?.(sut)}
    >
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className={`h-3 w-3 rounded-full ${statusColor}`} />
          <div>
            <h3 className="font-semibold text-text-primary">
              {sut.hostname || sut.ip}
            </h3>
            <p className="text-sm text-text-muted">{sut.ip}:{sut.port}</p>
          </div>
        </div>
        {sut.is_paired && (
          <span className="rounded-full bg-primary/10 px-2 py-1 text-xs font-medium text-primary">
            Paired
          </span>
        )}
      </div>

      <div className="mt-4 grid grid-cols-2 gap-2 text-sm">
        <div>
          <span className="text-text-muted">Status:</span>
          <span className="ml-2 capitalize font-medium text-text-primary">{sut.status}</span>
        </div>
        <div>
          <span className="text-text-muted">Success:</span>
          <span className="ml-2 font-medium text-text-primary">{sut.success_rate.toFixed(1)}%</span>
        </div>
        <div>
          <span className="text-text-muted">Last Seen:</span>
          <span className="ml-2 text-text-secondary">{formatTime(sut.last_seen)}</span>
        </div>
        <div>
          <span className="text-text-muted">Errors:</span>
          <span className="ml-2 text-text-secondary">{sut.error_count}</span>
        </div>
      </div>

      {sut.current_task && (
        <div className="mt-3 rounded bg-warning/10 p-2 text-sm text-warning border border-warning/20">
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
            className="flex-1 rounded bg-surface-elevated px-3 py-1.5 text-sm font-medium text-text-secondary hover:bg-surface-hover transition-colors"
          >
            Unpair
          </button>
        ) : (
          <button
            onClick={(e) => {
              e.stopPropagation();
              onPair?.(sut.device_id);
            }}
            className="flex-1 rounded bg-primary px-3 py-1.5 text-sm font-medium text-white hover:bg-primary/90 disabled:opacity-50 transition-colors"
            disabled={sut.status !== 'online'}
          >
            Pair
          </button>
        )}
      </div>
    </div>
  );
}
