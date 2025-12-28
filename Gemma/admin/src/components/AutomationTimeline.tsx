import { useState, useMemo } from 'react';
import type { StepProgress, StepStatus } from '../types';

// ============================================
// Step Status Indicator Component
// ============================================

interface StepIndicatorProps {
  status: StepStatus;
  stepNumber: number;
  isActive?: boolean;
}

function StepIndicator({ status, stepNumber, isActive }: StepIndicatorProps) {
  const statusConfig: Record<StepStatus, { bg: string; border: string; icon: React.ReactNode }> = {
    pending: {
      bg: 'bg-surface-elevated',
      border: 'border-border',
      icon: <span className="text-xs text-text-muted">{stepNumber}</span>,
    },
    in_progress: {
      bg: 'bg-primary/20',
      border: 'border-primary',
      icon: (
        <svg className="w-4 h-4 text-primary animate-spin" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
        </svg>
      ),
    },
    completed: {
      bg: 'bg-success/20',
      border: 'border-success',
      icon: (
        <svg className="w-4 h-4 text-success" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
        </svg>
      ),
    },
    failed: {
      bg: 'bg-danger/20',
      border: 'border-danger',
      icon: (
        <svg className="w-4 h-4 text-danger" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
        </svg>
      ),
    },
    skipped: {
      bg: 'bg-warning/20',
      border: 'border-warning',
      icon: (
        <svg className="w-4 h-4 text-warning" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 5l7 7-7 7M5 5l7 7-7 7" />
        </svg>
      ),
    },
  };

  const config = statusConfig[status];

  return (
    <div
      className={`
        w-8 h-8 rounded-full flex items-center justify-center border-2 transition-all
        ${config.bg} ${config.border}
        ${isActive ? 'ring-2 ring-primary/50 ring-offset-2 ring-offset-surface' : ''}
      `}
    >
      {config.icon}
    </div>
  );
}

// ============================================
// Step Detail Popover Component
// ============================================

interface StepDetailPopoverProps {
  step: StepProgress;
  position: 'top' | 'bottom';
}

function StepDetailPopover({ step, position }: StepDetailPopoverProps) {
  const formatTime = (isoString: string | null) => {
    if (!isoString) return '-';
    return new Date(isoString).toLocaleTimeString();
  };

  const getDuration = () => {
    if (!step.started_at) return null;
    const start = new Date(step.started_at);
    const end = step.completed_at ? new Date(step.completed_at) : new Date();
    const seconds = Math.round((end.getTime() - start.getTime()) / 1000);
    if (seconds < 60) return `${seconds}s`;
    const minutes = Math.floor(seconds / 60);
    return `${minutes}m ${seconds % 60}s`;
  };

  const statusLabels: Record<StepStatus, string> = {
    pending: 'Pending',
    in_progress: 'In Progress',
    completed: 'Completed',
    failed: 'Failed',
    skipped: 'Skipped',
  };

  const statusColors: Record<StepStatus, string> = {
    pending: 'text-text-muted',
    in_progress: 'text-primary',
    completed: 'text-success',
    failed: 'text-danger',
    skipped: 'text-warning',
  };

  return (
    <div
      className={`
        absolute z-50 w-64 p-3 rounded-lg bg-surface-elevated border border-border shadow-xl
        ${position === 'top' ? 'bottom-full mb-2' : 'top-full mt-2'}
        left-1/2 -translate-x-1/2
      `}
    >
      {/* Arrow */}
      <div
        className={`
          absolute left-1/2 -translate-x-1/2 w-3 h-3 bg-surface-elevated border-border rotate-45
          ${position === 'top' ? 'bottom-0 translate-y-1/2 border-r border-b' : 'top-0 -translate-y-1/2 border-l border-t'}
        `}
      />

      <div className="relative">
        {/* Step Header */}
        <div className="flex items-start justify-between mb-2">
          <span className="text-xs font-medium text-text-muted">Step {step.step_number}</span>
          <span className={`text-xs font-medium ${statusColors[step.status]}`}>
            {statusLabels[step.status]}
            {step.is_optional && ' (optional)'}
          </span>
        </div>

        {/* Description */}
        <p className="text-sm text-text-primary mb-3 line-clamp-2">{step.description}</p>

        {/* Timing Info */}
        <div className="space-y-1 text-xs">
          {step.started_at && (
            <div className="flex justify-between">
              <span className="text-text-muted">Started:</span>
              <span className="text-text-secondary font-mono">{formatTime(step.started_at)}</span>
            </div>
          )}
          {step.completed_at && (
            <div className="flex justify-between">
              <span className="text-text-muted">Completed:</span>
              <span className="text-text-secondary font-mono">{formatTime(step.completed_at)}</span>
            </div>
          )}
          {getDuration() && (
            <div className="flex justify-between">
              <span className="text-text-muted">Duration:</span>
              <span className="text-text-secondary font-mono">{getDuration()}</span>
            </div>
          )}
        </div>

        {/* Error Message */}
        {step.error_message && (
          <div className="mt-2 p-2 rounded bg-danger/10 border border-danger/30 text-xs text-danger">
            {step.error_message}
          </div>
        )}

        {/* Screenshot Link */}
        {step.screenshot_url && (
          <a
            href={step.screenshot_url}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-2 flex items-center gap-1 text-xs text-primary hover:underline"
          >
            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
            View Screenshot
          </a>
        )}
      </div>
    </div>
  );
}

// ============================================
// Timeline Step Component
// ============================================

interface TimelineStepProps {
  step: StepProgress;
  isFirst: boolean;
  isLast: boolean;
  isActive: boolean;
}

