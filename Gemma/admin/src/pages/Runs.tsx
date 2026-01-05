import React, { useState, useCallback, useEffect, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useRuns, useCampaigns } from '../hooks';
import { LogViewer, RunTimeline } from '../components';
import type { AutomationRun, LogEntry, Campaign } from '../types';

// Expand icon component
function ExpandIcon({ className = "w-4 h-4" }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" />
    </svg>
  );
}

// Close icon component
function CloseIcon({ className = "w-5 h-5" }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
    </svg>
  );
}

// Chevron icons for carousel
function ChevronLeft({ className = "w-5 h-5" }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
    </svg>
  );
}

function ChevronRight({ className = "w-5 h-5" }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
    </svg>
  );
}

// Split screen icon
function SplitIcon({ className = "w-4 h-4" }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 17V7m0 10a2 2 0 01-2 2H5a2 2 0 01-2-2V7a2 2 0 012-2h2a2 2 0 012 2m0 10a2 2 0 002 2h2a2 2 0 002-2M9 7a2 2 0 012-2h2a2 2 0 012 2m0 10V7m0 10a2 2 0 002 2h2a2 2 0 002-2V7a2 2 0 00-2-2h-2a2 2 0 00-2 2" />
    </svg>
  );
}

// Helper to parse logs and identify iteration boundaries
function parseLogsWithIterations(logs: LogEntry[]): { iterations: Map<number, LogEntry[]>; global: LogEntry[] } {
  const iterations = new Map<number, LogEntry[]>();
  const global: LogEntry[] = [];
  let currentIteration: number | null = null;

  for (const log of logs) {
    // Check for iteration start markers
    const startMatch = log.message.match(/Starting iteration (\d+)/i) ||
                       log.message.match(/Iteration (\d+) starting/i) ||
                       log.message.match(/Beginning iteration (\d+)/i);
    if (startMatch) {
      currentIteration = parseInt(startMatch[1], 10);
    }

    // Check for iteration reference in message
    const iterMatch = log.message.match(/iteration (\d+)/i) ||
                      log.message.match(/Iteration (\d+)/i);
    const iterNum = iterMatch ? parseInt(iterMatch[1], 10) : currentIteration;

    if (iterNum !== null) {
      if (!iterations.has(iterNum)) {
        iterations.set(iterNum, []);
      }
      iterations.get(iterNum)!.push(log);
    } else {
      global.push(log);
    }
  }

  return { iterations, global };
}

