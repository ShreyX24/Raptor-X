import { useEffect, useRef, useState, useCallback } from 'react';
import { io, Socket } from 'socket.io-client';

// Event types from backend websocket_handler.py
export interface AutomationEvent {
  event: 'automation_started' | 'automation_completed' | 'automation_failed';
  data: {
    run_id: string;
    game_name?: string;
    sut_ip?: string;
    status?: string;
    [key: string]: unknown;
  };
  timestamp: string;
}

export interface StepEvent {
  event: 'step_started' | 'step_completed' | 'step_failed';
  run_id: string;
  step: {
    step_number: number;
    description?: string;
    status?: string;
    [key: string]: unknown;
  };
  timestamp: string;
}

export interface ProgressEvent {
  event: 'progress_update';
  run_id: string;
  progress: {
    current_iteration?: number;
    current_step?: number;
    [key: string]: unknown;
  };
  timestamp: string;
}

export interface DeviceEvent {
  event: 'device_discovered' | 'device_online' | 'device_offline' | 'device_status_changed';
  device: Record<string, unknown>;
  timestamp: string;
}

export interface CampaignEvent {
  event: 'campaign_created' | 'campaign_progress' | 'campaign_completed' | 'campaign_failed';
  data: {
    campaign_id: string;
    campaign: Record<string, unknown>;
    [key: string]: unknown;
  };
  timestamp: string;
}

// Timeline events from TimelineManager via automation_orchestrator
// Note: This matches the TimelineEvent interface in RunTimeline.tsx
export interface TimelineEvent {
  run_id: string;
  event_id: string;
  event_type: string;
  message: string;
  status: 'pending' | 'in_progress' | 'completed' | 'failed' | 'skipped' | 'warning' | 'error';
  timestamp: string;
  duration_ms?: number | null;
  metadata?: Record<string, unknown>;
  replaces_event_id?: string | null;
  group?: string | null;
}

type EventCallback<T> = (data: T) => void;

interface UseWebSocketOptions {
  autoConnect?: boolean;
  reconnectionAttempts?: number;
  reconnectionDelay?: number;
}

export function useWebSocket(options: UseWebSocketOptions = {}) {
  const {
    autoConnect = true,
    reconnectionAttempts = 5,
    reconnectionDelay = 2000,
  } = options;

  const [isConnected, setIsConnected] = useState(false);
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const socketRef = useRef<Socket | null>(null);

  // Event listeners stored in refs to avoid recreation
  const automationListeners = useRef<Set<EventCallback<AutomationEvent>>>(new Set());
  const stepListeners = useRef<Set<EventCallback<StepEvent>>>(new Set());
  const progressListeners = useRef<Set<EventCallback<ProgressEvent>>>(new Set());
  const deviceListeners = useRef<Set<EventCallback<DeviceEvent>>>(new Set());
  const campaignListeners = useRef<Set<EventCallback<CampaignEvent>>>(new Set());
  const timelineListeners = useRef<Set<EventCallback<TimelineEvent>>>(new Set());

  // Initialize socket connection
  useEffect(() => {
    if (!autoConnect) return;

    // Connect to the same origin as the page (Vite proxy will handle it)
    // Use polling first - WebSocket through Vite proxy causes 500 errors
    const socket = io({
      path: '/socket.io/',
      transports: ['polling', 'websocket'],
      reconnectionAttempts,
      reconnectionDelay,
      autoConnect: true,
      upgrade: false,  // Don't upgrade from polling to websocket (avoids proxy issues)
    });

    socketRef.current = socket;

    socket.on('connect', () => {
      setIsConnected(true);
      setConnectionError(null);
    });

    socket.on('disconnect', () => {
      setIsConnected(false);
    });

    socket.on('connect_error', (error) => {
      console.error('[WebSocket] Connection error:', error.message);
      setConnectionError(error.message);
      setIsConnected(false);
    });

    // Automation events (run started/completed/failed)
    socket.on('automation_event', (data: AutomationEvent) => {
      automationListeners.current.forEach((callback) => callback(data));
    });

    // Step events
    socket.on('automation_step', (data: StepEvent) => {
      stepListeners.current.forEach((callback) => callback(data));
    });

    // Progress events
    socket.on('automation_progress', (data: ProgressEvent) => {
      progressListeners.current.forEach((callback) => callback(data));
    });

    // Device events
    socket.on('device_event', (data: DeviceEvent) => {
      deviceListeners.current.forEach((callback) => callback(data));
    });

    // Campaign events
    socket.on('campaign_event', (data: CampaignEvent) => {
      campaignListeners.current.forEach((callback) => callback(data));
    });

    // Timeline events (detailed events from TimelineManager for real-time updates)
    socket.on('timeline_event', (data: TimelineEvent) => {
      timelineListeners.current.forEach((callback) => callback(data));
    });

    // Connection status from server (silently acknowledge)
    socket.on('connection_status', (_data: { status: string; client_id: string }) => {
      // Connection confirmed - no need to log
    });

    return () => {
      socket.disconnect();
      socketRef.current = null;
    };
  }, [autoConnect, reconnectionAttempts, reconnectionDelay]);

  // Subscribe to automation events
  const onAutomationEvent = useCallback((callback: EventCallback<AutomationEvent>) => {
    automationListeners.current.add(callback);
    return () => {
      automationListeners.current.delete(callback);
    };
  }, []);

  // Subscribe to step events
  const onStepEvent = useCallback((callback: EventCallback<StepEvent>) => {
    stepListeners.current.add(callback);
    return () => {
      stepListeners.current.delete(callback);
    };
  }, []);

  // Subscribe to progress events
  const onProgressEvent = useCallback((callback: EventCallback<ProgressEvent>) => {
    progressListeners.current.add(callback);
    return () => {
      progressListeners.current.delete(callback);
    };
  }, []);

  // Subscribe to device events
  const onDeviceEvent = useCallback((callback: EventCallback<DeviceEvent>) => {
    deviceListeners.current.add(callback);
    return () => {
      deviceListeners.current.delete(callback);
    };
  }, []);

  // Subscribe to campaign events
  const onCampaignEvent = useCallback((callback: EventCallback<CampaignEvent>) => {
    campaignListeners.current.add(callback);
    return () => {
      campaignListeners.current.delete(callback);
    };
  }, []);

  // Subscribe to timeline events (real-time updates from TimelineManager)
  const onTimelineEvent = useCallback((callback: EventCallback<TimelineEvent>) => {
    timelineListeners.current.add(callback);
    return () => {
      timelineListeners.current.delete(callback);
    };
  }, []);

  // Subscribe to a specific run's updates
  const subscribeToRun = useCallback((runId: string) => {
    socketRef.current?.emit('subscribe_to_run', { run_id: runId });
  }, []);

  // Unsubscribe from a specific run
  const unsubscribeFromRun = useCallback((runId: string) => {
    socketRef.current?.emit('unsubscribe_from_run', { run_id: runId });
  }, []);

  // Manually connect
  const connect = useCallback(() => {
    socketRef.current?.connect();
  }, []);

  // Manually disconnect
  const disconnect = useCallback(() => {
    socketRef.current?.disconnect();
  }, []);

  return {
    isConnected,
    connectionError,
    // Event subscriptions
    onAutomationEvent,
    onStepEvent,
    onProgressEvent,
    onDeviceEvent,
    onCampaignEvent,
    onTimelineEvent,
    // Run-specific subscriptions
    subscribeToRun,
    unsubscribeFromRun,
    // Manual control
    connect,
    disconnect,
  };
}
