// SUT (System Under Test) types
export interface SUT {
  device_id: string;
  ip: string;
  port: number;
  hostname: string;
  status: 'online' | 'offline' | 'busy' | 'error';
  capabilities: Record<string, unknown>;
  last_seen: string | null;
  first_discovered: string | null;
  current_task: string | null;
  error_count: number;
  success_rate: number;
  is_paired?: boolean;
  paired_at?: string | null;
  paired_by?: string | null;
}

// Game configuration types
export interface GameConfig {
  name: string;
  display_name: string;
  executable_path: string;
  process_name: string;
  launch_delay: number;
  settings_menu_path: string[];
  automation_steps: AutomationStep[];
  presets?: Preset[];
}

export interface AutomationStep {
  type: 'click' | 'key' | 'wait' | 'screenshot' | 'analyze';
  target?: string;
  value?: string | number;
  delay?: number;
}

export interface Preset {
  id: string;
  name: string;
  game_id: string;
  settings: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

// Automation run types
export interface AutomationRun {
  run_id: string;
  game_name: string;
  sut_ip: string;
  sut_device_id: string;
  status: 'queued' | 'running' | 'completed' | 'failed' | 'cancelled';
  iterations: number;
  current_iteration: number;
  progress: number;
  started_at: string | null;
  completed_at: string | null;
  error_message: string | null;
  logs: LogEntry[];
}

export interface LogEntry {
  timestamp: string;
  level: 'info' | 'warning' | 'error' | 'debug';
  message: string;
}

// System status types
export interface SystemStatus {
  backend: {
    running: boolean;
    version: string;
    mode: 'external_services' | 'internal_discovery';
    uptime: number;
    websocket_clients: number;
  };
  discovery: {
    running: boolean;
    external?: boolean;
    target_ips?: number;
  };
  devices: {
    total_devices: number;
    online_devices: number;
    offline_devices: number;
    paired_devices: number;
  };
  omniparser: {
    status: 'online' | 'offline' | 'error' | 'unknown';
    url: string;
    queue_size?: number;
  };
  services?: {
    discovery_service: ServiceStatus;
    queue_service: ServiceStatus;
    preset_manager: ServiceStatus;
  };
}

export interface ServiceStatus {
  url: string;
  available: boolean;
}

// API response types
export interface DevicesResponse {
  devices: SUT[];
  total_count: number;
  online_count: number;
  source: 'discovery_service' | 'internal_registry';
}

export interface GamesResponse {
  games: Record<string, GameConfig>;
}

export interface RunsResponse {
  active: Record<string, AutomationRun>;
  history: AutomationRun[];
}

export interface RunsStats {
  active_runs: number;
  queued_runs: number;
  total_history: number;
  completed_runs: number;
  failed_runs: number;
}

// WebSocket event types
export type WebSocketEventType =
  | 'system_status'
  | 'devices_update'
  | 'paired_suts_update'
  | 'runs_update'
  | 'run_started'
  | 'run_progress'
  | 'run_completed'
  | 'run_failed'
  | 'games_update'
  | 'error_notification';

export interface WebSocketMessage<T = unknown> {
  type: WebSocketEventType;
  data: T;
}

export interface ErrorNotification {
  type: string;
  title: string;
  message: string;
  run_id?: string;
  game_name?: string;
  sut_ip?: string;
  timestamp: string;
}
