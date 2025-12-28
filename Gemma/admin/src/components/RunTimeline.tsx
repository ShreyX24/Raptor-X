import { useState, useEffect, useRef, useCallback } from 'react';

// Helper hook for live countdown
function useCountdown(startTime: string | null, durationSeconds: number | null): number | null {
  const [remaining, setRemaining] = useState<number | null>(null);

  useEffect(() => {
    if (!startTime || !durationSeconds || durationSeconds <= 0) {
      setRemaining(null);
      return;
    }

    const updateRemaining = () => {
      const start = new Date(startTime).getTime();
      const elapsed = Math.floor((Date.now() - start) / 1000);
      const left = Math.max(0, durationSeconds - elapsed);
      setRemaining(left);
    };

    updateRemaining();
    const interval = setInterval(updateRemaining, 1000);
    return () => clearInterval(interval);
  }, [startTime, durationSeconds]);

  return remaining;
}

// Live wait counter component
function WaitCounter({ event }: { event: TimelineEvent }) {
  // Extract wait duration from metadata
  const waitDuration =
    (event.metadata?.seconds as number) ||
    (event.metadata?.wait_seconds as number) ||
    (event.metadata?.duration as number) ||
    null;

  const remaining = useCountdown(event.timestamp, waitDuration);

  if (remaining === null || remaining <= 0) return null;

  return (
    <span className="ml-1 text-primary font-mono text-[10px] animate-pulse">
      {remaining}s
    </span>
  );
}

/**
 * Timeline event from backend
 */
export interface TimelineEvent {
  event_id: string;
  event_type: string;
  message: string;
  timestamp: string;
  status: 'pending' | 'in_progress' | 'completed' | 'failed' | 'skipped';
  duration_ms: number | null;
  metadata: Record<string, unknown>;
  replaces_event_id: string | null;
  group: string | null;
}

interface RunTimelineProps {
  runId: string;
  pollInterval?: number;  // ms, default 2000
  compact?: boolean;
}

// Status colors
const statusColors: Record<string, { bg: string; border: string; text: string }> = {
  pending: { bg: 'bg-surface-elevated', border: 'border-border', text: 'text-text-muted' },
  in_progress: { bg: 'bg-primary/20', border: 'border-primary', text: 'text-primary' },
  completed: { bg: 'bg-success/20', border: 'border-success', text: 'text-success' },
  failed: { bg: 'bg-danger/20', border: 'border-danger', text: 'text-danger' },
  skipped: { bg: 'bg-warning/20', border: 'border-warning', text: 'text-warning' },
};

// Event type icons
function EventIcon({ eventType: _eventType, status }: { eventType: string; status: string }) {
  const iconClass = "w-3.5 h-3.5";

  // Spinner for in-progress
  if (status === 'in_progress') {
    return (
      <svg className={`${iconClass} animate-spin`} fill="none" viewBox="0 0 24 24">
        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
      </svg>
    );
  }

  // Check for completed
  if (status === 'completed') {
    return (
      <svg className={iconClass} fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
      </svg>
    );
  }

  // X for failed
  if (status === 'failed') {
    return (
      <svg className={iconClass} fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
      </svg>
    );
  }

  // Skip arrows for skipped
  if (status === 'skipped') {
    return (
      <svg className={iconClass} fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 5l7 7-7 7M5 5l7 7-7 7" />
      </svg>
    );
  }

  // Empty circle for pending
  return null;
}

