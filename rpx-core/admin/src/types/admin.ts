/**
 * Admin Panel TypeScript Types
 * Matches the backend admin_routes.py API structure
 */

// ============================================================================
// Service Configuration Types
// ============================================================================

export interface ServiceSettings {
  host: string;
  port: number;
  enabled: boolean;
  remote: boolean;
  env_vars: Record<string, string>;
}

export interface ServiceWithStatus extends ServiceSettings {
  name?: string;
  status: 'online' | 'offline' | 'disabled' | 'error' | 'timeout' | 'unknown' | 'no_port';
  response_time?: number | null;
  details?: Record<string, unknown> | null;
}

export type ServiceName =
  | 'sut-discovery'
  | 'queue-service'
  | 'rpx-backend'
  | 'rpx-frontend'
  | 'preset-manager'
  | 'pm-frontend'
  | 'sut-client';

// ============================================================================
// Profile Types
// ============================================================================

export interface Profile {
  name: string;
  description: string;
  overrides: Record<string, Partial<ServiceSettings>>;
  is_active?: boolean;
  is_default?: boolean;
}

export interface ProfilesResponse {
  profiles: Profile[];
  active_profile: string;
}

// ============================================================================
// OmniParser Types
// ============================================================================

export interface OmniParserServer {
  name: string;
  url: string;
  enabled: boolean;
}

export interface OmniParserSettings {
  servers: OmniParserServer[];
  instance_count: number;
  omniparser_dir: string;
}

export interface OmniParserTestResult {
  status: 'online' | 'offline' | 'timeout' | 'error';
  response_time?: number;
  details?: Record<string, unknown>;
  error?: string;
}

// ============================================================================
// Steam Account Types
// ============================================================================

export interface SteamAccountPair {
  name: string;
  af_username: string;
  af_password: string;
  gz_username: string;
  gz_password: string;
  enabled: boolean;
}

export interface SteamAccountsResponse {
  pairs: SteamAccountPair[];
  login_timeout: number;
}

// ============================================================================
// Discovery Settings Types
// ============================================================================

export interface DiscoverySettings {
  scan_interval: number;
  timeout: number;
  offline_timeout: number;
  stale_timeout: number;
  udp_port: number;
  paired_interval: number;
  network_ranges: string[];
  manual_targets: string[];
}

// ============================================================================
// Automation Settings Types
// ============================================================================

export interface AutomationSettings {
  startup_wait: number;
  benchmark_duration: number;
  screenshot_interval: number;
  retry_count: number;
  step_timeout: number;
  process_detection_timeout: number;
}

// ============================================================================
// Game Configuration Types
// ============================================================================

export interface GameListItem {
  filename: string;
  name: string;
  game_name: string;
  steam_app_id?: string;
  preset_id?: string;
  display_name?: string;
  error?: string;
}

export interface GamesListResponse {
  games: GameListItem[];
  count: number;
}

export interface GameYamlResponse {
  name: string;
  filename: string;
  content: string;
  path: string;
}

export interface YamlValidationResult {
  valid: boolean;
  error?: string;
  line?: number | null;
  warnings?: string[];
  parsed_keys?: string[] | null;
}

// ============================================================================
// Tracing Configuration Types
// ============================================================================

export interface TracingAgent {
  enabled: boolean;
  description: string;
  path: string;
  args: string[];
  duration_arg: string;
  duration_style: string;
  output_arg: string;
  output_style: string;
  has_duration: boolean;
  output_filename_only?: boolean;
}

export interface TracingConfig {
  output_dir: string;
  post_trace_buffer: number;
  ssh: {
    timeout: number;
    max_retries: number;
    retry_delay: number;
    user: string;
  };
  agents: Record<string, TracingAgent>;
}

// ============================================================================
// Full Configuration Type
// ============================================================================

export interface AdminConfig {
  version: string;
  project_dir: string;
  omniparser_dir: string;
  services: Record<ServiceName, ServiceSettings>;
  profiles: Record<string, Omit<Profile, 'name'>>;
  active_profile: string;
  omniparser_servers: OmniParserServer[];
  omniparser_instance_count: number;
  steam_account_pairs: SteamAccountPair[];
  steam_login_timeout: number;
  discovery_settings: DiscoverySettings;
  automation_settings: AutomationSettings;
}

// ============================================================================
// API Response Types
// ============================================================================

export interface ApiResponse {
  status: 'ok' | 'error';
  message?: string;
  error?: string;
}

export interface ApiResponseWithRestart extends ApiResponse {
  restart_required?: boolean;
}

export interface ServiceRestartResponse extends ApiResponse {
  note?: string;
}

export interface GameCreateResponse extends ApiResponse {
  name?: string;
  filename?: string;
}

export interface GameDeleteResponse extends ApiResponse {
  backup?: string;
}

export interface GameUpdateResponse extends ApiResponse {
  backup?: string | null;
}

// ============================================================================
// Tab Types
// ============================================================================

export type AdminTab =
  | 'services'
  | 'omniparser'
  | 'discovery'
  | 'games'
  | 'automation'
  | 'steam'
  | 'profiles'
  | 'branding'
  | 'tracing';

export interface TabDefinition {
  id: AdminTab;
  label: string;
  icon?: string;
  description?: string;
}

// ============================================================================
// UI State Types
// ============================================================================

export interface UnsavedChanges {
  services?: boolean;
  omniparser?: boolean;
  discovery?: boolean;
  games?: boolean;
  automation?: boolean;
  steam?: boolean;
  profiles?: boolean;
  branding?: boolean;
  tracing?: boolean;
}

export interface ToastMessage {
  id: string;
  type: 'success' | 'error' | 'warning' | 'info';
  title: string;
  message?: string;
  duration?: number;
}
