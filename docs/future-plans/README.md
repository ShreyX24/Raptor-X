# Future Plans

This folder contains documentation for planned features and improvements for Raptor X Mission Control.

## Documents

| Document | Description | Priority | Status |
|----------|-------------|----------|--------|
| [automation-sequence.md](./automation-sequence.md) | Full automation pipeline walkthrough | High | Reference |
| [self-update-system.md](./self-update-system.md) | Self-updating mechanism for all RPX components | High | Pending |
| [run-scheduling.md](./run-scheduling.md) | Run scheduling, queueing, and reordering | High | Pending |
| [temp-steam-accounts.md](./temp-steam-accounts.md) | Temporary Steam account with Steam Guard support | Medium | Pending |
| [game-menu-fsm.md](./game-menu-fsm.md) | Finite State Machine for game menu navigation | Medium | Pending |
| [ui-animations.md](./ui-animations.md) | Motion/Framer animation patterns for frontend | Low | Pending |
| [ssh-automation.md](./ssh-automation.md) | SSH setup for automated SUT deployment | Medium | Pending |

---

## Planned Features Summary

### High Priority

#### Self-Update System
- Auto-update from GitHub for SUT client and main RPX system
- Periodic checks (configurable: 2-3x per day)
- User confirmation before updating
- Toast notifications on Windows
- See [self-update-system.md](./self-update-system.md)

#### Run Scheduling & Queue
- Schedule runs on busy SUTs (execute when available)
- Schedule runs for future time or event triggers
- Spotify-style "Add to Queue" functionality
- Drag-and-drop reordering of queued runs
- See [run-scheduling.md](./run-scheduling.md)

### Medium Priority

#### Temporary Steam Accounts
- Support for personal/temp Steam accounts with Steam Guard
- Interactive code entry in frontend
- QR code display for Steam mobile scan
- Account types: managed vs personal
- See [temp-steam-accounts.md](./temp-steam-accounts.md)

#### Game Menu FSM
- Map game menus as state machines
- Dynamic navigation from any starting point
- Recovery from unexpected states
- See [game-menu-fsm.md](./game-menu-fsm.md)

#### SSH Automation
- Passwordless SSH to SUTs
- Automated deployment and log collection
- See [ssh-automation.md](./ssh-automation.md)

### Low Priority

#### UI Animations
- Motion library integration
- Number animations, transitions, drag-drop
- See [ui-animations.md](./ui-animations.md)

---

## Additional Planned Items

### Infrastructure
- [ ] Copy tracing packages from master to SUT if unavailable
- [ ] Remote log pulling via OpenSSH
- [ ] Driver installation automation
- [ ] MEINFO tool integration (`C:\OWR\CSME\External\Tools\System_Tools\MEInfo`)

### Frontend Enhancements
- [ ] About Page with automation sequence diagram
- [ ] Run Timeline Tooltips - step-by-step explanations
- [ ] Progress Indicator - real-time step matching

### Backend Improvements
- [ ] Results Collection - auto-collect benchmark results from SUTs
- [ ] Multi-SUT Campaigns - run same campaign across multiple SUTs in parallel
- [ ] Hitman 3 benchmark results extraction (`%userprofile%/hitman/profiledata.txt`)

### Documentation
- [ ] Game Config Guide - how to create YAML configs for new games
- [ ] Troubleshooting Guide - common issues and solutions

---

## Completed Features

- [x] 4 resolutions across 4 graphics presets
- [x] Change Windows resolution
- [x] Disable start automation until frontend receives all SUT info
- [x] Single, batch, campaign run modes
- [x] "No Steam Login" feature (`skip_steam_login`) for pre-logged accounts

---

## Related Documentation

- `docs/plans/` - Implementation plans and roadmaps
- `docs/knowledge-base/` - Architecture learnings and per-game fixes
- `.claude/LEARNINGS.md` - Dos and don'ts discovered during development
