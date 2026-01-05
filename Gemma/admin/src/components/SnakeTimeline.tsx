/**
 * SnakeTimeline - Boustrophedon pattern timeline
 * Uses CSS Grid with explicit cell positioning for proper snake flow
 *
 * Pattern visualization (6 columns):
 * Row 0: [1] → [2] → [3] → [4] → [5] → [6] ↓
 *                                          ↓
 * Row 1: [12] ← [11] ← [10] ← [9] ← [8] ← [7]
 *   ↓
 * Row 2: [13] → [14] → [15] → ...
 */

import { useState, useEffect, useRef, useCallback, useMemo } from 'react';

interface TimelineEvent {
  event_id: string;
  event_type: string;
  message: string;
  timestamp: string;
  status: 'pending' | 'in_progress' | 'completed' | 'failed' | 'warning';
  duration_ms: number | null;
  metadata?: Record<string, unknown>;
  replaces_event_id?: string | null;
}

// Hook for live countdown timer
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

// Countdown display component
function WaitCounter({ event }: { event: TimelineEvent }) {
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

  const formatTime = (seconds: number) => {
    if (seconds >= 60) {
      const mins = Math.floor(seconds / 60);
      const secs = seconds % 60;
      return `${mins}:${secs.toString().padStart(2, '0')}`;
    }
    return `${seconds}s`;
  };

  return (
    <span className="font-mono font-bold text-primary text-sm animate-pulse">
      {formatTime(remaining)}
    </span>
  );
}

interface SnakeTimelineProps {
  runId: string | null;
  gameName?: string; // Game name to display in header
  pollInterval?: number;
  className?: string;
  maxRows?: number; // Max visible rows before scrolling (default: unlimited)
}

// Demo data for testing layout - uncomment to debug snake pattern
// const DEMO_EVENTS: TimelineEvent[] = [
//   { event_id: 'd1', event_type: 'run_started', message: 'Run started', timestamp: '', status: 'completed', duration_ms: 100, metadata: {} },
//   { event_id: 'd2', event_type: 'sut_connecting', message: 'Connecting to SUT', timestamp: '', status: 'completed', duration_ms: 500, metadata: {} },
//   { event_id: 'd3', event_type: 'sut_connected', message: 'SUT connected', timestamp: '', status: 'completed', duration_ms: 100, metadata: {} },
//   { event_id: 'd4', event_type: 'resolution_detected', message: 'Resolution 1920x1080', timestamp: '', status: 'completed', duration_ms: 200, metadata: {} },
//   { event_id: 'd5', event_type: 'omniparser_connected', message: 'OmniParser ready', timestamp: '', status: 'completed', duration_ms: 300, metadata: {} },
//   { event_id: 'd6', event_type: 'preset_synced', message: 'Preset synced', timestamp: '', status: 'completed', duration_ms: 1000, metadata: {} },
//   { event_id: 'd7', event_type: 'game_launched', message: 'Game launched', timestamp: '', status: 'completed', duration_ms: 5000, metadata: {} },
//   { event_id: 'd8', event_type: 'step_started', message: 'Step 1: Navigate menu', timestamp: '', status: 'completed', duration_ms: null, metadata: { step_number: 1 } },
//   { event_id: 'd9', event_type: 'step_completed', message: 'Step 1 done', timestamp: '', status: 'completed', duration_ms: 2000, metadata: { step_number: 1 } },
//   { event_id: 'd10', event_type: 'step_started', message: 'Step 2: Click button', timestamp: '', status: 'in_progress', duration_ms: null, metadata: { step_number: 2 } },
//   { event_id: 'd11', event_type: 'step_completed', message: 'Step 2 done', timestamp: '', status: 'pending', duration_ms: null, metadata: { step_number: 2 } },
//   { event_id: 'd12', event_type: 'run_completed', message: 'Run finished', timestamp: '', status: 'pending', duration_ms: null, metadata: {} },
// ];

// Status colors matching RunTimeline
const statusColors: Record<string, { bg: string; border: string; text: string }> = {
  pending: { bg: 'bg-surface-elevated', border: 'border-border', text: 'text-text-muted' },
  in_progress: { bg: 'bg-primary/20', border: 'border-primary', text: 'text-primary' },
  completed: { bg: 'bg-success/20', border: 'border-success', text: 'text-success' },
  failed: { bg: 'bg-danger/20', border: 'border-danger', text: 'text-danger' },
  error: { bg: 'bg-danger/20', border: 'border-danger', text: 'text-danger' },
  skipped: { bg: 'bg-warning/20', border: 'border-warning', text: 'text-warning' },
  warning: { bg: 'bg-warning/20', border: 'border-warning', text: 'text-warning' },
};

