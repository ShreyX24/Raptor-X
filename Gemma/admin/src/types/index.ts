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
  // Extended properties for dashboard
  path?: string;           // Installation path on SUT
  preset_id?: string;      // Preset manager game slug
  steam_app_id?: string;   // Steam app ID for matching
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
export type StepStatus = 'pending' | 'in_progress' | 'completed' | 'failed' | 'skipped';

export interface StepProgress {
  step_number: number;
  description: string;
  status: StepStatus;
  started_at: string | null;
  completed_at: string | null;
  screenshot_url: string | null;
  error_message: string | null;
  is_optional: boolean;
}

export interface RunProgress {
  current_iteration: number;
  current_step: number;
  total_iterations: number;
  total_steps: number;
  steps?: StepProgress[];
}

// SUT hardware/system info (from manifest or live fetch)
export interface SUTSystemInfo {
  cpu: { brand_string: string };
  gpu: { name: string };
  ram: { total_gb: number };
  os: { name: string; version: string; release: string; build: string };
  bios: { name: string; version: string };
  screen: { width: number; height: number };
  hostname: string;
  device_id: string;
}

export interface AutomationRun {
  run_id: string;
  game_name: string;
  sut_ip: string;
  sut_device_id: string;
  status: 'queued' | 'running' | 'completed' | 'failed' | 'cancelled';
  iterations: number;
  current_iteration: number;
  progress: number | RunProgress;  // Can be number (0-100) or detailed object
  started_at: string | null;
  completed_at: string | null;
  error_message: string | null;
  logs: LogEntry[];
  sut_info?: SUTSystemInfo | null;  // Embedded SUT metadata from manifest
  folder_name?: string | null;  // Run folder name for logs/artifacts
  campaign_id?: string | null;  // Links to parent campaign if part of one
  campaign_name?: string | null;  // Campaign name for grouping display
  quality?: string | null;  // 'low' | 'medium' | 'high' | 'ultra'
  resolution?: string | null;  // '720p' | '1080p' | '1440p' | '2160p'
}

// Campaign types
export type CampaignStatus = 'queued' | 'running' | 'completed' | 'failed' | 'partially_completed' | 'stopped';

export interface CampaignProgress {
  total_games: number;
  completed_games: number;
  failed_games: number;
  current_game: string | null;
  current_game_index: number;
}

