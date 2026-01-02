# Gemma Frontend (Admin Dashboard)

React-based admin dashboard for monitoring and controlling game automation.

## Architecture

- **Entry Point**: `Gemma/admin/src/main.tsx` → `App.tsx`
- **Port**: 3000
- **Framework**: React 19 + React Router 7 + Tailwind CSS
- **Build Tool**: Vite
- **CLI Command**: `npm run dev` (from `Gemma/admin/`)

## Key Files

| File | Purpose |
|------|---------|
| `src/App.tsx` | Root component with routing |
| `src/main.tsx` | Entry point, React DOM render |
| `src/api/index.ts` | Core API client setup |
| `src/types/index.ts` | TypeScript type definitions |

## Pages (`src/pages/`)

| Page | Purpose |
|------|---------|
| `Dashboard.tsx` | Main overview with metrics |
| `Games.tsx` | Game management and configuration |
| `Runs.tsx` | Run history and active run details |
| `Devices.tsx` | Connected SUT device management |
| `Queue.tsx` | OmniParser request queue |
| `WorkflowBuilder.tsx` | Campaign/automation workflow editor |
| `Settings.tsx` | System configuration |

## Components (`src/components/`)

### Dashboard Components
| Component | Purpose |
|-----------|---------|
| `FleetStatusPanel.tsx` | SUT fleet overview with online count |
| `QuickLaunchPanel.tsx` | Main launch control (SUT select, game select, presets, pre-flight) |
| `GameLibraryPanel.tsx` | Netflix-style game grid with multi-select |
| `ActiveRunsPanel.tsx` | Live running automation cards |
| `RunMetricsPanel.tsx` | Success rate gauge, run statistics |
| `RadialGauge.tsx` | SVG circular gauge component |
| `SparklineChart.tsx` | Mini trend line chart |
| `CollapsiblePanel.tsx` | Collapsible panel wrapper |

### Core Components
| Component | Purpose |
|-----------|---------|
| `AutomationTimeline.tsx` | Real-time execution timeline |
| `RunTimeline.tsx` | Run progress visualization |
| `GameCard.tsx` | Game card display |
| `SUTCard.tsx` | SUT device card |
| `SUTDetailPanel.tsx` | SUT detail sidebar |
| `PreflightChecks.tsx` | Pre-automation system checks |
| `PresetMatrix.tsx` | Preset selection matrix |
| `ServiceHealthPanel.tsx` | Service status monitoring |
| `CampaignModal.tsx` | Campaign creation dialog |
| `LogViewer.tsx` | Log display component |
| `DataTable.tsx` | Generic data table |
| `ErrorBoundary.tsx` | Error handling wrapper |

## Hooks (`src/hooks/`)

| Hook | Purpose |
|------|---------|
| `useDevices.ts` | Device data fetching |
| `useRuns.ts` | Run data and WebSocket updates |
| `useGames.ts` | Game list fetching |
| `useCampaigns.ts` | Campaign management |
| `useQueueStats.ts` | Queue Service stats |
| `useServiceHealth.ts` | Service health monitoring |
| `useSystemStatus.ts` | Overall system status |

## API Clients (`src/api/`)

| Client | Purpose |
|--------|---------|
| `index.ts` | Core Gemma API client |
| `presetManager.ts` | Preset Manager API |
| `queueService.ts` | Queue Service API |
| `workflowBuilder.ts` | Workflow building endpoints |

## Features

### Real-time Updates
- WebSocket connection to Gemma Backend
- Live timeline event streaming
- Automatic run status updates

### Device Management
- View connected SUTs
- See installed games per SUT
- Monitor device health

### Run Monitoring
- Start/stop automation runs
- View timeline events in real-time
- See step progress and screenshots

## Dependencies

- **Depends on**: Gemma Backend (API + WebSocket)
- **Optional**: Preset Manager, Queue Service (for extended features)

## Common Modifications

### Add new page
1. Create component in `src/pages/`
2. Add route in `App.tsx`
3. Add navigation link in sidebar

### Add new API endpoint
1. Add function in `src/api/index.ts`
2. Create React Query hook in `src/hooks/`
3. Use hook in component

### Add new component
1. Create in `src/components/`
2. Export from `src/components/index.ts`
3. Import and use in pages

## Styling

- Tailwind CSS for utility classes
- Dark theme by default
- Responsive design

## Key Constants (QuickLaunchPanel.tsx)

### GAMES_WITH_PRESETS
Games that have actual preset files in `preset-manager/configs/presets/`:
- assassins-creed-mirage, black-myth-wukong, cyberpunk-2077, f1-24
- far-cry-6, final-fantasy-xiv-dawntrail, hitman-3-dubai
- horizon-zero-dawn-remastered, red-dead-redemption-2
- shadow-of-tomb-raider, sid-meier-civ-6, tiny-tina-wonderlands

**Note**: CS2, Dota 2 do NOT have presets.

### Helper Functions
- `gameHasPreset(game)` - Check if game has preset files
- `getDisplayGpu(name)` - Filter virtual GPUs, clean up GPU names
- `roundRamToEven(gb)` - Round RAM to nearest even (31.2 → 32)
- `getMaxResolution(resolutions)` - Get max supported resolution
- `getGameShortName(game)` - Get abbreviation (AC-M, BMW, FC6, etc.)

## Recent Changes

| Date | Change |
|------|--------|
| 2026-01-01 | Added GAMES_WITH_PRESETS set for accurate preset detection |
| 2026-01-01 | Filter virtual GPUs (Meta Virtual Monitor) from display |
| 2026-01-01 | Round RAM to even numbers (31GB → 32GB) |
| 2026-01-01 | Show both current and max resolution in system info |
| 2026-01-01 | Dynamic games chip display with scroll |
| 2026-01-01 | Fixed preset matrix API response transformation |
| 2026-01-01 | Fixed system info API response handling |
| 2024-12-31 | Added SUTDetailPanel component |
| 2024-12-31 | Added PreflightChecks and PresetMatrix |
| 2024-12-31 | Rebranded to Raptor X Mission Control |