// Event icon component - same as RunTimeline
function EventIcon({ status }: { status: string }) {
  const iconClass = "w-3 h-3";

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
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
      </svg>
    );
  }

  // X for failed/error
  if (status === 'failed' || status === 'error') {
    return (
      <svg className={iconClass} fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M6 18L18 6M6 6l12 12" />
      </svg>
    );
  }

  // Warning icon
  if (status === 'warning') {
    return (
      <svg className={iconClass} fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01" />
      </svg>
    );
  }

  // Empty for pending
  return null;
}

// Helper to extract iteration number from event
function extractIterationNumber(event: TimelineEvent): number {
  // Check metadata first
  if (event.metadata?.iteration_number) return event.metadata.iteration_number as number;
  if (event.metadata?.current_iteration) return event.metadata.current_iteration as number;
  // Parse from event_id (e.g., "iteration_1", "iteration_2")
  const match = event.event_id.match(/iteration[_-]?(\d+)/i);
  if (match) return parseInt(match[1], 10);
  // Parse from message (e.g., "Starting iteration 2/3")
  const msgMatch = event.message?.match(/iteration\s*(\d+)/i);
  if (msgMatch) return parseInt(msgMatch[1], 10);
  return 1;
}

// Descriptive label for event - use actual message or meaningful name
function getEventLabel(event: TimelineEvent): string {
  // For iteration events, show iteration number
  if (event.event_type === 'iteration_started') {
    const iterNum = extractIterationNumber(event);
    return `Iter ${iterNum}`;
  }

  // For steps, show step number and brief description
  if (event.event_type.startsWith('step_') && event.metadata?.step_number) {
    const stepNum = event.metadata.step_number;
    const totalSteps = event.metadata.total_steps;
    // Try to extract action from message
    if (event.message) {
      const msg = event.message.toLowerCase();
      if (msg.includes('click')) return `Step ${stepNum}: Click`;
      if (msg.includes('key') || msg.includes('press')) return `Step ${stepNum}: Key`;
      if (msg.includes('wait')) return `Step ${stepNum}: Wait`;
      if (msg.includes('navigate')) return `Step ${stepNum}: Nav`;
    }
    return totalSteps ? `Step ${stepNum}/${totalSteps}` : `Step ${stepNum}`;
  }

  // For info events, try to show meaningful content from message
  if (event.event_type === 'info') {
    if (event.message) {
      // Extract key info from message
      const msg = event.message.toLowerCase();
      if (msg.includes('game ready')) return 'Game Ready';
      if (msg.includes('benchmark')) return 'Benchmark';
      if (msg.includes('screenshot')) return 'Screenshot';
      if (msg.includes('waiting')) return 'Waiting...';
      if (msg.includes('detected')) return 'Detected';
      if (msg.includes('found')) return 'Found';
      // Resolution changes
      if (msg.includes('changing resolution')) return 'Change Res';
      if (msg.includes('resolution changed')) return 'Res Changed';
      if (msg.includes('restoring') && msg.includes('resolution')) return 'Restore Res';
      if (msg.includes('resolution restored')) return 'Res Restored';
      // Steam login
      if (msg.includes('steam') && msg.includes('logging in')) return 'Steam Login';
      if (msg.includes('steam') && msg.includes('login successful')) return 'Steam OK';
      if (msg.includes('already logged')) return 'Steam OK';
      if (msg.includes('need to switch')) return 'Steam: Need to...';
      // Automation
      if (msg.includes('starting automation')) return 'Automation';
      if (msg.includes('automation completed')) return 'Auto Done';
      // Truncate message for display
      return event.message.length > 12 ? event.message.slice(0, 12) + '...' : event.message;
    }
    return 'Info';
  }

  // Use descriptive labels for known event types
  const labels: Record<string, string> = {
    run_started: 'Run Started',
    sut_connecting: 'Connecting SUT',
    sut_connected: 'SUT Connected',
    resolution_detecting: 'Detect Res',
    resolution_detected: 'Resolution OK',
    omniparser_connecting: 'Omni Connect',
    omniparser_connected: 'OmniParser OK',
    preset_syncing: 'Syncing Preset',
    preset_synced: 'Preset Applied',
    preset_skipped: 'Preset Skipped',
    game_launching: 'Launching Game',
    game_launched: 'Game Launched',
    game_process_waiting: 'Waiting Process',
    game_process_detected: 'Process Found',
    steam_dialog_checking: 'Check Dialog',
    steam_dialog_handled: 'Dialog OK',
    steam_dialog_detected: 'Steam Dialog',
    game_ready: 'Game ready',
    warning: 'Warning',
    run_completed: 'Completed',
    run_failed: 'Failed',
  };

  // Use the label map or fall back to the message (truncated)
  if (labels[event.event_type]) {
    return labels[event.event_type];
  }

  // Use message if available, truncated
  if (event.message) {
    return event.message.length > 15 ? event.message.slice(0, 15) + '...' : event.message;
  }

  return event.event_type;
}

