export { SUTCard } from './SUTCard';
export { GameCard } from './GameCard';
export { RunCard } from './RunCard';
export { StatusBadge } from './StatusBadge';
export { ServiceStatus } from './ServiceStatus';
export { LogViewer } from './LogViewer';
export { ErrorBoundary } from './ErrorBoundary';

// New components for enhanced dashboard
export { MetricCard, MetricGrid } from './MetricCard';
export { ServiceHealthPanel, ServiceHealthBar } from './ServiceHealthPanel';
export { SparklineChart, QueueDepthChart } from './SparklineChart';
export { DataTable, JobHistoryTable, StatusDot } from './DataTable';
export { RecentRunsTable } from './RecentRunsTable';

// Pre-automation telemetry components (Phase 1)
export { PresetMatrix, PresetSelector, QUALITY_LEVELS, RESOLUTIONS } from './PresetMatrix';
export type { QualityLevel, Resolution, PresetAvailability } from './PresetMatrix';
export { PreflightChecks, CheckIndicator } from './PreflightChecks';
export type { PreflightCheck, CheckStatus } from './PreflightChecks';
export { SUTDetailPanel } from './SUTDetailPanel';

// Automation timeline components (Phase 2)
export { AutomationTimeline, StepIndicator, StepDetailPopover, TimelineStep } from './AutomationTimeline';
export { RunTimeline, TimelineNode, EventDetailPanel, EventIcon } from './RunTimeline';
export type { TimelineEvent } from './RunTimeline';

// Campaign components
export { CampaignModal } from './CampaignModal';

// Data-dense dashboard components (Unified Dashboard)
export { RadialGauge, MiniGauge } from './RadialGauge';
export { CollapsiblePanel, Panel } from './CollapsiblePanel';
export { FleetStatusPanel, CompactSutCard } from './FleetStatusPanel';
export { GameLibraryPanel, GameListItem } from './GameLibraryPanel';
export { QuickLaunchPanel } from './QuickLaunchPanel';
export { ActiveRunsPanel, MiniRunIndicator } from './ActiveRunsPanel';
export { RunMetricsPanel, CompactMetricsRow } from './RunMetricsPanel';
export { SnakeTimeline } from './SnakeTimeline';