// Individual timeline node
function TimelineNode({ event, isFirst: _isFirst, isLast, onClick, isSelected }: {
  event: TimelineEvent;
  isFirst: boolean;
  isLast: boolean;
  onClick: () => void;
  isSelected: boolean;
}) {
  const colors = statusColors[event.status] || statusColors.pending;

  // Format time
  const formatTime = (isoString: string) => {
    const date = new Date(isoString);
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  };

  // Truncate message for display
  const shortMessage = event.message.length > 25
    ? event.message.substring(0, 25) + '...'
    : event.message;

  return (
    <div className="flex flex-col items-center min-w-[100px] relative group">
      {/* Time label above */}
      <div className="text-[10px] text-text-muted mb-1 font-mono opacity-0 group-hover:opacity-100 transition-opacity">
        {formatTime(event.timestamp)}
      </div>

      {/* Node */}
      <button
        onClick={onClick}
        className={`
          relative z-10 w-6 h-6 rounded-full flex items-center justify-center border-2 transition-all
          ${colors.bg} ${colors.border} ${colors.text}
          ${isSelected ? 'ring-2 ring-primary/50 ring-offset-2 ring-offset-surface scale-110' : ''}
          hover:scale-110 cursor-pointer
        `}
        title={event.message}
      >
        <EventIcon eventType={event.event_type} status={event.status} />
      </button>

      {/* Connector line */}
      {!isLast && (
        <div
          className={`absolute left-1/2 top-1/2 h-0.5 z-0 transition-colors
            ${event.status === 'completed' ? 'bg-success' :
              event.status === 'failed' ? 'bg-danger' :
              event.status === 'in_progress' ? 'bg-primary' :
              'bg-border'}
          `}
          style={{
            width: '100%',
            transform: 'translateY(-50%)',
            marginTop: '12px',
          }}
        />
      )}

      {/* Message label below */}
      <div className="mt-2 text-[10px] text-text-secondary text-center max-w-[90px] line-clamp-2" title={event.message}>
        {shortMessage}
        {/* Show live countdown for in_progress waiting events */}
        {event.status === 'in_progress' && <WaitCounter event={event} />}
      </div>
    </div>
  );
}