// Calculate grid position for snake pattern
function getSnakePosition(index: number, cols: number): { row: number; col: number } {
  const row = Math.floor(index / cols);
  const posInRow = index % cols;
  // Even rows: left-to-right (0,1,2,3,4,5)
  // Odd rows: right-to-left (5,4,3,2,1,0)
  const col = row % 2 === 0 ? posInRow : (cols - 1 - posInRow);
  return { row, col };
}

export function SnakeTimeline({ runId, gameName, pollInterval = 2000, className = '', maxRows }: SnakeTimelineProps) {
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [loading, setLoading] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const [cols, setCols] = useState(6); // Start with safe default
  const [currentIteration, setCurrentIteration] = useState(1);

  const fetchTimeline = useCallback(async () => {
    if (!runId) return;
    try {
      const response = await fetch(`http://localhost:5000/api/runs/${runId}/timeline`);
      if (response.ok) {
        const data = await response.json();
        setEvents(data.events || []);
      }
    } catch (err) {
      console.error('Timeline fetch error:', err);
    } finally {
      setLoading(false);
    }
  }, [runId]);

  useEffect(() => {
    if (!runId) {
      setEvents([]);
      setCurrentIteration(1);
      return;
    }
    setLoading(true);
    fetchTimeline();
    if (pollInterval > 0) {
      const interval = setInterval(fetchTimeline, pollInterval);
      return () => clearInterval(interval);
    }
  }, [runId, pollInterval, fetchTimeline]);

  // Responsive columns - calculate based on actual available width
  // Each cell is CELL_WIDTH (80px) + GAP_X (4px), except last column has no gap after
  useEffect(() => {
    if (!containerRef.current) return;

    const calculateCols = (width: number) => {
      // Account for arrow buttons (32px each side = 64px total)
      const availableWidth = width - 64;
      const cellWidthWithGap = 80 + 4; // CELL_WIDTH + GAP_X
      const maxCols = Math.floor((availableWidth + 4) / cellWidthWithGap);
      return Math.max(4, maxCols);
    };

    // Calculate immediately on mount
    const initialWidth = containerRef.current.getBoundingClientRect().width;
    setCols(calculateCols(initialWidth));

    // Then observe for changes
    const observer = new ResizeObserver(entries => {
      const containerWidth = entries[0]?.contentRect.width || 400;
      setCols(calculateCols(containerWidth));
    });
    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, []);

  // Filter out replaced events (keep latest version)
  const filteredEvents = useMemo(() => {
    return events.filter(event => {
      const isReplaced = events.some(e => e.replaces_event_id === event.event_id);
      return !isReplaced;
    });
  }, [events]);

  // Group events by iteration
  // CRITICAL: Events must be sorted by timestamp first because the backend
  // adds events in the order they arrive, not chronologically!
  const { iterations, totalIterations } = useMemo(() => {
    const iterMap = new Map<number, TimelineEvent[]>();
    let maxIterSeen = 1;

    // Helper to extract iteration number from event
    const getIterNum = (event: TimelineEvent): number | null => {
      // Check metadata first
      if (typeof event.metadata?.iteration_number === 'number') return event.metadata.iteration_number;
      if (typeof event.metadata?.current_iteration === 'number') return event.metadata.current_iteration;
      // Parse from event_id (e.g., "iteration_1", "iteration_2", "iteration_1_done")
      const match = event.event_id.match(/iteration[_-]?(\d+)/i);
      if (match) return parseInt(match[1], 10);
      // Parse from message (e.g., "Starting iteration 2/3", "Iteration 2 completed")
      const msgMatch = event.message?.match(/iteration\s*(\d+)/i);
      if (msgMatch) return parseInt(msgMatch[1], 10);
      return null;
    };

    // Check if event is iteration_started (marks START of iteration)
    const isIterationStart = (event: TimelineEvent): boolean => {
      return event.event_type === 'iteration_started' ||
             (event.event_id.match(/^iteration[_-]?\d+$/i) !== null && !event.event_id.includes('done'));
    };

    // Check if event is iteration_completed (marks END of iteration)
    const isIterationEnd = (event: TimelineEvent): boolean => {
      return event.event_type === 'iteration_completed' ||
             event.event_id.match(/^iteration[_-]?\d+[_-]?done$/i) !== null;
    };

    // SORT events by timestamp before grouping!
    // This is essential because the backend adds events in arrival order, not chronologically
    const sortedEvents = [...filteredEvents].sort((a, b) => {
      const timeA = new Date(a.timestamp).getTime();
      const timeB = new Date(b.timestamp).getTime();
      return timeA - timeB;
    });

    // Track current iteration, update when we see markers
    let currentIter = 1;

    for (const event of sortedEvents) {
      const iterNum = getIterNum(event);

      // iteration_started or iteration_X: this event AND following belong to iterNum
      if (isIterationStart(event) && iterNum) {
        currentIter = iterNum;
        maxIterSeen = Math.max(maxIterSeen, iterNum);
      }
      // iteration_completed or iteration_X_done: this event belongs to iterNum, NEXT events go to iterNum+1
      else if (isIterationEnd(event) && iterNum) {
        // Add this event to the iteration it completes
        if (!iterMap.has(iterNum)) {
          iterMap.set(iterNum, []);
        }
        iterMap.get(iterNum)!.push(event);
        maxIterSeen = Math.max(maxIterSeen, iterNum);
        // Next events go to next iteration
        currentIter = iterNum + 1;
        continue; // Skip the normal add below since we already added
      }

      // Add event to current iteration
      if (!iterMap.has(currentIter)) {
        iterMap.set(currentIter, []);
      }
      iterMap.get(currentIter)!.push(event);
    }

    return {
      iterations: iterMap,
      totalIterations: Math.max(1, iterMap.size, maxIterSeen)
    };
  }, [filteredEvents]);

  // Get events for current iteration view
  const displayEvents = useMemo(() => {
    return iterations.get(currentIteration) || [];
  }, [iterations, currentIteration]);

  // Auto-advance to latest iteration when new events come in
  useEffect(() => {
    if (totalIterations > 0) {
      setCurrentIteration(totalIterations);
    }
  }, [totalIterations]);

  // Calculate grid data with connectors
  const gridData = useMemo(() => {
    const totalRows = Math.ceil(displayEvents.length / cols);

    // Create positioned events
    const positioned = displayEvents.map((event, index) => {
      const { row, col } = getSnakePosition(index, cols);
      return { event, row, col, index };
    });

    // Generate connector segments
    const connectors: Array<{
      type: 'horizontal' | 'vertical' | 'corner';
      row: number;
      col: number;
      direction?: 'down-left' | 'down-right';
    }> = [];

    for (let i = 0; i < displayEvents.length - 1; i++) {
      const curr = getSnakePosition(i, cols);
      const next = getSnakePosition(i + 1, cols);

      if (curr.row === next.row) {
        // Horizontal connector within same row
        const minCol = Math.min(curr.col, next.col);
        connectors.push({ type: 'horizontal', row: curr.row, col: minCol });
      } else {
        // Vertical connector between rows (at row end)
        const isEvenRow = curr.row % 2 === 0;
        connectors.push({
          type: 'corner',
          row: curr.row,
          col: isEvenRow ? cols - 1 : 0,
          direction: isEvenRow ? 'down-left' : 'down-right',
        });
      }
    }

    return { positioned, connectors, totalRows };
  }, [displayEvents, cols]);

  if (!runId) {
    return <div className={`text-center text-text-muted text-xs p-2 ${className}`}>No active run</div>;
  }

  if (loading && events.length === 0) {
    return <div className={`text-center text-text-muted text-xs p-2 animate-pulse ${className}`}>Loading...</div>;
  }

  if (events.length === 0) {
    return <div className={`text-center text-text-muted text-xs p-2 ${className}`}>Waiting for events...</div>;
  }

  const isLive = filteredEvents.some(e => e.status === 'in_progress');
  const CELL_WIDTH = 80; // px
  const CELL_HEIGHT = 70; // px - room for countdown + circle + label

  // Navigation handlers
  const goToPrevIteration = () => setCurrentIteration(prev => Math.max(1, prev - 1));
  const goToNextIteration = () => setCurrentIteration(prev => Math.min(totalIterations, prev + 1));
  const canGoPrev = currentIteration > 1;
  const canGoNext = currentIteration < totalIterations;
  const CIRCLE_SIZE = 26; // px
  const GAP_X = 4; // horizontal gap
  const GAP_Y = 6; // vertical gap

  return (
    <div ref={containerRef} className={`relative ${className}`}>
      {/* Header: Game name + Iteration navigation + Live */}
      <div className="flex items-center justify-between mb-2">
        {/* Left: Game name + Iteration navigation */}
        <div className="flex items-center gap-3">
          {/* Game name */}
          {gameName && (
            <span className="text-sm font-medium text-text-primary">
              {gameName}
            </span>
          )}

          {/* Iteration navigation */}
          <div className="flex items-center gap-1">
            {/* Previous iteration */}
            <button
              onClick={goToPrevIteration}
              disabled={!canGoPrev}
              className={`flex items-center gap-0.5 text-xs transition-colors ${
                canGoPrev
                  ? 'text-text-secondary hover:text-primary cursor-pointer'
                  : 'text-text-muted/30 cursor-not-allowed'
              }`}
              title={canGoPrev ? `Go to iteration ${currentIteration - 1}` : ''}
            >
              {canGoPrev && <span className="font-bold text-warning">#{currentIteration - 1}</span>}
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
            </button>

            {/* Current iteration */}
            <span className="text-xs font-medium text-text-primary px-2 py-0.5 bg-warning/20 rounded-full">
              Iter {currentIteration}
            </span>

            {/* Next iteration */}
            <button
              onClick={goToNextIteration}
              disabled={!canGoNext}
              className={`flex items-center gap-0.5 text-xs transition-colors ${
                canGoNext
                  ? 'text-text-secondary hover:text-primary cursor-pointer'
                  : 'text-text-muted/30 cursor-not-allowed'
              }`}
              title={canGoNext ? `Go to iteration ${currentIteration + 1}` : ''}
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
              {canGoNext && <span className="font-bold text-warning">#{currentIteration + 1}</span>}
            </button>
          </div>
        </div>

        {/* Right: Live indicator */}
        {isLive && (
          <div className="flex items-center gap-1 text-[10px] text-primary">
            <span className="w-1.5 h-1.5 bg-primary rounded-full animate-pulse" />
            Live
          </div>
        )}
      </div>

      {/* Scrollable Grid container - maxRows limits visible rows before scrolling */}
      <div
        className={`relative ${maxRows ? 'overflow-y-auto' : ''} overflow-x-hidden`}
          style={maxRows ? {
            maxHeight: `${maxRows * CELL_HEIGHT + (maxRows - 1) * GAP_Y + 4}px`, // +4px buffer
          } : undefined}
        >
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: `repeat(${cols}, ${CELL_WIDTH}px)`,
              gridTemplateRows: `repeat(${gridData.totalRows}, ${CELL_HEIGHT}px)`,
              gap: `${GAP_Y}px ${GAP_X}px`,
            }}
          >
        {/* SVG layer for connecting lines (behind circles) */}
        <svg
          className="absolute inset-0 pointer-events-none z-0"
          style={{
            width: cols * (CELL_WIDTH + GAP_X) - GAP_X,
            height: gridData.totalRows * (CELL_HEIGHT + GAP_Y) - GAP_Y,
          }}
        >
          {gridData.connectors.map((conn, i) => {
            const cellWidth = CELL_WIDTH + GAP_X;
            const cellHeight = CELL_HEIGHT + GAP_Y;
            const COUNTDOWN_HEIGHT = 16; // h-4 spacer above circle

            // Helper to get correct event index accounting for snake pattern
            // Even rows: left-to-right, Odd rows: right-to-left
            const getEventIndex = (row: number, col: number) => {
              if (row % 2 === 0) {
                return row * cols + col;
              } else {
                // Odd rows: rightmost col is first in row
                return row * cols + (cols - 1 - col);
              }
            };

            if (conn.type === 'horizontal') {
              // Horizontal line between two circles
              const x1 = conn.col * cellWidth + CELL_WIDTH / 2 + CIRCLE_SIZE / 2;
              const x2 = (conn.col + 1) * cellWidth + CELL_WIDTH / 2 - CIRCLE_SIZE / 2;
              const y = conn.row * cellHeight + COUNTDOWN_HEIGHT + CIRCLE_SIZE / 2;

              // Get source event for this connector (the one the line comes FROM)
              // For even rows: source is at conn.col, for odd rows: source is at conn.col + 1
              const sourceCol = conn.row % 2 === 0 ? conn.col : conn.col + 1;
              const eventIndex = getEventIndex(conn.row, sourceCol);
              const event = displayEvents[eventIndex];
              const lineColor = event?.status === 'completed' ? 'var(--color-success)' :
                               event?.status === 'failed' ? 'var(--color-danger)' :
                               event?.status === 'in_progress' ? 'var(--color-primary)' :
                               'var(--color-border)';

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
            } else if (conn.type === 'corner') {
              // Vertical connector between rows
              const isRight = conn.direction === 'down-left';
              const x = isRight
                ? (cols - 1) * cellWidth + CELL_WIDTH / 2
                : CELL_WIDTH / 2;
              const y1 = conn.row * cellHeight + COUNTDOWN_HEIGHT + CIRCLE_SIZE;
              const y2 = (conn.row + 1) * cellHeight + COUNTDOWN_HEIGHT;

              // Get the last event of the current row (source of vertical line)
              // Even rows end at rightmost col, odd rows end at leftmost col
              const lastColInRow = conn.row % 2 === 0 ? cols - 1 : 0;
              const eventIndex = getEventIndex(conn.row, lastColInRow);
              const event = displayEvents[Math.min(eventIndex, displayEvents.length - 1)];
              const lineColor = event?.status === 'completed' ? 'var(--color-success)' :
                               event?.status === 'failed' ? 'var(--color-danger)' :
                               event?.status === 'in_progress' ? 'var(--color-primary)' :
                               'var(--color-border)';

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
            return null;
          })}
        </svg>

        {/* Render circular milestones - same style as RunTimeline */}
        {gridData.positioned.map(({ event, row, col }) => {
          const colors = statusColors[event.status] || statusColors.pending;
          const showCountdown = event.status === 'in_progress';
          const isIteration = event.event_type === 'iteration_started' || event.event_type === 'iteration_completed';
          // Ensure iterNum is always a number (metadata values could be objects)
          const rawIterNum = event.metadata?.iteration_number ?? event.metadata?.current_iteration ?? null;
          const iterNum: number | null = isIteration
            ? (typeof rawIterNum === 'number' ? rawIterNum : extractIterationNumber(event))
            : null;

          return (
            <div
              key={event.event_id}
              className="flex flex-col items-center z-10"
              style={{
                gridColumn: col + 1,
                gridRow: row + 1,
              }}
              title={event.message}
            >
              {/* Top label: Countdown for in_progress, Iteration number for iterations */}
              {showCountdown ? (
                <div className="h-4 flex items-center justify-center mb-0.5">
                  <WaitCounter event={event} />
                </div>
              ) : isIteration && iterNum ? (
                <div className="h-4 flex items-center justify-center mb-0.5">
                  <span className="text-[10px] font-bold text-warning">#{iterNum}</span>
                </div>
              ) : (
                <div className="h-4" /> // Spacer for alignment
              )}

              {/* Circle node - larger for iteration events */}
              <div
                className={`
                  flex items-center justify-center rounded-full border-2 transition-all
                  ${colors.bg} ${colors.border} ${colors.text}
                  ${isIteration ? 'ring-2 ring-warning/30 ring-offset-1 ring-offset-surface' : ''}
                `}
                style={{
                  width: `${isIteration ? CIRCLE_SIZE + 4 : CIRCLE_SIZE}px`,
                  height: `${isIteration ? CIRCLE_SIZE + 4 : CIRCLE_SIZE}px`,
                }}
              >
                {isIteration ? (
                  <span className="text-[10px] font-bold">{iterNum}</span>
                ) : (
                  <EventIcon status={event.status} />
                )}
              </div>

              {/* Label below */}
              <div className="mt-1 text-[10px] text-text-secondary text-center leading-tight w-full truncate px-0.5">
                {isIteration ? 'Iteration' : getEventLabel(event)}
              </div>
            </div>
          );
        })}
          </div>
        </div>
    </div>
  );
}

export default SnakeTimeline;