export interface Campaign {
  campaign_id: string;
  name: string;
  sut_ip: string;
  sut_device_id: string;
  games: string[];
  iterations_per_game: number;
  status: CampaignStatus;
  run_ids: string[];
  progress: CampaignProgress;
  created_at: string;
  completed_at: string | null;
  error_message: string | null;
  runs?: AutomationRun[];  // Populated when fetching single campaign
  quality?: string | null;  // 'low' | 'medium' | 'high' | 'ultra'
  resolution?: string | null;  // '720p' | '1080p' | '1440p' | '2160p'
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

export interface PaginationInfo {
  page: number;
  per_page: number;
  total: number;
  total_pages: number;
  has_more: boolean;
}

export interface RunsResponse {
  active: Record<string, AutomationRun>;
  history: AutomationRun[];
  pagination?: PaginationInfo;
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
  | 'error_notification'
  | 'automation_step'
  | 'automation_progress';

// Automation step event types
export interface AutomationStepEvent {
  event: 'step_started' | 'step_completed' | 'step_failed';
  run_id: string;
  step: StepProgress;
  timestamp: string;
}

export interface AutomationProgressEvent {
  event: 'progress_update';
  run_id: string;
  progress: RunProgress;
  timestamp: string;
}

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

// ============================================
// Queue Service Types
// ============================================

export interface QueueStats {
  total_requests: number;
  successful_requests: number;
  failed_requests: number;
  timeout_requests: number;
  current_queue_size: number;
  worker_running: boolean;
  avg_processing_time: number;
  avg_queue_wait_time: number;
  requests_per_minute: number;
  uptime_seconds: number;
}

export interface QueueJob {
  job_id: string;
  timestamp: string;
  status: 'success' | 'failed' | 'timeout';
  processing_time: number;
  queue_wait_time: number;
  image_size: number;
  error?: string;
}

export interface QueueDepthPoint {
  timestamp: string;
  depth: number;
}

export interface QueueHealth {
  status: 'healthy' | 'degraded' | 'unhealthy';
  worker_running: boolean;
  queue_size: number;
  uptime_seconds: number;
  omniparser_status?: 'online' | 'offline' | 'error';
  version?: string;
  omniparser_url?: string;
}

// ============================================
// Preset Manager Types
// ============================================

export interface PresetGame {
  short_name: string;
  name: string;
  version?: string;
  description?: string;
  default_level?: string;
  available_levels: string[];
  preset_count: number;
  steam_app_id?: string;
  enabled: boolean;
}

export interface PresetLevel {
  level: string;
  description?: string;
  target_gpu?: string;
  resolution?: string;
  target_fps?: number;
  version?: string;
  file_count: number;
}

export interface PresetFile {
  filename: string;
  size: number;
  hash: string;
  modified: string;
}

export interface SyncStats {
  total_games: number;
  total_presets: number;
  total_suts: number;
  online_suts: number;
  sync_manager_ready: boolean;
}

export interface SyncResult {
  game: string;
  level: string;
  sut_count: number;
  status: 'success' | 'partial' | 'failed';
  message: string;
  results?: Array<{
    sut_id: string;
    success: boolean;
    error?: string;
  }>;
}

export interface BackupInfo {
  backup_id: string;
  game_slug: string;
  created_at: string;
  file_count: number;
  total_size: number;
}

// ============================================
// Workflow Builder Types
// ============================================

export interface BoundingBox {
  x: number;
  y: number;
  width: number;
  height: number;
  element_type: 'icon' | 'text';
  element_text: string;
  confidence?: number;
}

export interface ParsedScreenshot {
  elements: BoundingBox[];
  annotated_image_base64?: string;
  element_count: number;
  processing_time: number;
}

export interface WorkflowStep {
  step_number: number;
  description: string;
  action_type: 'find_and_click' | 'right_click' | 'double_click' | 'middle_click'
             | 'key' | 'hotkey' | 'text' | 'drag' | 'scroll' | 'wait'
             | 'hold_key' | 'hold_click';
  find?: {
    type: 'icon' | 'text' | 'any';
    text: string;
    text_match: 'contains' | 'exact' | 'startswith' | 'endswith';
  };
  action?: {
    type: string;
    button?: 'left' | 'right' | 'middle';
    key?: string;
    keys?: string[];
    text?: string;
    duration?: number;
    clicks?: number;
    direction?: 'up' | 'down';
    dest_x?: number;
    dest_y?: number;
    move_duration?: number;
    click_delay?: number;
    clear_first?: boolean;
    char_delay?: number;
  };
  verify_success?: Array<{
    type: 'icon' | 'text' | 'any';
    text: string;
    text_match: 'contains' | 'exact' | 'startswith' | 'endswith';
  }>;
  expected_delay: number;
  timeout: number;
  optional?: boolean;
  // Per-step OCR config (overrides workflow-level defaults)
  ocr_config?: {
    use_paddleocr?: boolean;
    text_threshold?: number;
    box_threshold?: number;
  };
}

export interface Workflow {
  game_name: string;
  game_path?: string;
  process_name?: string;
  version?: string;
  benchmark_duration?: number;
  startup_wait?: number;
  resolution?: string;
  preset?: string;
  steps: WorkflowStep[];
}

export interface ActionResult {
  success: boolean;
  message: string;
  response_time?: number;
  error?: string;
}

export interface PerformanceMetrics {
  cpu_usage: number;
  ram_usage: number;
  gpu_usage?: number;
  cpu_temp?: number;
  gpu_temp?: number;
}

// ============================================
// Display Resolution Types
// ============================================

export interface SutDisplayResolution {
  width: number;
  height: number;
  name?: string;  // e.g., "1080p", "4K"
}

export interface SutDisplayResolutionsResponse {
  status: string;
  resolutions: SutDisplayResolution[];
  device_id: string;
}

// Quality and Resolution presets
export type QualityLevel = 'low' | 'medium' | 'high' | 'ultra';
export type ResolutionPreset = '720p' | '1080p' | '1440p' | '2160p';

// ============================================
// Service Health Types (for dashboard)
// ============================================

export interface ServiceHealthStatus {
  name: string;
  displayName: string;
  status: 'online' | 'offline' | 'error' | 'starting';
  url: string;
  port: number;
  details?: Record<string, unknown>;
  lastChecked: string;
  onlineSuts?: number;
}

export interface AllServicesHealth {
  gemmaBackend: ServiceHealthStatus;
  discoveryService: ServiceHealthStatus;
  queueService: ServiceHealthStatus & { queueDepth?: number };
  presetManager: ServiceHealthStatus;
  omniparserInstances: Array<ServiceHealthStatus & {
    instanceId: number;
    enabled: boolean;
  }>;
}

// ============================================
// Admin Panel Types (re-export)
// ============================================

export * from './admin';
