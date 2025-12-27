# Gemma E2E Documentation

> **Last Updated:** 2025-12-27

## Folder Structure

```
doc/
├── README.md                          # This file
├── knowledge-base/
│   └── per-game-fixes/
│       └── game-automation-fixes.md   # Per-game automation fixes & patterns
└── plans/
    ├── README.md                      # Plan index
    ├── steam-account-pool-and-ocr-config.md
    ├── queue-service-multi-server-omniparser.md
    ├── omniparser-server-management.md
    ├── gemma-frontend-control-center.md
    ├── service-manager-dashboard-omniparser.md
    ├── service-manager-gui-initial.md
    └── gemma-preset-manager-integration.md
```

## Documentation Categories

### Knowledge Base (`knowledge-base/`)
Accumulated knowledge from debugging and fixing issues:
- **per-game-fixes/** - Game-specific automation fixes, OCR configs, timing adjustments

### Plans (`plans/`)
Implementation plans for major features:
- Architecture diagrams
- File-by-file changes
- Data flow descriptions
- Status tracking

## Quick Links

| Document | Description |
|----------|-------------|
| [Game Automation Fixes](./knowledge-base/per-game-fixes/game-automation-fixes.md) | Per-game fixes, patterns, and lessons learned |
| [Plans Index](./plans/README.md) | All implementation plans with status |

## Contributing

When adding new documentation:

1. **Knowledge Base** - For debugging insights, patterns, best practices
2. **Plans** - For multi-file feature implementations
3. **Update this README** if adding new categories
