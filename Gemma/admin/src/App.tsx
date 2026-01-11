import { useState, useEffect } from 'react';
import { Routes, Route, NavLink, Link, useLocation } from 'react-router-dom';
import { Brain, ScanEye, FileChartColumn, Antenna, ListOrdered } from 'lucide-react';
import { Dashboard } from './pages/Dashboard';
import { Devices } from './pages/Devices';
import { Games } from './pages/Games';
import { Runs } from './pages/Runs';
import { Queue } from './pages/Queue';
import { WorkflowBuilder } from './pages/WorkflowBuilder';
import { Settings } from './pages/Settings';
import { useServiceHealth, useRuns } from './hooks';
import { ToastProvider } from './contexts/ToastContext';
import { ToastContainer } from './components/shared/ToastContainer';
import type { ServiceHealthStatus } from './types';

// Mobile detection hook
function useIsMobile(breakpoint = 768) {
  const [isMobile, setIsMobile] = useState(() =>
    typeof window !== 'undefined' ? window.innerWidth < breakpoint : false
  );

  useEffect(() => {
    const handleResize = () => setIsMobile(window.innerWidth < breakpoint);
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [breakpoint]);

  return isMobile;
}

// Service Icon component for footer with activity animation
interface ServiceIconProps {
  icon: React.ComponentType<{ className?: string }>;
  name: string;
  status?: ServiceHealthStatus['status'];
  extra?: number;
  active?: boolean; // Show activity animation
}

function ServiceIcon({ icon: Icon, name, status, extra, active }: ServiceIconProps) {
  const statusColors = {
    online: 'text-success',
    offline: 'text-danger',
    error: 'text-danger',
    starting: 'text-warning',
  };

  const colorClass = status ? statusColors[status] : 'text-text-muted';

  // Activity animation - blink when active
  const activityClass = active && status === 'online' ? 'animate-pulse' : '';

  return (
    <div className="flex items-center gap-2 group" title={`${name}: ${status || 'unknown'}`}>
      <Icon className={`w-5 h-5 ${colorClass} ${activityClass} transition-colors`} />
      <span className="text-xs text-text-muted font-medium">{name}</span>
      {extra !== undefined && extra > 0 && (
        <span className="text-xs text-text-muted font-numbers">({extra})</span>
      )}
    </div>
  );
}

function App() {
  const isMobile = useIsMobile();
  const location = useLocation();

  // Hide header/footer for WorkflowBuilder (fullscreen mode)
  const isWorkflowBuilder = location.pathname === '/workflow';

  // Service health for footer status bar - poll every 10s since /api/status takes ~3s
  const { services } = useServiceHealth(10000);
  const { activeRunsList } = useRuns();

  // Check if there's active automation running
  const hasActiveRuns = activeRunsList.length > 0;

  const navLinkClass = ({ isActive }: { isActive: boolean }) =>
    `px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
      isActive
        ? 'bg-primary text-white'
        : 'text-text-secondary hover:bg-surface-hover hover:text-text-primary'
    }`;

  return (
    <ToastProvider>
    <div className="min-h-screen bg-background flex flex-col">
      {/* Header - Hide on mobile and WorkflowBuilder */}
      {!isMobile && !isWorkflowBuilder && (
        <header className="bg-surface border-b border-border sticky top-0 z-50">
          <div className="px-4 lg:px-6">
            <div className="flex items-center justify-between h-14">
              {/* Left - Logo */}
              <NavLink to="/" className="flex items-center gap-2 flex-shrink-0">
                <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-brand-cyan via-primary to-brand-pink flex items-center justify-center">
                  <span className="font-numbers text-white text-xs font-bold tracking-tight">RX</span>
                </div>
                <div className="hidden sm:flex flex-col leading-none">
                  <span className="font-numbers text-lg font-bold text-text-primary tracking-tight">
                    Raptor X
                  </span>
                  <span className="text-[10px] text-text-muted tracking-wide">
                    MISSION CONTROL
                  </span>
                </div>
              </NavLink>

              {/* Center - Navigation Tabs */}
              <nav className="flex items-center gap-1 absolute left-1/2 transform -translate-x-1/2">
                <NavLink to="/" className={navLinkClass} end>
                  Dashboard
                </NavLink>
                <NavLink to="/devices" className={navLinkClass}>
                  SUTs
                </NavLink>
                <NavLink to="/games" className={navLinkClass}>
                  Games
                </NavLink>
                <NavLink to="/runs" className={navLinkClass}>
                  Runs
                </NavLink>
                <NavLink to="/queue" className={navLinkClass}>
                  Queue
                </NavLink>
              </nav>

              {/* Right - Actions */}
              <div className="flex items-center gap-2 flex-shrink-0">
                <Link
                  to="/workflow"
                  className="px-3 py-1.5 rounded-lg text-sm font-medium bg-primary/20 text-primary hover:bg-primary/30 transition-colors hidden sm:block"
                >
                  Workflow Builder
                </Link>
                <NavLink
                  to="/settings"
                  className={({ isActive }) =>
                    `p-2 rounded-lg transition-colors ${
                      isActive
                        ? 'bg-surface-hover text-text-primary'
                        : 'text-text-muted hover:bg-surface-hover hover:text-text-primary'
                    }`
                  }
                  title="Settings"
                >
                  <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                  </svg>
                </NavLink>
              </div>
            </div>
          </div>
        </header>
      )}

      {/* Main Content - flex-1 to push footer to bottom */}
      <main className="flex-1">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/devices" element={<Devices />} />
          <Route path="/games" element={<Games />} />
          <Route path="/runs" element={<Runs />} />
          <Route path="/queue" element={<Queue />} />
          <Route path="/workflow" element={<WorkflowBuilder />} />
          <Route path="/settings" element={<Settings />} />
        </Routes>
      </main>

      {/* Footer - Hide on mobile and WorkflowBuilder */}
      {!isMobile && !isWorkflowBuilder && (
        <footer className="bg-surface border-t border-border sticky bottom-0 z-40 px-4 py-2.5">
          <div className="flex items-center justify-center gap-6">
            {/* Gemma Backend */}
            <ServiceIcon
              icon={Brain}
              name="Gemma"
              status={services?.gemmaBackend.status}
              active={hasActiveRuns}
            />
            {/* SUT Discovery */}
            <ServiceIcon
              icon={Antenna}
              name="Discovery"
              status={services?.discoveryService.status}
            />
            {/* Queue Service */}
            <ServiceIcon
              icon={ListOrdered}
              name="Queue"
              status={services?.queueService.status}
              extra={services?.queueService.queueDepth}
              active={hasActiveRuns}
            />
            {/* Preset Manager */}
            <ServiceIcon
              icon={FileChartColumn}
              name="Presets"
              status={services?.presetManager.status}
            />
            {/* OmniParser Instances */}
            {services?.omniparserInstances.map((instance, idx) => (
              <ServiceIcon
                key={instance.name}
                icon={ScanEye}
                name={`OP${idx + 1}`}
                status={instance.status}
                active={hasActiveRuns}
              />
            ))}
          </div>
        </footer>
      )}
      <ToastContainer />
    </div>
    </ToastProvider>
  );
}

export default App;