function TimelineStep({ step, isFirst, isLast, isActive }: TimelineStepProps) {
  const [showPopover, setShowPopover] = useState(false);

  // Determine connector line color based on previous step's status
  const getConnectorColor = () => {
    if (step.status === 'completed') return 'bg-success';
    if (step.status === 'in_progress') return 'bg-gradient-to-r from-success to-primary';
    if (step.status === 'failed') return 'bg-gradient-to-r from-success to-danger';
    if (step.status === 'skipped') return 'bg-gradient-to-r from-success to-warning';
    return 'bg-border';
  };

  return (
    <div
      className="relative flex flex-col items-center"
      onMouseEnter={() => setShowPopover(true)}
      onMouseLeave={() => setShowPopover(false)}
    >
      {/* Connector Line (before) */}
      {!isFirst && (
        <div
          className={`absolute right-1/2 top-4 h-0.5 w-full ${getConnectorColor()}`}
          style={{ transform: 'translateX(-50%)' }}
        />
      )}

      {/* Step Indicator */}
      <div className="relative z-10">
        <StepIndicator
          status={step.status}
          stepNumber={step.step_number}
          isActive={isActive}
        />
      </div>

      {/* Connector Line (after) */}
      {!isLast && (
        <div
          className={`absolute left-1/2 top-4 h-0.5 w-full ${
            step.status === 'completed' ? 'bg-success' : 'bg-border'
          }`}
          style={{ transform: 'translateX(50%)' }}
        />
      )}

      {/* Step Label (truncated) */}
      <div className="mt-2 w-20 text-center">
        <p className="text-xs text-text-muted truncate" title={step.description}>
          {step.description.length > 15
            ? step.description.substring(0, 15) + '...'
            : step.description}
        </p>
      </div>

      {/* Popover */}
      {showPopover && (
        <StepDetailPopover step={step} position="bottom" />
      )}
    </div>
  );
}

// ============================================
// Main AutomationTimeline Component
// ============================================

interface AutomationTimelineProps {
  steps: StepProgress[];
  currentStep?: number;
  compact?: boolean;
}

export function AutomationTimeline({ steps, currentStep, compact = false }: AutomationTimelineProps) {
  // Calculate summary stats
  const stats = useMemo(() => {
    const completed = steps.filter(s => s.status === 'completed').length;
    const failed = steps.filter(s => s.status === 'failed').length;
    const skipped = steps.filter(s => s.status === 'skipped').length;
    const inProgress = steps.filter(s => s.status === 'in_progress').length;
    const pending = steps.filter(s => s.status === 'pending').length;
    return { completed, failed, skipped, inProgress, pending, total: steps.length };
  }, [steps]);

  if (steps.length === 0) {
    return (
      <div className="text-center text-text-muted text-sm py-4">
        No step data available
      </div>
    );
  }

  // For compact mode, show a simplified view
  if (compact) {
    return (
      <div className="flex items-center gap-2">
        {steps.map((step, index) => (
          <div
            key={step.step_number}
            className="group relative"
          >
            <div
              className={`
                w-2.5 h-2.5 rounded-full transition-transform group-hover:scale-125
                ${step.status === 'completed' ? 'bg-success' :
                  step.status === 'in_progress' ? 'bg-primary animate-pulse' :
                  step.status === 'failed' ? 'bg-danger' :
                  step.status === 'skipped' ? 'bg-warning' :
                  'bg-border'}
              `}
            />
            {/* Connector */}
            {index < steps.length - 1 && (
              <div
                className={`absolute top-1/2 left-full w-2 h-0.5 -translate-y-1/2
                  ${step.status === 'completed' ? 'bg-success' : 'bg-border'}
                `}
              />
            )}
          </div>
        ))}
        <span className="text-xs text-text-muted ml-2">
          {stats.completed}/{stats.total}
        </span>
      </div>
    );
  }

  return (
    <div className="w-full">
      {/* Summary Bar */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-4 text-xs">
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-success" />
            <span className="text-text-muted">Completed: {stats.completed}</span>
          </span>
          {stats.failed > 0 && (
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-danger" />
              <span className="text-text-muted">Failed: {stats.failed}</span>
            </span>
          )}
          {stats.skipped > 0 && (
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-warning" />
              <span className="text-text-muted">Skipped: {stats.skipped}</span>
            </span>
          )}
          {stats.inProgress > 0 && (
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-primary animate-pulse" />
              <span className="text-text-muted">Running: {stats.inProgress}</span>
            </span>
          )}
        </div>
        <span className="text-xs text-text-secondary font-mono">
          {stats.completed + stats.failed + stats.skipped}/{stats.total} steps
        </span>
      </div>

      {/* Timeline */}
      <div className="relative">
        {/* Background track */}
        <div className="absolute top-4 left-4 right-4 h-0.5 bg-border" />

        {/* Progress track */}
        <div
          className="absolute top-4 left-4 h-0.5 bg-success transition-all duration-300"
          style={{
            width: `${Math.max(0, ((stats.completed + stats.failed + stats.skipped) / Math.max(1, stats.total - 1)) * 100)}%`,
            maxWidth: 'calc(100% - 32px)',
          }}
        />

        {/* Steps */}
        <div className="relative flex justify-between px-0">
          {steps.map((step, index) => (
            <TimelineStep
              key={step.step_number}
              step={step}
              isFirst={index === 0}
              isLast={index === steps.length - 1}
              isActive={step.step_number === currentStep}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

// Export sub-components for flexibility
export { StepIndicator, StepDetailPopover, TimelineStep };
