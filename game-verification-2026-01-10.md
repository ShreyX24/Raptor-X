# Game Verification Log - 2026-01-10

Testing all 12 games individually (excluding CS2 and DOTA2).

## Test Environment
- **SUT**: ZEL-X4 (6 games), then switch to new SUT (remaining 6)
- **Backend Version**: Latest
- **Date**: 2026-01-10

## Phase 1: ZEL-X4 (6 games available)
1. AC Mirage
2. Cyberpunk 2077
3. F1 24
4. Far Cry 6
5. Shadow of the Tomb Raider
6. Sid Meier's Civ 6

## Phase 2: New SUT (6 remaining games)
1. Black Myth Wukong
2. FF XIV Dawntrail
3. Hitman 3
4. Horizon Zero Dawn Remastered
5. Red Dead Redemption 2
6. Tiny Tina's Wonderlands

---

## 1. Assassin's Creed Mirage (ac-mirage)
**Status**: FAILED
**Result**: Run failed - SUT Client 500 error on /launch

### Issues Found
- **Root Cause**: `500 Server Error: INTERNAL SERVER ERROR for url: http://192.168.0.109:8080/launch`
- SUT Client crashed when trying to launch the game
- SUT health check shows "healthy" after failure (transient issue)

### Notes
- Steam account switching worked (arlrauto)
- Preset sync completed
- Failed at game launch step
- Need to check SUT Client logs for detailed error

---

## 2. Black Myth Wukong (black-myth-wukong)
**Status**: Pending
**Result**:

### Issues Found
-

### Notes
-

---

## 3. Cyberpunk 2077 (cyberpunk-2077)
**Status**: SUCCESS
**Result**: 1/1 iterations completed successfully

### Issues Found
- None

### Notes
- All 12 steps completed
- Benchmark ran successfully
- Steam account switching worked (arlrauto)
- **User Note**: Consider running game using .exe file - use Steam to locate exe and launch from there

---

## 4. F1 24 (f1-24)
**Status**: SUCCESS
**Result**: 1/1 iterations completed successfully

### Issues Found
1. **Initial attempts failed** due to Steam Remote Play dialog (account busy) - added `remote_play` dialog handler
2. **Controller dialog** appeared - added `controller_required` dialog handler
3. **Process detection timeout** - game needed more startup wait time

### Notes
- Game has longer startup time than default
- Steam dialogs (Remote Play, Controller Required) now handled
- **Resolution**: Increased startup wait resolved process detection issue

---

## 5. Far Cry 6 (far-cry-6)
**Status**: SKIPPED
**Result**: Skipped for now

### Issues Found
- N/A

### Notes
- Will test on new SUT later

---

## 6. Final Fantasy XIV Dawntrail (final-fantasy-xiv-dawntrail)
**Status**: Pending
**Result**:

### Issues Found
-

### Notes
-

---

## 7. Hitman 3 (hitman-3)
**Status**: Pending
**Result**:

### Issues Found
-

### Notes
-

---

## 8. Horizon Zero Dawn Remastered (horizon-zero-dawn-remastered)
**Status**: Pending
**Result**:

### Issues Found
-

### Notes
-

---

## 9. Red Dead Redemption 2 (red-dead-redemption-2)
**Status**: Pending
**Result**:

### Issues Found
-

### Notes
-

---

## 10. Shadow of the Tomb Raider (shadow-of-the-tomb-raider)
**Status**: FAILED
**Result**: Run failed (from disk manifest)

### Issues Found
- Run completed but failed (need to check logs for details)

### Notes
- Data saved to disk but not showing in API due to history pruning bug

---

## 11. Sid Meier's Civilization 6 (sid-meier-civ-6)
**Status**: SUCCESS
**Result**: 1/1 iterations completed successfully (from disk manifest)

### Issues Found
- None

### Notes
- Data saved to disk but not showing in API due to history pruning bug

---

## 12. Tiny Tina's Wonderlands (tiny-tina-wonderlands)
**Status**: Pending
**Result**:

### Issues Found
-

### Notes
-

---

## Summary

| # | Game | Status | Result | Issues |
|---|------|--------|--------|--------|
| 1 | AC Mirage | FAILED | SUT 500 error | SUT Client issue |
| 2 | Black Myth Wukong | Pending | - | On new SUT |
| 3 | Cyberpunk 2077 | SUCCESS | 1/1 | None |
| 4 | F1 24 | SUCCESS | 1/1 | Startup wait needed |
| 5 | Far Cry 6 | SKIPPED | - | Will test on new SUT |
| 6 | FF XIV Dawntrail | Pending | - | On new SUT |
| 7 | Hitman 3 | Pending | - | On new SUT |
| 8 | Horizon Zero Dawn | Pending | - | On new SUT |
| 9 | RDR2 | Pending | - | On new SUT |
| 10 | Shadow of Tomb Raider | FAILED | Failed | Need to check logs |
| 11 | Civ 6 | SUCCESS | 1/1 | None (from disk) |
| 12 | Tiny Tina's | Pending | - | On new SUT |

## Action Items
_Issues to fix after testing:_

1. **CRITICAL: History Pruning Bug** in `run_manager.py:741-742`
   - `run_history[-100:]` removes NEWEST runs when history > 100
   - Should be `run_history[:100]` to keep newest 100

2. AC Mirage: Investigate SUT Client 500 error on /launch
3. Shadow of Tomb Raider: Check failure logs
