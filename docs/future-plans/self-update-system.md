# Self-Update System

## Overview

Implement a self-updating mechanism for RPX that allows all components (SUT client, backend, frontend, services) to automatically check for updates from GitHub and update themselves without manual intervention.

## Components to Update

1. **SUT Client** (`sut_client/`)
   - Runs on remote SUT machines
   - Most critical for self-update (manual updates are tedious)

2. **Main RPX System** (entire `RPX/` root)
   - Gemma Backend
   - Gemma Frontend (Admin Dashboard)
   - Preset Manager
   - Queue Service
   - SUT Discovery Service
   - Service Manager
   - Configuration files

## Architecture

### Update Flow

```
┌─────────────────────────────────────────────────────────────┐
│                     GitHub (main branch)                     │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ git fetch / compare
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     Update Checker Service                   │
│  - Runs periodically (configurable: 2-3x per day)           │
│  - Compares local commit hash with remote                   │
│  - Notifies user if updates available                       │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ User approves update
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     Update Executor                          │
│  - Stops running services                                   │
│  - git pull origin main                                     │
│  - pip install -e . (for Python packages)                   │
│  - npm install (for frontend)                               │
│  - Restarts services                                        │
└─────────────────────────────────────────────────────────────┘
```

## Configuration

### Settings File (`~/.rpx/update-config.json`)

```json
{
  "auto_check": true,
  "check_interval_hours": 8,
  "check_times": ["09:00", "14:00", "20:00"],
  "auto_update": false,
  "notify_only": true,
  "github_repo": "owner/rpx",
  "branch": "main",
  "components": {
    "sut_client": true,
    "backend": true,
    "frontend": true,
    "preset_manager": true,
    "queue_service": true,
    "sut_discovery": true,
    "service_manager": true
  }
}
```

## Implementation Details

### 1. SUT Client Self-Update

**New CLI Commands:**
```bash
# Check for updates
sut-client --check-updates

# Update now
sut-client --update

# Enable/disable auto-update
sut-client --auto-update on
sut-client --auto-update off
```

**Update Process:**
1. Check if git repo exists and is clean
2. Fetch latest from origin/main
3. Compare local HEAD with remote HEAD
4. If different:
   - Notify user (toast notification on Windows)
   - If auto-update enabled OR user approves:
     - Stop SUT client service
     - `git pull origin main`
     - `pip install -e .`
     - Restart via scheduled task

**Code Location:** `sut_client/src/sut_client/updater.py`

```python
class SelfUpdater:
    def __init__(self, repo_path: str, branch: str = "main"):
        self.repo_path = repo_path
        self.branch = branch

    def check_for_updates(self) -> tuple[bool, str]:
        """Check if updates are available.
        Returns: (has_updates, latest_commit_message)
        """
        pass

    def get_changelog(self, since_commit: str) -> list[str]:
        """Get commit messages since given commit."""
        pass

    def update(self, restart: bool = True) -> bool:
        """Pull latest and reinstall."""
        pass
```

### 2. Main RPX System Update

**Service Manager Integration:**
- Add "Check for Updates" button in Service Manager GUI
- Show notification badge when updates available
- Update all services in correct dependency order

**Update Process:**
1. Stop all services (in reverse dependency order)
2. `git pull origin main`
3. For each Python service: `pip install -e .`
4. For frontend: `npm install`
5. Restart all services (in dependency order)

**Code Location:** `service_manager/src/service_manager/updater.py`

### 3. Background Update Checker

**Implementation Options:**

A. **Windows Task Scheduler** (Preferred for SUT)
   - Create scheduled task that runs check periodically
   - Shows Windows toast notification if updates available

B. **Background Thread** (For Service Manager)
   - Thread that sleeps and checks periodically
   - Updates status bar in GUI

### 4. Notification System

**Windows Toast Notifications:**
```python
from win10toast import ToastNotifier

def notify_update_available(version: str, changes: list[str]):
    toaster = ToastNotifier()
    toaster.show_toast(
        "RPX Update Available",
        f"Version {version} is ready to install.\n{len(changes)} new changes.",
        duration=10,
        callback_on_click=lambda: open_update_dialog()
    )
```

**Service Manager GUI:**
- Status bar message: "Update available (v1.2.3)"
- Notification icon with badge
- Modal dialog with changelog

## Safety Considerations

1. **Backup Before Update**
   - Create backup of current state before pulling
   - Allow rollback if update fails

2. **Clean Git State Required**
   - Don't update if there are uncommitted changes
   - Warn user to commit or stash changes first

3. **Graceful Service Shutdown**
   - Wait for running automations to complete
   - Or warn user about active runs

4. **Version Compatibility**
   - Check if update requires database migrations
   - Check if config file format changed

5. **Network Failure Handling**
   - Timeout for git fetch
   - Retry logic for transient failures

## User Experience

### SUT Client Update Flow

```
[Background check detects update]
     │
     ▼
┌─────────────────────────────────┐
│  Windows Toast Notification      │
│  "RPX SUT Client Update"         │
│  "New version available"         │
│  [Click to update]               │
└─────────────────────────────────┘
     │
     │ User clicks
     ▼
┌─────────────────────────────────┐
│  Update Dialog                   │
│                                  │
│  Changes:                        │
│  - Fixed screenshot retry bug    │
│  - Added EULA dialog handling    │
│  - Improved focus management     │
│                                  │
│  [Update Now]  [Later]  [Skip]   │
└─────────────────────────────────┘
     │
     │ User clicks "Update Now"
     ▼
┌─────────────────────────────────┐
│  Updating...                     │
│  [████████░░░░░░░░] 50%          │
│  Pulling latest changes...       │
└─────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────┐
│  Update Complete!                │
│  SUT Client will restart now.    │
│  [OK]                            │
└─────────────────────────────────┘
```

### Service Manager Update Flow

```
[Menu Bar]
File  View  Services  Help
                       │
                       ├─ Check for Updates
                       ├─ Auto-Update Settings...
                       └─ About
```

## Dependencies

```
# For Windows toast notifications
pip install win10toast

# For git operations (already available via subprocess)
# git must be installed on the system
```

## Milestones

### Phase 1: Manual Update Check (MVP)
- [ ] Add `--check-updates` to SUT client
- [ ] Add `--update` to SUT client
- [ ] Basic git pull + pip install

### Phase 2: Automatic Checking
- [ ] Background update checker thread
- [ ] Windows toast notifications
- [ ] Configurable check intervals

### Phase 3: Service Manager Integration
- [ ] Update checker in Service Manager
- [ ] GUI for update settings
- [ ] Coordinated service restart

### Phase 4: Polish
- [ ] Changelog display
- [ ] Rollback capability
- [ ] Update history log

## Related Files

- `sut_client/src/sut_client/updater.py` (to be created)
- `service_manager/src/service_manager/updater.py` (to be created)
- `~/.rpx/update-config.json` (runtime config)

## Notes

- Git must be installed on all machines
- SSH keys or credentials needed for private repos
- Consider rate limiting GitHub API calls
- May need to handle merge conflicts gracefully