// Event detail panel
function EventDetailPanel({ event, onClose }: { event: TimelineEvent; onClose: () => void }) {
  const formatDuration = (ms: number | null) => {
    if (!ms) return null;
    if (ms < 1000) return `${ms}ms`;
    const seconds = Math.round(ms / 1000);
    if (seconds < 60) return `${seconds}s`;
    const minutes = Math.floor(seconds / 60);
    return `${minutes}m ${seconds % 60}s`;
  };

  const colors = statusColors[event.status] || statusColors.pending;

  return (
    <div className="mt-4 p-4 rounded-lg bg-surface-elevated border border-border">
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${colors.bg} ${colors.text}`}>
            {event.status}
          </span>
          <span className="text-xs text-text-muted font-mono">
            {new Date(event.timestamp).toLocaleTimeString()}
          </span>
        </div>
        <button
          onClick={onClose}
          className="p-1 text-text-muted hover:text-text-primary rounded transition-colors"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      <p className="text-sm text-text-primary mb-3">{event.message}</p>

      <div className="grid grid-cols-2 gap-2 text-xs">
        <div>
          <span className="text-text-muted">Type:</span>
          <span className="ml-1 text-text-secondary">{event.event_type}</span>
        </div>
        {event.duration_ms && (
          <div>
            <span className="text-text-muted">Duration:</span>
            <span className="ml-1 text-text-secondary font-mono">{formatDuration(event.duration_ms)}</span>
          </div>
        )}
        {event.group && (
          <div>
            <span className="text-text-muted">Group:</span>
            <span className="ml-1 text-text-secondary">{event.group}</span>
          </div>
        )}
      </div>

      {/* Metadata */}
      {Object.keys(event.metadata).length > 0 && (
        <div className="mt-3 pt-3 border-t border-border">
          <div className="text-xs text-text-muted mb-1">Details:</div>
          <div className="text-xs text-text-secondary font-mono bg-surface rounded p-2 max-h-24 overflow-auto">
            {JSON.stringify(event.metadata, null, 2)}
          </div>
        </div>
      )}
    </div>
  );
}

export function RunTimeline({ runId, pollInterval = 2000, compact = false }: RunTimelineProps) {
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedEvent, setSelectedEvent] = useState<TimelineEvent | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  const fetchTimeline = useCallback(async () => {
    try {
      const response = await fetch(`/api/runs/${runId}/timeline`);
      if (!response.ok) {
        throw new Error('Failed to fetch timeline');
      }
      const data = await response.json();
      setEvents(data.events || []);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load timeline');
    } finally {
      setLoading(false);
    }
  }, [runId]);

  // Initial fetch and polling
  useEffect(() => {
    fetchTimeline();
    // Only set up polling if pollInterval > 0 (0 means no polling)
    if (pollInterval > 0) {
      const interval = setInterval(fetchTimeline, pollInterval);
      return () => clearInterval(interval);
    }
  }, [fetchTimeline, pollInterval]);

  // Auto-scroll to latest event
  useEffect(() => {
    if (scrollRef.current && events.length > 0) {
      scrollRef.current.scrollLeft = scrollRef.current.scrollWidth;
    }
  }, [events.length]);

  // Filter out replaced events for display (keep latest version)
  const displayEvents = events.filter(event => {
    // Check if any other event replaces this one
    const isReplaced = events.some(e => e.replaces_event_id === event.event_id);
    return !isReplaced;
  });

  if (loading && events.length === 0) {
    return (
      <div className="flex items-center justify-center py-4">
        <span className="text-text-muted text-sm">Loading timeline...</span>
      </div>
    );
  }

  if (error && events.length === 0) {
    return (
      <div className="flex items-center justify-center py-4">
        <span className="text-danger text-sm">{error}</span>
      </div>
    );
  }

  if (displayEvents.length === 0) {
    return (
      <div className="flex items-center justify-center py-4">
        <span className="text-text-muted text-sm">No timeline data available</span>
      </div>
    );
  }

  // Compact mode - just dots
  if (compact) {
    return (
      <div className="flex items-center gap-1 flex-wrap">
        {displayEvents.map((event) => {
          const colors = statusColors[event.status] || statusColors.pending;
          return (
            <div
              key={event.event_id}
              className={`w-2 h-2 rounded-full ${colors.bg} border ${colors.border}`}
              title={event.message}
            />
          );
        })}
        <span className="text-xs text-text-muted ml-2">
          {displayEvents.filter(e => e.status === 'completed').length}/{displayEvents.length}
        </span>
      </div>
    );
  }

  return (
    <div className="w-full">
      {/* Summary stats */}
      <div className="flex items-center gap-4 mb-2 text-xs text-text-muted">
        <span className="font-numbers">{displayEvents.filter(e => e.status === 'completed').length}/{displayEvents.length}</span>
        {displayEvents.some(e => e.status === 'failed') && (
          <span className="flex items-center gap-1 text-danger">
            <span className="w-2 h-2 rounded-full bg-danger" />
            {displayEvents.filter(e => e.status === 'failed').length} failed
          </span>
        )}
        {displayEvents.some(e => e.status === 'in_progress') && (
          <span className="flex items-center gap-1 text-primary">
            <span className="w-2 h-2 rounded-full bg-primary animate-pulse" />
            in progress
          </span>
        )}
      </div>

      {/* Horizontal scrolling timeline */}
      <div className="relative">
        <div
          ref={scrollRef}
          className="flex items-start gap-0 overflow-x-auto pb-2 scrollbar-thin scrollbar-thumb-border scrollbar-track-transparent"
        >
          {displayEvents.map((event, idx) => (
            <TimelineNode
              key={event.event_id}
              event={event}
              isFirst={idx === 0}
              isLast={idx === displayEvents.length - 1}
              onClick={() => setSelectedEvent(selectedEvent?.event_id === event.event_id ? null : event)}
              isSelected={selectedEvent?.event_id === event.event_id}
            />
          ))}
        </div>
      </div>

      {/* Selected event details */}
      {selectedEvent && (
        <EventDetailPanel
          event={selectedEvent}
          onClose={() => setSelectedEvent(null)}
        />
      )}
    </div>
  );
}

// Also export individual components for flexibility
export { TimelineNode, EventDetailPanel, EventIcon };