// Log Panel Component for one side of the view
function LogPanel({
  logs,
  title,
  iterations,
  selectedIteration,
  onIterationChange,
  maxHeight,
}: {
  logs: LogEntry[];
  title: string;
  iterations: number[];
  selectedIteration: number | 'all';
  onIterationChange: (iter: number | 'all') => void;
  maxHeight: string;
}) {
  const parsedLogs = useMemo(() => parseLogsWithIterations(logs), [logs]);

  const displayLogs = useMemo(() => {
    if (selectedIteration === 'all') {
      return logs;
    }
    const iterLogs = parsedLogs.iterations.get(selectedIteration) || [];
    return iterLogs;
  }, [logs, selectedIteration, parsedLogs]);

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 bg-surface-elevated border-b border-border">
        <span className="font-medium text-text-primary text-sm truncate">{title}</span>
        {/* Iteration selector */}
        {iterations.length > 1 && (
          <select
            value={selectedIteration}
            onChange={(e) => onIterationChange(e.target.value === 'all' ? 'all' : parseInt(e.target.value, 10))}
            className="text-xs bg-surface border border-border rounded px-2 py-1 text-text-primary"
          >
            <option value="all">All Iterations</option>
            {iterations.map(i => (
              <option key={i} value={i}>Iteration {i}</option>
            ))}
          </select>
        )}
      </div>
      {/* Logs */}
      <div className="flex-1 overflow-auto bg-gray-900 p-3 font-mono text-xs" style={{ maxHeight }}>
        {displayLogs.length === 0 ? (
          <div className="text-gray-500 text-center py-4">No logs for this selection</div>
        ) : (
          displayLogs.map((log, index) => (
            <div key={index} className="flex gap-2 hover:bg-gray-800 px-1 -mx-1 rounded leading-relaxed">
              <span className="text-gray-500 flex-shrink-0">
                {new Date(log.timestamp).toLocaleTimeString('en-US', { hour12: false })}
              </span>
              <span className={`flex-shrink-0 uppercase w-14 ${
                log.level === 'error' ? 'text-red-400' :
                log.level === 'warning' ? 'text-yellow-400' :
                log.level === 'info' ? 'text-blue-400' : 'text-gray-500'
              }`}>
                [{log.level}]
              </span>
              <span className="text-gray-300 break-all whitespace-pre-wrap">{log.message}</span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

// Expanded Logs Modal with iteration filtering and split-screen compare
function ExpandedLogsModal({
  isOpen,
  onClose,
  item,
  logsCache,
  logsLoading,
  getStatusBadge,
}: {
  isOpen: boolean;
  onClose: () => void;
  item: RunSummaryItem | null;
  logsCache: Record<string, LogEntry[]>;
  logsLoading: Set<string>;
  getStatusBadge: (status: string) => string;
}) {
  // State for current view
  const [selectedGame, setSelectedGame] = useState<string | null>(null);
  const [selectedIteration, setSelectedIteration] = useState<number | 'all'>('all');
  const [compareMode, setCompareMode] = useState(false);
  const [compareGame, setCompareGame] = useState<string | null>(null);
  const [compareIteration, setCompareIteration] = useState<number | 'all'>('all');

  // Get available runs/games
  const availableRuns = useMemo(() => {
    if (!item) return [];
    if (item.type === 'single' && item.run) {
      return [{ id: item.run.run_id, name: item.run.game_name, status: item.run.status, iterations: item.run.iterations || 1 }];
    }
    if (item.campaignRuns) {
      return item.campaignRuns.map(r => ({
        id: r.run_id,
        name: r.game_name,
        status: r.status,
        iterations: r.iterations || 1
      }));
    }
    return [];
  }, [item]);

  // Set default selection when item changes
  useEffect(() => {
    if (availableRuns.length > 0 && !selectedGame) {
      setSelectedGame(availableRuns[0].id);
    }
  }, [availableRuns, selectedGame]);

  // Get current logs and iterations for selected game
  const currentLogs = selectedGame ? (logsCache[selectedGame] || []) : [];
  const currentRun = availableRuns.find(r => r.id === selectedGame);
  const currentIterations = currentRun ? Array.from({ length: currentRun.iterations }, (_, i) => i + 1) : [];

  // Get compare logs and iterations
  const compareLogs = compareGame ? (logsCache[compareGame] || []) : [];
  const compareRunData = availableRuns.find(r => r.id === compareGame);
  const compareIterations = compareRunData ? Array.from({ length: compareRunData.iterations }, (_, i) => i + 1) : [];

  if (!isOpen || !item) return null;

  const title = item.type === 'campaign'
    ? `Campaign Logs - ${formatGamesDisplay(item.games, 5)}`
    : `Run Logs - ${item.games[0]}`;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
      <div className="bg-surface border border-border rounded-lg shadow-xl w-full max-w-7xl" style={{ height: '90vh' }}>
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-3 border-b border-border">
          <h2 className="text-lg font-semibold text-text-primary">{title}</h2>
          <div className="flex items-center gap-3">
            {/* Compare toggle */}
            <button
              onClick={() => {
                setCompareMode(!compareMode);
                if (!compareMode && availableRuns.length > 1) {
                  // Set compare to second game by default
                  setCompareGame(availableRuns[1]?.id || availableRuns[0].id);
                }
              }}
              className={`flex items-center gap-2 px-3 py-1.5 text-sm rounded-lg transition-colors ${
                compareMode
                  ? 'bg-primary/20 text-primary border border-primary'
                  : 'bg-surface-elevated text-text-muted hover:text-text-primary border border-border'
              }`}
              title="Toggle split-screen compare"
            >
              <SplitIcon />
              <span>Compare</span>
            </button>
            <button
              onClick={onClose}
              className="p-2 text-text-muted hover:text-text-primary hover:bg-surface-elevated rounded-lg transition-colors"
            >
              <CloseIcon />
            </button>
          </div>
        </div>

        {/* Game selector bar */}
        <div className="flex items-center gap-2 px-6 py-2 border-b border-border bg-surface-elevated/50">
          <span className="text-xs text-text-muted mr-2">Game:</span>
          <div className="flex gap-2 flex-wrap">
            {availableRuns.map(run => (
              <button
                key={run.id}
                onClick={() => {
                  setSelectedGame(run.id);
                  setSelectedIteration('all');
                }}
                className={`px-3 py-1 text-xs font-medium rounded-full transition-colors ${
                  selectedGame === run.id
                    ? 'bg-primary text-white'
                    : 'bg-surface border border-border text-text-secondary hover:border-primary'
                }`}
              >
                {run.name}
                <span className={`ml-2 inline-flex px-1.5 py-0.5 text-[10px] rounded-full ${getStatusBadge(run.status)}`}>
                  {run.status}
                </span>
              </button>
            ))}
          </div>
          {compareMode && (
            <>
              <span className="text-xs text-text-muted mx-4">vs</span>
              <div className="flex gap-2 flex-wrap">
                {availableRuns.map(run => (
                  <button
                    key={run.id}
                    onClick={() => {
                      setCompareGame(run.id);
                      setCompareIteration('all');
                    }}
                    className={`px-3 py-1 text-xs font-medium rounded-full transition-colors ${
                      compareGame === run.id
                        ? 'bg-cyan-500 text-white'
                        : 'bg-surface border border-border text-text-secondary hover:border-cyan-500'
                    }`}
                  >
                    {run.name}
                    <span className={`ml-2 inline-flex px-1.5 py-0.5 text-[10px] rounded-full ${getStatusBadge(run.status)}`}>
                      {run.status}
                    </span>
                  </button>
                ))}
              </div>
            </>
          )}
        </div>

        {/* Content */}
        <div className={`flex gap-2 p-4 ${compareMode ? 'h-[calc(90vh-130px)]' : 'h-[calc(90vh-130px)]'}`}>
          {/* Left/Main Panel */}
          <div className={`${compareMode ? 'w-1/2' : 'w-full'} border border-border rounded-lg overflow-hidden`}>
            {selectedGame && logsLoading.has(selectedGame) ? (
              <div className="h-full flex items-center justify-center text-text-muted">
                Loading logs...
              </div>
            ) : (
              <LogPanel
                logs={currentLogs}
                title={currentRun?.name || 'Logs'}
                iterations={currentIterations}
                selectedIteration={selectedIteration}
                onIterationChange={setSelectedIteration}
                maxHeight="100%"
              />
            )}
          </div>

          {/* Right Panel (Compare) */}
          {compareMode && (
            <div className="w-1/2 border border-cyan-500/30 rounded-lg overflow-hidden">
              {compareGame && logsLoading.has(compareGame) ? (
                <div className="h-full flex items-center justify-center text-text-muted">
                  Loading logs...
                </div>
              ) : (
                <LogPanel
                  logs={compareLogs}
                  title={compareRunData?.name || 'Compare Logs'}
                  iterations={compareIterations}
                  selectedIteration={compareIteration}
                  onIterationChange={setCompareIteration}
                  maxHeight="100%"
                />
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// Iteration Carousel Component for timeline
function IterationCarousel({
  runId,
  iterations,
  pollInterval,
  runStatus,
  previousGameName,
}: {
  runId: string;
  iterations: number;
  pollInterval: number;
  runStatus: string;
  previousGameName?: string;
}) {
  const [currentIteration, setCurrentIteration] = useState(0); // 0 = all, 1-N = specific iteration

  const handlePrev = () => {
    setCurrentIteration(prev => (prev <= 0 ? iterations : prev - 1));
  };

  const handleNext = () => {
    setCurrentIteration(prev => (prev >= iterations ? 0 : prev + 1));
  };

  return (
    <div>
      {/* Iteration navigation */}
      {iterations > 1 && (
        <div className="flex items-center justify-between mb-3 px-2">
          <button
            onClick={handlePrev}
            className="p-1.5 text-text-muted hover:text-text-primary hover:bg-surface-elevated rounded-lg transition-colors"
          >
            <ChevronLeft />
          </button>
          <div className="flex items-center gap-2">
            <span className="text-sm text-text-secondary">
              {currentIteration === 0 ? 'All Iterations' : `Iteration ${currentIteration}/${iterations}`}
            </span>
            {/* Dots indicator */}
            <div className="flex items-center gap-1">
              <button
                onClick={() => setCurrentIteration(0)}
                className={`w-2 h-2 rounded-full transition-colors ${
                  currentIteration === 0 ? 'bg-primary' : 'bg-border hover:bg-text-muted'
                }`}
                title="All iterations"
              />
              {Array.from({ length: iterations }, (_, i) => (
                <button
                  key={i + 1}
                  onClick={() => setCurrentIteration(i + 1)}
                  className={`w-2 h-2 rounded-full transition-colors ${
                    currentIteration === i + 1 ? 'bg-primary' : 'bg-border hover:bg-text-muted'
                  }`}
                  title={`Iteration ${i + 1}`}
                />
              ))}
            </div>
          </div>
          <button
            onClick={handleNext}
            className="p-1.5 text-text-muted hover:text-text-primary hover:bg-surface-elevated rounded-lg transition-colors"
          >
            <ChevronRight />
          </button>
        </div>
      )}

      {/* Timeline with iteration filter */}
      <RunTimeline
        runId={runId}
        pollInterval={pollInterval}
        runStatus={runStatus}
        filterIteration={currentIteration > 0 ? currentIteration : undefined}
        previousGameName={previousGameName}
      />
    </div>
  );
}

// Game name to short form mapping
const GAME_SHORT_NAMES: Record<string, string> = {
  'assassins-creed-mirage': 'AC-M',
  'ac-mirage': 'AC-M',
  'black-myth-wukong': 'BMW',
  'cyberpunk-2077': 'CP77',
  'cyberpunk 2077': 'CP77',
  'counter-strike-2': 'CS2',
  'dota-2': 'DOTA2',
  'f1-24': 'F1-24',
  'far-cry-6': 'FC6',
  'far cry 6': 'FC6',
  'final-fantasy-xiv-dawntrail': 'FFXIV',
  'hitman-3': 'H3',
  'hitman-3-dubai': 'H3',
  'hitman 3': 'H3',
  'horizon-zero-dawn-remastered': 'HZD',
  'red-dead-redemption-2': 'RDR2',
  'shadow-of-the-tomb-raider': 'SOTR',
  'shadow-of-tomb-raider': 'SOTR',
  'sid-meier-civ-6': 'CIV6',
  'tiny-tina-wonderlands': 'TTW',
};

function getGameShortName(gameName: string): string {
  const normalized = gameName.toLowerCase().replace(/\s+/g, '-');
  return GAME_SHORT_NAMES[normalized] || GAME_SHORT_NAMES[gameName.toLowerCase()] ||
    gameName.split(/[\s-]+/).map(w => w[0]?.toUpperCase()).join('').slice(0, 4);
}

function formatGamesDisplay(games: string[], maxShow: number = 3): string {
  if (games.length === 0) return '-';
  const shortNames = games.map(g => getGameShortName(g));
  if (shortNames.length <= maxShow) {
    return shortNames.join(', ');
  }
  return `${shortNames.slice(0, maxShow).join(', ')} +${shortNames.length - maxShow} more`;
}

// Unified run item type
type RunSummaryItem = {
  id: string;
  type: 'single' | 'campaign';
  games: string[];
  sut_ip: string;
  status: string;
  started_at: string | null;
  completed_at?: string | null;
  iterations: number;
  quality?: string | null;
  resolution?: string | null;
  // For campaigns
  campaign?: Campaign;
  campaignRuns?: AutomationRun[];
  // For single runs
  run?: AutomationRun;
};

// Calculate duration from start to end (or now if running)
function formatDuration(startedAt: string | null, completedAt: string | null | undefined, status: string): string {
  if (!startedAt) return '-';
  const start = new Date(startedAt).getTime();
  const end = completedAt ? new Date(completedAt).getTime() :
    (status === 'running' ? Date.now() : new Date(startedAt).getTime());
  const diffMs = end - start;
  if (diffMs < 0) return '-';

  const seconds = Math.floor(diffMs / 1000);
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);

  if (hours > 0) {
    return `${hours}h ${minutes % 60}m`;
  } else if (minutes > 0) {
    return `${minutes}m ${seconds % 60}s`;
  } else {
    return `${seconds}s`;
  }
}

export function Runs() {
  const [searchParams, setSearchParams] = useSearchParams();
  const { activeRunsList, history, loading, stop } = useRuns();
  const { activeCampaigns, historyCampaigns, stop: stopCampaign } = useCampaigns();
  const [isClearing, setIsClearing] = useState(false);

  // Expanded rows state
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());
  const [expandedTab, setExpandedTab] = useState<Record<string, 'timeline' | 'logs'>>({});
  const [logsCache, setLogsCache] = useState<Record<string, LogEntry[]>>({});
  const [logsLoading, setLogsLoading] = useState<Set<string>>(new Set());

  // Expanded logs modal state
  const [expandedLogsItem, setExpandedLogsItem] = useState<RunSummaryItem | null>(null);

  // Build unified list combining campaigns and standalone runs
  const unifiedList = useMemo(() => {
    const items: RunSummaryItem[] = [];

    // Create a map of all runs by ID for quick lookup
    const allRunsMap = new Map<string, AutomationRun>();
    activeRunsList.forEach(r => allRunsMap.set(r.run_id, r));
    history.forEach(r => allRunsMap.set(r.run_id, r));

    // Track which run IDs belong to campaigns
    const campaignRunIds = new Set<string>();

    // Add active campaigns
    activeCampaigns.forEach(campaign => {
      // Use run_ids from campaign to find associated runs
      const campaignRuns: AutomationRun[] = [];
      (campaign.run_ids || []).forEach(runId => {
        campaignRunIds.add(runId);
        const run = allRunsMap.get(runId);
        if (run) campaignRuns.push(run);
      });
      // Also check by campaign_id as fallback
      activeRunsList.filter(r => r.campaign_id === campaign.campaign_id).forEach(r => {
        campaignRunIds.add(r.run_id);
        if (!campaignRuns.find(cr => cr.run_id === r.run_id)) campaignRuns.push(r);
      });

      items.push({
        id: `campaign-${campaign.campaign_id}`,
        type: 'campaign',
        games: campaign.games,
        sut_ip: campaign.sut_ip,
        status: campaign.status,
        started_at: String(campaign.created_at || ''),
        completed_at: campaign.completed_at ? String(campaign.completed_at) : null,
        iterations: campaign.iterations_per_game,
        quality: campaign.quality,
        resolution: campaign.resolution,
        campaign,
        campaignRuns,
      });
    });

    // Add historical campaigns
    historyCampaigns.forEach(campaign => {
      // Use run_ids from campaign to find associated runs
      const campaignRuns: AutomationRun[] = [];
      (campaign.run_ids || []).forEach(runId => {
        campaignRunIds.add(runId);
        const run = allRunsMap.get(runId);
        if (run) campaignRuns.push(run);
      });
      // Also check by campaign_id as fallback
      history.filter(r => r.campaign_id === campaign.campaign_id).forEach(r => {
        campaignRunIds.add(r.run_id);
        if (!campaignRuns.find(cr => cr.run_id === r.run_id)) campaignRuns.push(r);
      });

      items.push({
        id: `campaign-${campaign.campaign_id}`,
        type: 'campaign',
        games: campaign.games,
        sut_ip: campaign.sut_ip,
        status: campaign.status,
        started_at: String(campaign.created_at || ''),
        completed_at: campaign.completed_at ? String(campaign.completed_at) : null,
        iterations: campaign.iterations_per_game,
        quality: campaign.quality,
        resolution: campaign.resolution,
        campaign,
        campaignRuns,
      });
    });

    // Add active standalone runs (exclude runs that belong to campaigns)
    activeRunsList.filter(r => !r.campaign_id && !campaignRunIds.has(r.run_id)).forEach(run => {
      items.push({
        id: `run-${run.run_id}`,
        type: 'single',
        games: [run.game_name],
        sut_ip: run.sut_ip,
        status: run.status,
        started_at: run.started_at || null,
        completed_at: run.completed_at || null,
        iterations: run.iterations,
        quality: run.quality,
        resolution: run.resolution,
        run,
      });
    });

    // Add historical standalone runs (exclude runs that belong to campaigns)
    history.filter(r => !r.campaign_id && !campaignRunIds.has(r.run_id)).forEach(run => {
      items.push({
        id: `run-${run.run_id}`,
        type: 'single',
        games: [run.game_name],
        sut_ip: run.sut_ip,
        status: run.status,
        started_at: run.started_at || null,
        completed_at: run.completed_at || null,
        iterations: run.iterations,
        quality: run.quality,
        resolution: run.resolution,
        run,
      });
    });

    // Sort by started_at descending (most recent first)
    items.sort((a, b) => {
      const timeA = a.started_at ? new Date(a.started_at).getTime() : 0;
      const timeB = b.started_at ? new Date(b.started_at).getTime() : 0;
      return timeB - timeA;
    });

    return items;
  }, [activeCampaigns, historyCampaigns, activeRunsList, history]);

  const toggleRowExpand = (id: string) => {
    setExpandedRows(prev => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
        // Default to timeline tab
        if (!expandedTab[id]) {
          setExpandedTab(t => ({ ...t, [id]: 'timeline' }));
        }
      }
      return next;
    });
  };

  const fetchLogs = useCallback(async (runId: string) => {
    if (logsCache[runId]) return;

    setLogsLoading(prev => new Set(prev).add(runId));
    try {
      const response = await fetch(`/api/runs/${runId}/logs`);
      if (response.ok) {
        const data = await response.json();
        setLogsCache(prev => ({ ...prev, [runId]: data.logs || [] }));
      }
    } catch (error) {
      console.error('Failed to fetch logs:', error);
    } finally {
      setLogsLoading(prev => {
        const next = new Set(prev);
        next.delete(runId);
        return next;
      });
    }
  }, [logsCache]);

  // Handle URL query param for run selection
  useEffect(() => {
    const runId = searchParams.get('run');
    if (!runId) return;

    // Find the item containing this run
    const item = unifiedList.find(i =>
      i.type === 'single' && i.run?.run_id === runId ||
      i.type === 'campaign' && i.campaignRuns?.some(r => r.run_id === runId)
    );

    if (item) {
      setExpandedRows(prev => new Set(prev).add(item.id));
      setExpandedTab(t => ({ ...t, [item.id]: 'timeline' }));
      // Clear URL param
      searchParams.delete('run');
      setSearchParams(searchParams, { replace: true });
    }
  }, [searchParams, unifiedList, setSearchParams]);

  // Count queued runs
  const queuedRuns = activeRunsList.filter(r => r.status === 'queued');
  const queuedCount = queuedRuns.length;

  const stats = {
    active: activeRunsList.filter(r => r.status === 'running').length + activeCampaigns.filter(c => c.status === 'running').length,
    queued: queuedCount,
    completed: history.filter(r => r.status === 'completed').length,
    failed: history.filter(r => r.status === 'failed').length,
    total: unifiedList.length,
  };

  // Clear all queued runs
  const handleClearQueue = async () => {
    if (queuedCount === 0) return;
    if (!window.confirm(`Clear ${queuedCount} queued runs? This cannot be undone.`)) return;

    setIsClearing(true);
    try {
      // Stop all queued runs
      await Promise.all(queuedRuns.map(run => stop(run.run_id, false).catch(console.error)));
    } finally {
      setIsClearing(false);
    }
  };

  const getStatusBadge = (status: string) => {
    const styles: Record<string, string> = {
      running: 'bg-primary/20 text-primary',
      queued: 'bg-warning/20 text-warning',
      completed: 'bg-success/20 text-success',
      failed: 'bg-danger/20 text-danger',
      stopped: 'bg-text-muted/20 text-text-muted',
      partially_completed: 'bg-warning/20 text-warning',
    };
    return styles[status] || 'bg-surface-elevated text-text-muted';
  };

  return (
    <div className="space-y-6 p-4 lg:p-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-text-primary">Automation Runs</h1>
        <p className="text-text-muted">Monitor active and past automation runs</p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-4">
        <div className="card p-4">
          <p className="text-sm text-text-muted">Running</p>
          <p className="text-2xl font-bold text-primary">{stats.active}</p>
        </div>
        <div className="card p-4 relative">
          <p className="text-sm text-text-muted">Queued</p>
          <p className={`text-2xl font-bold ${stats.queued > 0 ? 'text-warning' : 'text-text-primary'}`}>
            {stats.queued}
          </p>
          {stats.queued > 0 && (
            <button
              onClick={handleClearQueue}
              disabled={isClearing}
              className="absolute top-2 right-2 text-xs px-2 py-0.5 bg-danger/20 text-danger hover:bg-danger/30 rounded transition-colors disabled:opacity-50"
              title="Clear all queued runs"
            >
              {isClearing ? '...' : 'Clear'}
            </button>
          )}
        </div>
        <div className="card p-4">
          <p className="text-sm text-text-muted">Total</p>
          <p className="text-2xl font-bold text-text-primary">{stats.total}</p>
        </div>
        <div className="card p-4">
          <p className="text-sm text-text-muted">Completed</p>
          <p className="text-2xl font-bold text-success">{stats.completed}</p>
        </div>
        <div className="card p-4">
          <p className="text-sm text-text-muted">Failed</p>
          <p className="text-2xl font-bold text-danger">{stats.failed}</p>
        </div>
      </div>

      {/* Run Summary Table */}
      <div>
        <h2 className="text-lg font-semibold text-text-primary mb-4">
          Run Summary ({unifiedList.length})
        </h2>
        {loading ? (
          <div className="space-y-2">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="card p-4 animate-pulse">
                <div className="h-4 bg-surface-elevated rounded w-1/3 mb-2"></div>
                <div className="h-3 bg-surface-elevated rounded w-1/4"></div>
              </div>
            ))}
          </div>
        ) : unifiedList.length === 0 ? (
          <div className="card p-8 text-center text-text-muted">
            No runs yet
          </div>
        ) : (
          <div className="card overflow-hidden">
            <table className="min-w-full divide-y divide-border">
              <thead className="bg-surface-elevated">
                <tr>
                  <th className="w-8 px-2"></th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-text-muted uppercase tracking-wider">
                    Type
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-text-muted uppercase tracking-wider">
                    Game(s)
                  </th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-text-muted uppercase tracking-wider hidden sm:table-cell">
                    SUT
                  </th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-text-muted uppercase tracking-wider hidden lg:table-cell">
                    Preset
                  </th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-text-muted uppercase tracking-wider">
                    Status
                  </th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-text-muted uppercase tracking-wider hidden md:table-cell">
                    Duration
                  </th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-text-muted uppercase tracking-wider hidden lg:table-cell">
                    Started
                  </th>
                  <th className="w-16 px-2 py-3"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {unifiedList.slice(0, 50).map((item) => {
                  const isExpanded = expandedRows.has(item.id);
                  const currentTab = expandedTab[item.id] || 'timeline';

                  return (
                    <React.Fragment key={item.id}>
                      {/* Main Row */}
                      <tr
                        className={`hover:bg-surface-hover transition-colors cursor-pointer ${isExpanded ? 'bg-surface-elevated' : ''}`}
                        onClick={() => toggleRowExpand(item.id)}
                      >
                        <td className="px-2 py-3">
                          <svg
                            className={`h-4 w-4 text-text-muted transition-transform ${isExpanded ? 'rotate-90' : ''}`}
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                          >
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                          </svg>
                        </td>
                        <td className="px-3 py-3">
                          <span className={`inline-flex px-2 py-0.5 text-xs font-medium rounded ${
                            item.type === 'campaign' ? 'bg-purple-500/20 text-purple-400' : 'bg-cyan-500/20 text-cyan-400'
                          }`}>
                            {item.type === 'campaign' ? 'Campaign' : 'Single'}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-sm font-medium text-text-primary">
                          {item.type === 'campaign' ? (
                            <span title={item.games.join(', ')}>
                              {formatGamesDisplay(item.games, 3)}
                            </span>
                          ) : (
                            item.games[0]
                          )}
                        </td>
                        <td className="px-3 py-3 text-sm text-text-muted hidden sm:table-cell font-mono">
                          {item.sut_ip}
                        </td>
                        <td className="px-3 py-3 text-sm hidden lg:table-cell">
                          {item.quality && item.resolution ? (
                            <span className="text-xs text-text-secondary">
                              {item.quality}@{item.resolution}
                            </span>
                          ) : (
                            <span className="text-text-muted">-</span>
                          )}
                        </td>
                        <td className="px-3 py-3">
                          <span className={`inline-flex px-2 py-0.5 text-xs font-medium rounded-full ${getStatusBadge(item.status)}`}>
                            {item.status}
                          </span>
                        </td>
                        <td className="px-3 py-3 text-sm text-text-muted hidden md:table-cell font-mono">
                          {formatDuration(item.started_at, item.completed_at, item.status)}
                        </td>
                        <td className="px-3 py-3 text-sm text-text-muted hidden lg:table-cell">
                          {item.started_at ? new Date(item.started_at).toLocaleString() : '-'}
                        </td>
                        <td className="px-2 py-3 text-sm" onClick={e => e.stopPropagation()}>
                          {(item.status === 'running' || item.status === 'queued') && (
                            <button
                              onClick={() => {
                                if (item.type === 'campaign' && item.campaign) {
                                  stopCampaign(item.campaign.campaign_id).catch(console.error);
                                } else if (item.run) {
                                  stop(item.run.run_id, false).catch(console.error);
                                }
                              }}
                              className="text-danger hover:text-danger/80 text-xs font-medium"
                            >
                              Stop
                            </button>
                          )}
                        </td>
                      </tr>

                      {/* Expanded Content */}
                      {isExpanded && (
                        <tr>
                          <td colSpan={9} className="p-0">
                            <div className="bg-surface-elevated border-t border-border">
                              {/* Tabs */}
                              <div className="flex items-center justify-between border-b border-border px-4">
                                <div className="flex">
                                  <button
                                    onClick={() => setExpandedTab(t => ({ ...t, [item.id]: 'timeline' }))}
                                    className={`px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px ${
                                      currentTab === 'timeline'
                                        ? 'text-primary border-primary'
                                        : 'text-text-muted border-transparent hover:text-text-secondary'
                                    }`}
                                  >
                                    Timeline
                                  </button>
                                  <button
                                    onClick={() => {
                                      setExpandedTab(t => ({ ...t, [item.id]: 'logs' }));
                                      // Fetch logs for all runs
                                      if (item.type === 'single' && item.run) {
                                        fetchLogs(item.run.run_id);
                                      } else if (item.campaignRuns) {
                                        item.campaignRuns.forEach(r => fetchLogs(r.run_id));
                                      }
                                    }}
                                    className={`px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px ${
                                      currentTab === 'logs'
                                        ? 'text-primary border-primary'
                                        : 'text-text-muted border-transparent hover:text-text-secondary'
                                    }`}
                                  >
                                    Logs
                                  </button>
                                </div>
                                {/* Expand button for logs */}
                                {currentTab === 'logs' && (
                                  <button
                                    onClick={() => setExpandedLogsItem(item)}
                                    className="p-1.5 text-text-muted hover:text-text-primary hover:bg-surface rounded-lg transition-colors"
                                    title="Expand logs"
                                  >
                                    <ExpandIcon />
                                  </button>
                                )}
                              </div>

                              {/* Tab Content */}
                              <div className="p-4 max-h-[500px] overflow-auto">
                                {currentTab === 'timeline' ? (
                                  item.type === 'single' && item.run ? (
                                    <IterationCarousel
                                      runId={item.run.run_id}
                                      iterations={item.run.iterations || 1}
                                      pollInterval={item.status === 'running' ? 2000 : 0}
                                      runStatus={item.status}
                                    />
                                  ) : item.campaignRuns && item.campaignRuns.length > 0 ? (
                                    <div className="space-y-4">
                                      {item.campaignRuns.map((run, index) => {
                                        // Get previous game name for queued runs
                                        const previousGameName = index > 0 ? item.campaignRuns![index - 1].game_name : undefined;
                                        // Auto-collapse queued runs
                                        const isCollapsed = run.status === 'queued';

                                        return (
                                          <div key={run.run_id} className="border border-border rounded-lg overflow-hidden">
                                            <div className="bg-surface px-4 py-2 border-b border-border flex items-center justify-between">
                                              <span className="font-medium text-text-primary">{run.game_name}</span>
                                              <span className={`inline-flex px-2 py-0.5 text-xs font-medium rounded-full ${getStatusBadge(run.status)}`}>
                                                {run.status}
                                              </span>
                                            </div>
                                            {!isCollapsed && (
                                              <div className="p-4">
                                                <IterationCarousel
                                                  runId={run.run_id}
                                                  iterations={run.iterations || 1}
                                                  pollInterval={run.status === 'running' ? 2000 : 0}
                                                  runStatus={run.status}
                                                  previousGameName={previousGameName}
                                                />
                                              </div>
                                            )}
                                            {isCollapsed && (
                                              <div className="px-4 py-3 bg-surface-elevated/50">
                                                <div className="flex items-center gap-2 text-warning text-sm">
                                                  <svg className="w-4 h-4 animate-pulse" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                                                  </svg>
                                                  <span>
                                                    {previousGameName
                                                      ? `Awaiting ${previousGameName} completion`
                                                      : 'Waiting in queue...'}
                                                  </span>
                                                </div>
                                              </div>
                                            )}
                                          </div>
                                        );
                                      })}
                                    </div>
                                  ) : (
                                    <div className="text-center text-text-muted py-8">
                                      No timeline data available
                                    </div>
                                  )
                                ) : (
                                  /* Logs Tab */
                                  item.type === 'single' && item.run ? (
                                    logsLoading.has(item.run.run_id) ? (
                                      <div className="text-center text-text-muted py-8 animate-pulse">
                                        Loading logs...
                                      </div>
                                    ) : logsCache[item.run.run_id] ? (
                                      <LogViewer logs={logsCache[item.run.run_id]} maxHeight="400px" />
                                    ) : (
                                      <div className="text-center text-text-muted py-8">
                                        No logs available
                                      </div>
                                    )
                                  ) : item.campaignRuns && item.campaignRuns.length > 0 ? (
                                    <div className="space-y-4">
                                      {item.campaignRuns.map(run => (
                                        <div key={run.run_id} className="border border-border rounded-lg overflow-hidden">
                                          <div className="bg-surface px-4 py-2 border-b border-border flex items-center justify-between">
                                            <span className="font-medium text-text-primary">{run.game_name}</span>
                                            <span className={`inline-flex px-2 py-0.5 text-xs font-medium rounded-full ${getStatusBadge(run.status)}`}>
                                              {run.status}
                                            </span>
                                          </div>
                                          <div className="p-4">
                                            {logsLoading.has(run.run_id) ? (
                                              <div className="text-center text-text-muted py-4 animate-pulse">
                                                Loading logs...
                                              </div>
                                            ) : logsCache[run.run_id] ? (
                                              <LogViewer logs={logsCache[run.run_id]} maxHeight="300px" />
                                            ) : (
                                              <div className="text-center text-text-muted py-4">
                                                No logs available
                                              </div>
                                            )}
                                          </div>
                                        </div>
                                      ))}
                                    </div>
                                  ) : (
                                    <div className="text-center text-text-muted py-8">
                                      No logs available
                                    </div>
                                  )
                                )}
                              </div>
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Expanded Logs Modal */}
      <ExpandedLogsModal
        isOpen={!!expandedLogsItem}
        onClose={() => setExpandedLogsItem(null)}
        item={expandedLogsItem}
        logsCache={logsCache}
        logsLoading={logsLoading}
        getStatusBadge={getStatusBadge}
      />
    </div>
  );
}
