import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { useWebSocket, TimelineEvent as WsTimelineEvent } from '../hooks/useWebSocket';

// Module-level cache for timeline data - persists across component re-mounts
// Key: runId, Value: { events: TimelineEvent[], timestamp: number }
const timelineCache = new Map<string, { events: TimelineEvent[]; timestamp: number }>();

// Cache TTL for active runs (1 second) - use cached data briefly, then refresh
const ACTIVE_CACHE_TTL_MS = 1000;
// Cache is effectively permanent for completed runs - they don't change

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

  // Check if this is a parallel task
  const isParallelTask = event.metadata?.parallel === true;

  return (
    <div className="flex flex-col items-center min-w-[100px] flex-shrink-0 relative group">
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

      {/* Parallel task indicator */}
      {isParallelTask && (
        <div
          className="absolute -top-1 -right-1 z-20 w-4 h-4 rounded-full bg-warning/90 flex items-center justify-center"
          title="Running in parallel with other tasks"
        >
          <svg className="w-2.5 h-2.5 text-black" fill="currentColor" viewBox="0 0 24 24">
            <path d="M13 3L4 14h7l-1 7 9-11h-7l1-7z" />
          </svg>
        </div>
      )}

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
        {isParallelTask && <span className="text-warning">⚡</span>} {shortMessage}
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

  const isParallelTask = event.metadata?.parallel === true;

  return (
    <div className="mt-4 p-4 rounded-lg bg-surface-elevated border border-border">
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${colors.bg} ${colors.text}`}>
            {event.status}
          </span>
          {isParallelTask && (
            <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-warning/20 text-warning flex items-center gap-1">
              <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 24 24">
                <path d="M13 3L4 14h7l-1 7 9-11h-7l1-7z" />
              </svg>
              Parallel
            </span>
          )}
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

// Calculate grid position for snake pattern (boustrophedon)
function getSnakePosition(index: number, cols: number): { row: number; col: number } {
  const row = Math.floor(index / cols);
  const posInRow = index % cols;
  // Even rows: left-to-right (0,1,2,3,4,5)
  // Odd rows: right-to-left (5,4,3,2,1,0)
  const col = row % 2 === 0 ? posInRow : (cols - 1 - posInRow);
  return { row, col };
}

// Snake timeline constants
const MIN_CELL_WIDTH = 80; // px - minimum width of each cell
const CELL_HEIGHT = 80; // px - height for countdown + circle + label
const GAP_X = 4; // horizontal gap between cells
const GAP_Y = 8; // vertical gap between rows
const CIRCLE_SIZE = 24; // px - size of the node circle

export function RunTimeline({ runId, pollInterval = 2000, compact = false, runStatus, filterIteration, previousGameName }: RunTimelineProps) {
  // Initialize from cache if available for instant display
  const cachedData = timelineCache.get(runId);
  const [events, setEvents] = useState<TimelineEvent[]>(cachedData?.events || []);
  const [loading, setLoading] = useState(!cachedData); // Not loading if we have cache
  const [error, setError] = useState<string | null>(null);
  const [selectedEvent, setSelectedEvent] = useState<TimelineEvent | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [cols, setCols] = useState(6); // Default columns, will be calculated
  const [cellWidth, setCellWidth] = useState(MIN_CELL_WIDTH); // Actual cell width to fill container

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

        // Add or update event in local state and cache
        setEvents(prev => {
          const existingIndex = prev.findIndex(e => e.event_id === event.event_id);
          let newEvents: TimelineEvent[];
          if (existingIndex >= 0) {
            // Update existing event
            newEvents = [...prev];
            newEvents[existingIndex] = event;
          } else {
            // Add new event, sorted by timestamp
            newEvents = [...prev, event];
            newEvents.sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());
          }

          // Update cache with new events
          timelineCache.set(runId, { events: newEvents, timestamp: Date.now() });

          return newEvents;
        });
        setLoading(false);
        setError(null);
      }
    });
    return unsubscribe;
  }, [runId, onTimelineEvent]);

  // Responsive columns - calculate based on container width
  // 1. Calculate how many columns fit at MIN_CELL_WIDTH
  // 2. Calculate actual cell width to fill the container exactly
  useEffect(() => {
    if (!containerRef.current) return;

    const calculateLayout = (width: number) => {
      if (width <= 0) return null; // Skip if no width yet

      // How many columns fit? (accounting for gaps between columns)
      // Total width = numCols * cellWidth + (numCols - 1) * GAP_X
      // Rearranging: numCols = (width + GAP_X) / (cellWidth + GAP_X)
      const numCols = Math.max(4, Math.floor((width + GAP_X) / (MIN_CELL_WIDTH + GAP_X)));

      // Now calculate actual cell width to fill the container perfectly
      // width = numCols * actualCellWidth + (numCols - 1) * GAP_X
      // actualCellWidth = (width - (numCols - 1) * GAP_X) / numCols
      const actualCellWidth = (width - (numCols - 1) * GAP_X) / numCols;

      return { numCols, actualCellWidth };
    };

    const updateLayout = () => {
      if (!containerRef.current) return;
      const width = containerRef.current.getBoundingClientRect().width;
      const result = calculateLayout(width);
      if (result) {
        setCols(result.numCols);
        setCellWidth(result.actualCellWidth);
      }
    };

    // Use requestAnimationFrame to ensure layout is complete before measuring
    // This is important when component is inside expandable sections
    requestAnimationFrame(() => {
      updateLayout();
    });

    // Observe for changes
    const observer = new ResizeObserver(entries => {
      const width = entries[0]?.contentRect.width || 0;
      const result = calculateLayout(width);
      if (result) {
        setCols(result.numCols);
        setCellWidth(result.actualCellWidth);
      }
    });
    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, [events.length]); // Re-run when events change (e.g., when row expands)

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

  const fetchTimeline = useCallback(async (skipCacheCheck = false) => {
    // Check if cache is fresh enough (for non-completed runs)
    if (!skipCacheCheck) {
      const cached = timelineCache.get(runId);
      if (cached) {
        const isCompleted = runStatus === 'completed' || runStatus === 'failed';
        const cacheAge = Date.now() - cached.timestamp;
        // For completed runs, always use cache; for active, use if fresh
        if (isCompleted || cacheAge < ACTIVE_CACHE_TTL_MS) {
          if (events.length === 0) {
            setEvents(cached.events);
            setLoading(false);
          }
          return;
        }
      }
    }

    try {
      const response = await fetch(`/api/runs/${runId}/timeline`);
      if (!response.ok) {
        throw new Error('Failed to fetch timeline');
      }
      const data = await response.json();
      const newEvents = data.events || [];
      setEvents(newEvents);
      setError(null);

      // Update cache
      timelineCache.set(runId, { events: newEvents, timestamp: Date.now() });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load timeline');
    } finally {
      setLoading(false);
    }
  }, [runId, runStatus, events.length]);

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

  // Calculate grid data with snake pattern and connectors
  const gridData = useMemo(() => {
    const totalRows = Math.ceil(displayEvents.length / cols);

    // Create positioned events
    const positioned = displayEvents.map((event, index) => {
      const { row, col } = getSnakePosition(index, cols);
      return { event, row, col, index };
    });

    // Generate connector segments for SVG lines
    const connectors: Array<{
      type: 'horizontal' | 'vertical';
      row: number;
      col: number;
      direction?: 'down-left' | 'down-right';
      sourceIndex: number;
    }> = [];

    for (let i = 0; i < displayEvents.length - 1; i++) {
      const curr = getSnakePosition(i, cols);
      const next = getSnakePosition(i + 1, cols);

      if (curr.row === next.row) {
        // Horizontal connector within same row
        const minCol = Math.min(curr.col, next.col);
        connectors.push({ type: 'horizontal', row: curr.row, col: minCol, sourceIndex: i });
      } else {
        // Vertical connector between rows (at row end)
        const isEvenRow = curr.row % 2 === 0;
        connectors.push({
          type: 'vertical',
          row: curr.row,
          col: isEvenRow ? cols - 1 : 0,
          direction: isEvenRow ? 'down-left' : 'down-right',
          sourceIndex: i,
        });
      }
    }

    return { positioned, connectors, totalRows };
  }, [displayEvents, cols]);

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

  // Helper to get line color based on event status
  const getLineColor = (status: string) => {
    switch (status) {
      case 'completed': return 'var(--color-success)';
      case 'failed':
      case 'error': return 'var(--color-danger)';
      case 'in_progress': return 'var(--color-primary)';
      default: return 'var(--color-border)';
    }
  };

  // Calculate top offset for circle center (space for time label + half circle)
  const TIME_LABEL_HEIGHT = 24; // h-6 for time label
  const circleCenter = TIME_LABEL_HEIGHT + CIRCLE_SIZE / 2;

  return (
    <div ref={containerRef} className="w-full">
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

      {/* Snake pattern timeline grid - fills available width */}
      <div className="relative overflow-hidden w-full">
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: `repeat(${cols}, ${cellWidth}px)`,
            gridTemplateRows: `repeat(${gridData.totalRows}, ${CELL_HEIGHT}px)`,
            gap: `${GAP_Y}px ${GAP_X}px`,
          }}
        >
          {/* SVG layer for connecting lines (behind circles) */}
          <svg
            className="absolute inset-0 pointer-events-none z-0"
            style={{
              width: cols * cellWidth + (cols - 1) * GAP_X,
              height: gridData.totalRows * (CELL_HEIGHT + GAP_Y) - GAP_Y,
            }}
          >
            {gridData.connectors.map((conn, i) => {
              const cellWidthWithGap = cellWidth + GAP_X;
              const cellHeightWithGap = CELL_HEIGHT + GAP_Y;
              const sourceEvent = displayEvents[conn.sourceIndex];
              const lineColor = getLineColor(sourceEvent?.status || 'pending');

              if (conn.type === 'horizontal') {
                // Horizontal line between two circles
                const x1 = conn.col * cellWidthWithGap + cellWidth / 2 + CIRCLE_SIZE / 2;
                const x2 = (conn.col + 1) * cellWidthWithGap + cellWidth / 2 - CIRCLE_SIZE / 2;
                const y = conn.row * cellHeightWithGap + circleCenter;

                return (
                  <line
                    key={i}
                    x1={x1}
                    y1={y}
                    x2={x2}
                    y2={y}
                    stroke={lineColor}
                    strokeWidth="2"
                  />
                );
              } else {
                // Vertical connector between rows
                const isRight = conn.direction === 'down-left';
                const x = isRight
                  ? (cols - 1) * cellWidthWithGap + cellWidth / 2
                  : cellWidth / 2;
                const y1 = conn.row * cellHeightWithGap + circleCenter + CIRCLE_SIZE / 2;
                const y2 = (conn.row + 1) * cellHeightWithGap + circleCenter - CIRCLE_SIZE / 2;

                return (
                  <line
                    key={i}
                    x1={x}
                    y1={y1}
                    x2={x}
                    y2={y2}
                    stroke={lineColor}
                    strokeWidth="2"
                  />
                );
              }
            })}
          </svg>

          {/* Render event nodes in snake pattern */}
          {gridData.positioned.map(({ event, row, col }) => {
            const colors = statusColors[event.status] || statusColors.pending;
            const isSelected = selectedEvent?.event_id === event.event_id;

            // Check if this is a waiting event
            const isWaitingEvent = event.status === 'in_progress' && (
              event.metadata?.countdown ||
              event.metadata?.timeout ||
              event.metadata?.seconds ||
              event.metadata?.wait_seconds ||
              event.metadata?.duration ||
              event.metadata?.benchmark_duration
            );

            // Format time
            const formatTime = (isoString: string) => {
              const date = new Date(isoString);
              return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
            };

            // Truncate message
            const shortMessage = event.message.length > 20
              ? event.message.substring(0, 20) + '...'
              : event.message;

            return (
              <div
                key={event.event_id}
                className="flex flex-col items-center z-10 group"
                style={{
                  gridColumn: col + 1,
                  gridRow: row + 1,
                }}
                title={event.message}
              >
                {/* Time label or countdown above */}
                <div className="h-6 mb-1 flex items-center justify-center">
                  {isWaitingEvent ? (
                    <WaitCounter event={event} position="above" />
                  ) : (
                    <div className="text-[10px] text-text-muted font-mono opacity-0 group-hover:opacity-100 transition-opacity">
                      {formatTime(event.timestamp)}
                    </div>
                  )}
                </div>

                {/* Circle node */}
                <button
                  onClick={() => setSelectedEvent(isSelected ? null : event)}
                  className={`
                    flex items-center justify-center rounded-full border-2 transition-all
                    ${colors.bg} ${colors.border} ${colors.text}
                    ${isSelected ? 'ring-2 ring-primary/50 ring-offset-2 ring-offset-surface scale-110' : ''}
                    hover:scale-110 cursor-pointer
                  `}
                  style={{
                    width: `${CIRCLE_SIZE}px`,
                    height: `${CIRCLE_SIZE}px`,
                  }}
                >
                  <EventIcon eventType={event.event_type} status={event.status} />
                </button>

                {/* Label below */}
                <div className="mt-1 text-[10px] text-text-secondary text-center leading-tight w-full line-clamp-2 px-0.5">
                  {shortMessage}
                </div>
              </div>
            );
          })}
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
