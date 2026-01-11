import { useState, useEffect, useRef, useCallback } from 'react';
import { useWebSocket, TimelineEvent as WsTimelineEvent } from '../hooks/useWebSocket';

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

// Live wait counter component - displays above circles
function WaitCounter({ event, position = 'inline' }: { event: TimelineEvent; position?: 'inline' | 'above' }) {
  // Extract wait duration from metadata - check all possible keys
  const waitDuration =
    (event.metadata?.countdown as number) ||
    (event.metadata?.timeout as number) ||
    (event.metadata?.seconds as number) ||
    (event.metadata?.wait_seconds as number) ||
    (event.metadata?.duration as number) ||
    (event.metadata?.benchmark_duration as number) ||
    null;

  const remaining = useCountdown(event.timestamp, waitDuration);

  if (remaining === null || remaining <= 0) return null;

  // Format time as MM:SS for longer durations
  const formatTime = (seconds: number) => {
    if (seconds >= 60) {
      const mins = Math.floor(seconds / 60);
      const secs = seconds % 60;
      return `${mins}:${secs.toString().padStart(2, '0')}`;
    }
    return `${seconds}s`;
  };

  if (position === 'above') {
    return (
      <span className="font-numbers font-bold text-white text-xl animate-pulse drop-shadow-lg tracking-wide">
        {formatTime(remaining)}
      </span>
    );
  }

  return (
    <span className="ml-1 text-primary font-mono text-[10px] animate-pulse">
      {formatTime(remaining)}
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
  status: 'pending' | 'in_progress' | 'completed' | 'failed' | 'skipped' | 'warning' | 'error';
  duration_ms: number | null;
  metadata: Record<string, unknown>;
  replaces_event_id: string | null;
  group: string | null;
}

interface RunTimelineProps {
  runId: string;
  pollInterval?: number;  // ms, default 2000
  compact?: boolean;
  runStatus?: string;  // Overall run status - used to adjust event display for completed/failed runs
  filterIteration?: number;  // Filter to show only events from a specific iteration (1-indexed)
  previousGameName?: string;  // For queued runs in campaigns - shows "Awaiting X completion"
}

// Status colors
const statusColors: Record<string, { bg: string; border: string; text: string }> = {
  pending: { bg: 'bg-surface-elevated', border: 'border-border', text: 'text-text-muted' },
  in_progress: { bg: 'bg-primary/20', border: 'border-primary', text: 'text-primary' },
  completed: { bg: 'bg-success/20', border: 'border-success', text: 'text-success' },
  failed: { bg: 'bg-danger/20', border: 'border-danger', text: 'text-danger' },
  error: { bg: 'bg-danger/20', border: 'border-danger', text: 'text-danger' },
  skipped: { bg: 'bg-warning/20', border: 'border-warning', text: 'text-warning' },
  warning: { bg: 'bg-warning/20', border: 'border-warning', text: 'text-warning' },
};

// Steam event types for special handling
const STEAM_EVENT_TYPES = [
  'steam_dialog_checking',
  'steam_dialog_detected',
  'steam_dialog_dismissed',
  'steam_account_busy',
  'steam_account_switching',
  'steam_no_accounts',
];

// Event type icons
function EventIcon({ eventType, status }: { eventType: string; status: string }) {
  const iconClass = "w-3.5 h-3.5";
  const isSteamEvent = STEAM_EVENT_TYPES.includes(eventType);

  // Steam icon for Steam-related events
  if (isSteamEvent && status !== 'in_progress') {
    // Warning/exclamation for busy/no accounts
    if (status === 'warning' || status === 'error' || eventType === 'steam_account_busy' || eventType === 'steam_no_accounts') {
      return (
        <svg className={iconClass} fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
        </svg>
      );
    }
    // Account switching - arrows
    if (eventType === 'steam_account_switching') {
      return (
        <svg className={iconClass} fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4" />
        </svg>
      );
    }
  }

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

  // X for failed/error
  if (status === 'failed' || status === 'error') {
    return (
      <svg className={iconClass} fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
      </svg>
    );
  }

  // Warning icon for warning status
  if (status === 'warning') {
    return (
      <svg className={iconClass} fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
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

  // Check if this is a waiting event (has duration metadata)
  const isWaitingEvent = event.status === 'in_progress' && (
    event.metadata?.countdown ||
    event.metadata?.timeout ||
    event.metadata?.seconds ||
    event.metadata?.wait_seconds ||
    event.metadata?.duration ||
    event.metadata?.benchmark_duration
  );

  return (
    <div className="flex flex-col items-center min-w-[100px] relative group">
      {/* Time label above - shown on hover, or countdown if waiting */}
      <div className="h-6 mb-1 flex items-center justify-center">
        {isWaitingEvent ? (
          <WaitCounter event={event} position="above" />
        ) : (
          <div className="text-[10px] text-text-muted font-mono opacity-0 group-hover:opacity-100 transition-opacity">
            {formatTime(event.timestamp)}
          </div>
        )}
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

// Helper function to extract iteration number from event
function getEventIteration(event: TimelineEvent): number | null {
  // Check metadata first
  if (event.metadata?.iteration !== undefined) {
    return Number(event.metadata.iteration);
  }
  if (event.metadata?.current_iteration !== undefined) {
    return Number(event.metadata.current_iteration);
  }

  // Check group field (might be like "iteration_1" or "iteration-1")
  if (event.group) {
    const match = event.group.match(/iteration[_-]?(\d+)/i);
    if (match) return parseInt(match[1], 10);
  }

  // Check message for iteration patterns like "Iteration 1", "iteration 2/3", "Starting iteration 1"
  const msgMatch = event.message.match(/iteration\s*(\d+)/i);
  if (msgMatch) return parseInt(msgMatch[1], 10);

  // Check event type
  const typeMatch = event.event_type.match(/iteration[_-]?(\d+)/i);
  if (typeMatch) return parseInt(typeMatch[1], 10);

  return null;
}

export function RunTimeline({ runId, pollInterval = 2000, compact = false, runStatus, filterIteration, previousGameName }: RunTimelineProps) {
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedEvent, setSelectedEvent] = useState<TimelineEvent | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  // WebSocket for real-time timeline updates
  const { onTimelineEvent, isConnected } = useWebSocket();

  // Subscribe to WebSocket timeline events for this run
  useEffect(() => {
    const unsubscribe = onTimelineEvent((wsEvent: WsTimelineEvent) => {
      if (wsEvent.run_id === runId) {
        // Convert WebSocket event to local TimelineEvent format
        const event: TimelineEvent = {
          event_id: wsEvent.event_id,
          event_type: wsEvent.event_type,
          message: wsEvent.message,
          timestamp: wsEvent.timestamp,
          status: wsEvent.status,
          duration_ms: wsEvent.duration_ms ?? null,
          metadata: wsEvent.metadata ?? {},
          replaces_event_id: wsEvent.replaces_event_id ?? null,
          group: wsEvent.group ?? null,
        };

        // Add or update event in local state
        setEvents(prev => {
          const existingIndex = prev.findIndex(e => e.event_id === event.event_id);
          if (existingIndex >= 0) {
            // Update existing event
            const updated = [...prev];
            updated[existingIndex] = event;
            return updated;
          }
          // Add new event, sorted by timestamp
          const newEvents = [...prev, event];
          newEvents.sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());
          return newEvents;
        });
        setLoading(false);
        setError(null);
      }
    });
    return unsubscribe;
  }, [runId, onTimelineEvent]);

  // For queued runs, show "Awaiting X completion" instead of fetching timeline
  if (runStatus === 'queued') {
    const waitingMessage = previousGameName
      ? `Awaiting ${previousGameName} completion`
      : 'Waiting in queue...';

    return (
      <div className="flex items-center justify-center py-6">
        <div className="flex items-center gap-3 text-warning">
          <svg className="w-5 h-5 animate-pulse" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <span className="text-sm font-medium">{waitingMessage}</span>
        </div>
      </div>
    );
  }

  // Adjust event status based on overall run status
  // When a run has failed/completed, in_progress events should reflect that
  const adjustEventStatus = useCallback((event: TimelineEvent): TimelineEvent => {
    if (!runStatus) return event;

    // If run is failed and event is still in_progress, mark it as failed
    if (runStatus === 'failed' && (event.status === 'in_progress' || event.status === 'pending')) {
      return { ...event, status: 'failed' };
    }

    // If run is completed and event is still in_progress, mark it as completed
    if (runStatus === 'completed' && event.status === 'in_progress') {
      return { ...event, status: 'completed' };
    }

    return event;
  }, [runStatus]);

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
  // Use slower polling when WebSocket is connected (10s), faster when disconnected (2s default)
  const actualPollInterval = isConnected ? Math.max(pollInterval, 10000) : pollInterval;

  useEffect(() => {
    fetchTimeline();
    // Only set up polling if pollInterval > 0 (0 means no polling)
    if (actualPollInterval > 0) {
      const interval = setInterval(fetchTimeline, actualPollInterval);
      return () => clearInterval(interval);
    }
  }, [fetchTimeline, actualPollInterval]);

  // Auto-scroll to latest event
  useEffect(() => {
    if (scrollRef.current && events.length > 0) {
      scrollRef.current.scrollLeft = scrollRef.current.scrollWidth;
    }
  }, [events.length]);

  // Filter out replaced events for display (keep latest version) and adjust status
  const displayEvents = events
    .filter(event => {
      // Check if any other event replaces this one
      const isReplaced = events.some(e => e.replaces_event_id === event.event_id);
      if (isReplaced) return false;

      // Apply iteration filter if specified
      if (filterIteration !== undefined) {
        const eventIteration = getEventIteration(event);
        // Include events that match the iteration OR have no iteration (global events)
        // Also include events before the first iteration starts (setup events)
        if (eventIteration !== null && eventIteration !== filterIteration) {
          return false;
        }
      }

      return true;
    })
    .map(adjustEventStatus);

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
