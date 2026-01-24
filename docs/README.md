# Raptor X (RPX) Documentation

> **Last Updated:** 2026-01-24

## Folder Structure

```
docs/
├── README.md                          # This file
├── plan.md                            # Current active work plan
├── future-plans/                      # Planned features (not yet implemented)
│   ├── README.md                      # Feature index with priorities
│   ├── automation-sequence.md         # Full automation pipeline reference
│   ├── self-update-system.md          # Auto-update mechanism
│   ├── run-scheduling.md              # Run scheduling & queue
│   ├── temp-steam-accounts.md         # Steam Guard support
│   ├── game-menu-fsm.md               # Menu navigation FSM
│   ├── ssh-automation.md              # SSH deployment automation
│   └── ui-animations.md               # Frontend motion animations
├── plans/                             # Implementation plans (historical)
│   ├── README.md                      # Plan index with status
│   ├── gemma-roadmap-2025.md          # Development priorities
│   ├── gemma-frontend-control-center.md
│   ├── gemma-preset-manager-integration.md
│   ├── omniparser-server-management.md
│   ├── performance-extraction-intel-tracing.md
│   ├── queue-service-multi-server-omniparser.md
│   ├── run-logging-structure.md
│   ├── service-manager-dashboard-omniparser.md
│   ├── service-manager-gui-initial.md
│   └── steam-account-pool-and-ocr-config.md
└── knowledge-base/                    # Learnings & reference
    ├── architecture-learnings.md      # Architectural decisions
    └── per-game-fixes/
        └── game-automation-fixes.md   # Per-game automation fixes
```

## Documentation Categories

### Future Plans (`future-plans/`)
Planned features not yet implemented:
- Feature specifications
- Priority levels (High/Medium/Low)
- Implementation approach

See [future-plans/README.md](./future-plans/README.md) for the full index.

### Implementation Plans (`plans/`)
Historical implementation plans for major features:
- Architecture diagrams
- File-by-file changes
- Data flow descriptions
- Status tracking (Done/Partial/Pending)

See [plans/README.md](./plans/README.md) for status of all plans.

### Knowledge Base (`knowledge-base/`)
Accumulated knowledge from debugging and development:
- **architecture-learnings.md** - Architectural decisions, patterns, SSH setup
- **per-game-fixes/** - Game-specific automation fixes, OCR configs

## Quick Links

| Document | Description |
|----------|-------------|
| [Future Plans Index](./future-plans/README.md) | Planned features with priorities |
| [Plans Index](./plans/README.md) | Implementation plans with status |
| [Architecture Learnings](./knowledge-base/architecture-learnings.md) | Key architectural decisions |
| [Game Automation Fixes](./knowledge-base/per-game-fixes/game-automation-fixes.md) | Per-game fixes and patterns |

## Related Documentation

- `.claude/CLAUDE.md` - Main project documentation
- `.claude/LEARNINGS.md` - Development dos and don'ts
- `.claude/rules/` - Per-service documentation

## Contributing

When adding new documentation:

1. **Future Plans** - For features not yet implemented
2. **Plans** - For multi-file feature implementations (historical reference)
3. **Knowledge Base** - For debugging insights, patterns, best practices
4. **Update this README** if adding new categories
