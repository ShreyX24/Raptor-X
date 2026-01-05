# Raptor X (RPX) - Game Automation Platform

A microservices-based game automation and benchmarking platform for testing graphics presets across multiple SUTs (Systems Under Test).

## Quick Navigation

| Service | Port | Docs (auto-loaded) |
|---------|------|------|
| Gemma Backend | 5000 | `.claude/rules/gemma-backend.md` |
| Gemma Frontend | 3000 | `.claude/rules/gemma-frontend.md` |
| Preset Manager | 5002 | `.claude/rules/preset-manager.md` |
| SUT Discovery | 5001 | `.claude/rules/sut-discovery.md` |
| Queue Service | 9000 | `.claude/rules/queue-service.md` |
| SUT Client | 8080 | `.claude/rules/sut-client.md` |
| Service Manager | GUI | `.claude/rules/service-manager.md` |
| OmniParser | 8100 | `.claude/rules/omniparser.md` |

**Note**: All files in `.claude/rules/` are auto-loaded at session start.

## Key Resources

- **Operational Knowledge** (SSH, commands, troubleshooting): @.claude/KNOWLEDGE.md
- **Learnings** (dos and don'ts, gotchas): @.claude/LEARNINGS.md
- **Coding Standards**: @.claude/rules/coding-standards.md

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     Service Manager (GUI)                        │
│                  Manages all services below                      │
└─────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│ Gemma Backend │◄──►│ Preset Manager│◄──►│ SUT Discovery │
│   Port 5000   │    │   Port 5002   │    │   Port 5001   │
└───────┬───────┘    └───────────────┘    └───────┬───────┘
        │                                         │
        ▼                                         ▼
┌───────────────┐                        ┌───────────────┐
│ Queue Service │                        │  SUT Client   │
│   Port 9000   │                        │  (on SUTs)    │
└───────┬───────┘                        └───────────────┘
        │
        ▼
┌───────────────┐
│  OmniParser   │
│   Port 8100   │
└───────────────┘
```

## Communication Flow

1. **Device Discovery**: SUT Client → UDP broadcast → SUT Discovery Service
2. **Preset Sync**: Preset Manager ↔ SUT Discovery (device registry)
3. **Automation**: Gemma Backend → SUT Client (via SUT Discovery proxy)
4. **Vision AI**: Gemma Backend → Queue Service → OmniParser (load-balanced)
5. **Real-time UI**: Gemma Frontend ↔ Gemma Backend (WebSocket)

## Knowledge Base Update Protocol

When making significant code changes:
1. Update the relevant `.claude/rules/<service>.md` file
2. Add entry to "Recent Changes" section with date
3. If you discover a gotcha, add to `LEARNINGS.md`
4. If you add a new feature, document in the service's rule file

## Task Management Protocol

**IMPORTANT**: When working on multiple tasks (more than 1), ALWAYS use the TodoWrite tool to:
1. Create a todo list with all tasks before starting
2. Mark tasks as `in_progress` when starting work
3. Mark tasks as `completed` immediately when done
4. Keep only ONE task `in_progress` at a time

This ensures visibility into progress and prevents missing issues.

## React Component Reuse Protocol

**CRITICAL**: Never duplicate logic between components. React is component-based for reuse.

### Rules
1. **Logic lives in hooks/utilities** - Not in components
2. **Components are for UI only** - Different layouts, same data
3. **100% logic reuse** - Desktop and mobile use identical hooks
4. **Extract before duplicating** - If logic exists, extract it first

### Pattern for Desktop/Mobile
```
src/
├── hooks/
│   └── useInstalledGames.ts    # Shared logic (game matching, fetching)
├── utils/
│   └── gameMatching.ts         # Pure utility functions
├── components/
│   ├── GameCard.tsx            # Reusable card component
│   └── mobile/
│       └── MobileGameCard.tsx  # Mobile-specific UI wrapper
└── pages/
    └── Dashboard.tsx           # Uses hooks, renders desktop or mobile UI
```

### What Changes Between Desktop/Mobile
- ✅ Layout (grid vs scroll)
- ✅ Component sizes (w-48 vs w-36)
- ✅ Navigation (sidebar vs drawer)
- ✅ Density (compact vs spacious)

### What NEVER Changes
- ❌ Data fetching logic
- ❌ Business logic (game matching, validation)
- ❌ API calls
- ❌ State management patterns
- ❌ Algorithms (matching, sorting, filtering)

### Before Writing New Code
1. Check if hook exists in `src/hooks/`
2. Check if utility exists in `src/utils/`
3. If logic exists in another component, EXTRACT IT FIRST
4. Then import and use in new component

## Current Active Work

- Steam dialog detection via OmniParser
- Timeline events with countdown display
- Process detection with configurable timeout
- Service Manager optimizations complete

## Recent Changes

| Date | Service | Change |
|------|---------|--------|
| 2026-01-05 | Service Manager | Complete process_manager.py rewrite (1050+ lines) |
| 2026-01-05 | Service Manager | ProcessState enum, ProcessWrapper class with state machine |
| 2026-01-05 | Service Manager | QTcpSocket async health checks (non-blocking) |
| 2026-01-05 | Service Manager | taskkill /F /T for process tree termination (port busy fix) |
| 2026-01-05 | Service Manager | Dependency-aware startup (waits for health checks) |
| 2026-01-05 | Service Manager | Timer consolidation, log batching, health_path config |
| 2026-01-05 | OmniParser | Added --no-reload flag for visible request logs |
| 2024-12-31 | Gemma Backend | Added Steam dialog detection via OmniParser |
| 2024-12-31 | Gemma Backend | Added GAME_PROCESS_WAITING/DETECTED events |
| 2024-12-31 | Timeline | Added countdown metadata to events |
