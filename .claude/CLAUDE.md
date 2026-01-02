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

## Current Active Work

- Steam dialog detection via OmniParser
- Timeline events with countdown display
- Process detection with configurable timeout

## Recent Changes

| Date | Service | Change |
|------|---------|--------|
| 2024-12-31 | Gemma Backend | Added Steam dialog detection via OmniParser |
| 2024-12-31 | Gemma Backend | Added GAME_PROCESS_WAITING/DETECTED events |
| 2024-12-31 | Timeline | Added countdown metadata to events |
