# Future Plans

This folder contains documentation for planned features and improvements for Raptor X Mission Control.

## Documents

| Document | Description | Priority |
|----------|-------------|----------|
| [automation-sequence.md](./automation-sequence.md) | Full automation pipeline walkthrough - to be displayed in About/Help page | High |
| [self-update-system.md](./self-update-system.md) | Self-updating mechanism for all RPX components | High |

## Planned Features

### Infrastructure
- [ ] **Self-Update System** - Auto-update from GitHub for SUT client and main RPX system
  - Periodic checks (configurable: 2-3x per day)
  - Pull from main branch
  - User confirmation before updating
  - Toast notifications on Windows
  - See [self-update-system.md](./self-update-system.md) for full design

### Frontend Enhancements
- [ ] **About Page** - Display automation sequence with visual diagram
- [ ] **Run Timeline Tooltips** - Step-by-step explanations during runs
- [ ] **Progress Indicator** - Real-time matching of automation steps

### Backend Improvements
- [ ] **Results Collection** - Auto-collect benchmark results from SUTs
- [ ] **Multi-SUT Campaigns** - Run same campaign across multiple SUTs in parallel

### Documentation
- [ ] **Game Config Guide** - How to create YAML configs for new games
- [ ] **Troubleshooting Guide** - Common issues and solutions
