# Game Automation Fixes - Knowledge Base

> **Last Updated:** 2025-12-28
> **Purpose:** Document fixes applied to each game for E2E automation. Use this as reference for Workflow Builder and future game configs.

---

## Table of Contents
- [Framework-Level Changes](#framework-level-changes)
- [Per-Game Fixes](#per-game-fixes)
  - [Black Myth: Wukong](#1-black-myth-wukong-bmw)
  - [Shadow of the Tomb Raider](#2-shadow-of-the-tomb-raider-sotr)
  - [HITMAN 3](#3-hitman-3)
  - [Tiny Tina Wonderlands](#4-tiny-tina-wonderlands)
  - [Horizon Zero Dawn Remastered](#5-horizon-zero-dawn-remastered)
  - [Civilization VI](#6-civilization-vi)
  - [Far Cry 6](#7-far-cry-6)
  - [F1 24](#8-f1-24)
  - [Red Dead Redemption 2](#9-red-dead-redemption-2)
- [Common Patterns & Lessons](#common-patterns--lessons)

---

## Framework-Level Changes

These changes apply across all games and improve overall reliability.

### SUT Client Improvements

| Change | Description | Commit |
|--------|-------------|--------|
| Waitress WSGI Server | Replaced Flask dev server with 8-thread Waitress for concurrent screenshot + control requests | `11f4387` |
| Repeat Key Support | Added `count` + `interval` parameters for multiple key presses with delay | Session fix |
| Key Press Duration | Increased from 50ms to 100ms for better game compatibility | Session fix |
| Auto Firewall Rules | Creates Windows firewall rule on startup for remote access | `11f4387` |

### OmniParser & OCR Improvements

| Change | Description | Commit |
|--------|-------------|--------|
| Per-Request OCR Config | Each request can specify: `box_threshold`, `use_paddleocr`, `text_threshold`, etc. | `815f7b0` |
| OCR Fallback System | Automatically tries 4 fallback configs when target text not found | `815f7b0` |
| Multi-Text Matching | OR logic for text variations: `["Wukong", "WUKONG", "WUKONO"]` | `875b07e` |
| Multi-Server Support | Round-robin load balancing across multiple OmniParser instances | `c95aa04` |
| Empty Detection Handler | Returns empty results gracefully when no UI elements detected (fixes black screenshot crash) | Session fix |

### Automation Framework

| Change | Description | Commit |
|--------|-------------|--------|
| Per-Game OCR Config | `metadata.ocr_config` for game-level OCR defaults | `815f7b0` |
| Per-Step OCR Config | Override OCR settings at individual step level | `815f7b0` |
| Scroll Action Support | `type: scroll` with `direction` and `clicks` count | `815f7b0` |
| Conditional Wait | Wait for element with `condition: element_appears` | Session fix |
| Optional Steps | `optional: true` for steps that may not always appear | `11f4387` |
| Launch Args Support | `metadata.launch_args` for command-line game arguments | Session fix |

### Game Launch Improvements

| Change | Description | Commit |
|--------|-------------|--------|
| Launch Args in YAML | `launch_args: "-benchmark test.xml"` passes CLI args to game | Session fix |
| Steam CLI Launch | When `launch_args` provided with Steam app, uses `steam.exe -applaunch <appid> <args>` | Session fix |
| DRM-Safe Launch | Steam CLI method properly handles DRM (direct exe launch fails for DRM games) | Session fix |

---

## Per-Game Fixes

### 1. Black Myth: Wukong (BMW)

**Config File:** `black-myth-wukong.yaml`
**Status:** Working
**Commit:** `875b07e`

#### Issues & Fixes

| Issue | Root Cause | Fix |
|-------|-----------|-----|
| "Wukong" text not detected | OCR returns variations like "WUKONO" | Multi-text array: `["Wukong", "WUKONG", "WUKONO", "BLACK"]` |
| Slow startup detection | Initial wait too long | Reduced `startup_wait` from 80s → 50s |
| Step 9 quit confirmation fails | Text mismatch between "quit to desktop" variations | Multi-text: `["quit to desktop", "quit to the desktop"]` |
| Verification failures | Type "icon" too restrictive | Changed verify type from `"icon"` → `"any"` |
| Process not found | Full exe name not matching | Substring match: `b1` finds `b1-Win64-Shipping.exe` |

#### Key Config Settings
```yaml
metadata:
  startup_wait: 50
  process_id: "b1"  # Substring match

steps:
  6:
    verify_success:
      - type: "any"
        text: ["Wukong", "WUKONG", "WUKONO", "BLACK"]
        text_match: "contains"
  9:
    find:
      text: ["quit to desktop", "quit to the desktop"]
```

---

### 2. Shadow of the Tomb Raider (SOTR)

**Config File:** `shadow-of-the-tomb-raider.yaml`
**Status:** Working
**Commit:** `11f4387`

#### Issues & Fixes

| Issue | Root Cause | Fix |
|-------|-----------|-----|
| CONTINUE button sometimes appears | Save game state varies | Added `optional: true` step for CONTINUE |
| Wrong menu flow | Original config skipped steps | Updated: Play → CONTINUE → OPTIONS → DISPLAY → RUN BENCHMARK |
| Process detection fails | Full name not found | Changed to substring: `sottr` |
| Benchmark not completing | Wait too short | Set duration to 210s |

#### Key Config Settings
```yaml
metadata:
  startup_wait: 15
  process_id: sottr  # Substring match

steps:
  2:
    description: "click continue to enter game (optional)"
    find:
      text: CONTINUE
    optional: true  # Key: doesn't fail if not found
```

---

### 3. HITMAN 3

**Config File:** `hitman-3.yaml`
**Status:** Working
**Commit:** `815f7b0`

#### Issues & Fixes

| Issue | Root Cause | Fix |
|-------|-----------|-----|
| Stylized fonts not recognized | PaddleOCR can't read artistic fonts | Switched to EasyOCR: `use_paddleocr: false` |
| Low text confidence | Threshold too high for stylized text | Lowered `text_threshold: 0.6` |
| Inconsistent OCR results | No retry mechanism | Enabled `use_ocr_fallback: true` |
| Benchmark option below viewport | Need to scroll to see it | Added scroll action: `direction: down, clicks: 5` |

#### Key Config Settings
```yaml
metadata:
  use_ocr_fallback: true
  ocr_config:
    use_paddleocr: false  # EasyOCR for stylized fonts
    text_threshold: 0.6

steps:
  2:
    description: "Scroll down to benchmark option"
    find:
      text: "Ray Tracing"  # Scroll anchor
    action:
      type: scroll
      direction: down
      clicks: 5
    verify_success:
      - text: "Start Benchmark"
```

---

### 4. Tiny Tina Wonderlands

**Config File:** `tiny-tina-wonderlands.yaml`
**Status:** Working

#### Issues & Fixes

| Issue | Root Cause | Fix |
|-------|-----------|-----|
| Very slow game load | UE4 shader compilation | Set `startup_wait: 100s` |
| Benchmark menu hard to find | Icon-based menu | Find by "Tent" icon text |
| Post-benchmark stuck | Need to re-navigate | Re-enter OPTIONS → Tent → ESC → EXIT GAME |
| Process detection | Need exact match | Set to `Wonderlands.exe` |

#### Key Config Settings
```yaml
metadata:
  startup_wait: 100
  process_id: Wonderlands.exe

steps:
  2:
    find:
      text: Tent  # Benchmark menu icon
  7:
    action:
      type: key
      key: escape  # Return to main menu
```

---

### 5. Horizon Zero Dawn Remastered

**Config File:** `horizon-zero-dawn-remastered.yaml`
**Status:** Working

#### Issues & Fixes

| Issue | Root Cause | Fix |
|-------|-----------|-----|
| Keys not registering | Game ignores ctypes SendInput | Use `methodType: "pydirectinput"` |
| Very long initial load | Shader compilation + launcher | `startup_wait: 90s` + conditional wait up to 180s |
| Launcher blocks direct exe | Steam DRM | Launch via Steam App ID: `"2561580"` |
| Many confirmation dialogs | Complex exit flow | Back → Yes → Back → QUIT → Yes (5 steps) |

#### Key Config Settings
```yaml
metadata:
  startup_wait: 90
  path: "2561580"  # Steam App ID, not exe path
  process_id: "HorizonZeroDawnRemastered.exe"

steps:
  1:
    action:
      type: "key"
      key: "enter"
      methodType: "pydirectinput"  # Key: use DirectInput
    expected_delay: 90  # Long wait after launcher
```

---

### 6. Civilization VI

**Config File:** `sid-meier-civ-6.yaml`
**Status:** Working

#### Issues & Fixes

| Issue | Root Cause | Fix |
|-------|-----------|-----|
| Variable startup time | Different PC specs | Conditional wait for "CIVILIZATION" text (up to 180s) |
| Click not registering | Need explicit input method | Set `clickType: "ctypes"` |
| Multi-level menu | Benchmark inside submenu | Click Benchmark → CIVILIZATION → Gathering Storm AI |
| Very long benchmark | AI benchmark is slow | Set wait to 300s (5 minutes) |

#### Key Config Settings
```yaml
steps:
  1:
    description: "Conditional wait for element to appear"
    action:
      type: "wait"
      condition: "element_appears"
      max_wait: 180
      check_interval: 5
    verify_success:
      - text: "CIVILIZATION"

  2:
    action:
      type: "click"
      clickType: "ctypes"  # Explicit input method
```

---

### 7. Far Cry 6

**Config File:** `far-cry-6.yaml`
**Status:** Working
**Fixed:** 2025-12-27

#### Issues & Fixes

| Issue | Root Cause | Fix |
|-------|-----------|-----|
| Automation starts during credits | Unskippable intro sequence | Increased `startup_wait: 180s` |
| Process not detected | Window title has ® symbol | Use exe name `FarCry6.exe` not window title |
| ESC key unreliable | Game input handling | Replaced ALL key presses with clicks |
| Verification during loading | Loading screen has minimal UI | Increased `expected_delay: 5s` after Exit Benchmark |
| Wrong screen after transition | Verified element exists on both screens | Verify for "OPTIONS" (unique to options menu) |
| Fallback triggers loop | ESC behavior unpredictable | Fallback: click "BACK" instead of ESC key |

#### Key Config Settings
```yaml
metadata:
  startup_wait: 180  # Long unskippable credits
  process_id: "FarCry6.exe"  # Not window title

steps:
  4:
    find:
      text: "Exit Benchmark"
    verify_success:
      - text: "OPTIONS"  # Unique to options menu
    expected_delay: 5  # Wait for loading transition

fallbacks:
  general:
    action: "click"  # Click, not key press
    find:
      text: "BACK"
```

---

### 8. F1 24

**Config File:** `f1-24.yaml`
**Status:** Working
**Fixed:** 2025-12-27

#### Overview
F1 24 uses a **command-line benchmark mode** instead of in-game UI navigation. The game accepts `-benchmark <config.xml>` argument to run automated benchmarks.

#### Issues & Fixes

| Issue | Root Cause | Fix |
|-------|-----------|-----|
| Need CLI benchmark mode | No in-game benchmark button - command-line only | Added `launch_args: "-benchmark example_benchmark.xml"` |
| Direct exe launch fails | EA DRM requires Steam context | Use `steam.exe -applaunch` instead of direct exe |
| Steam dialog appears | Custom launch args trigger confirmation | Added optional step to click "Continue" |
| Process name detection | Need exact match | Set `process_id: "F1_24"` |

#### Key Config Settings
```yaml
metadata:
  game_name: "F1 24"
  steam_app_id: '2488620'
  path: "2488620"  # Steam App ID
  process_id: "F1_24"
  launch_args: "-benchmark example_benchmark.xml"  # CLI benchmark mode
  startup_wait: 5  # Short - Steam dialog appears quickly
  benchmark_duration: 400  # Benchmark takes ~350s

steps:
  1:
    description: "Click Continue on Steam launch args dialog (optional)"
    find:
      type: "any"
      text: "Continue"
    action:
      type: "click"
    optional: true  # Dialog may not appear if Steam remembers choice

  2:
    description: "Wait for benchmark to complete (~350s + buffer)"
    action:
      type: "wait"
      duration: 400
```

#### Benchmark XML Configuration
The benchmark config is placed at: `<F1 24 install>/benchmark/example_benchmark.xml`

```xml
<config infinite_loop="false" hardware_settings="hardware_settings_config.xml" show_fps="false">
  <track name="silverstone" laps="3" weather="wet" num_cars="20"
         camera_mode="cycle" driver="max_verstappen" grid_pos="3" />
</config>
```

#### Launch Flow
1. Preset sync copies `example_benchmark.xml` to game's benchmark folder
2. Game launches via: `steam.exe -applaunch 2488620 -benchmark example_benchmark.xml`
3. Steam may show "Launch with custom arguments" dialog → click Continue (optional)
4. Benchmark auto-starts (Silverstone wet, 3 laps)
5. After ~350s, benchmark completes and game exits

#### Technical Implementation
Files modified for `launch_args` support:
- `sut_client/src/sut_client/launcher.py` - Steam CLI launch with args
- `sut_client/src/sut_client/service.py` - Accept `launch_args` in `/launch` endpoint
- `Gemma/modules/network.py` - Pass `launch_args` to SUT
- `Gemma/modules/game_launcher.py` - Accept `launch_args` parameter
- `Gemma/backend/core/game_manager.py` - Load `launch_args` from YAML
- `Gemma/backend/core/automation_orchestrator.py` - Pass `launch_args` to launcher

---

### 9. Red Dead Redemption 2

**Config File:** `red-dead-redemption-2.yaml`
**Status:** Working
**Fixed:** 2025-12-28

#### Overview
RDR2 uses a unique **Rockstar Games menu system** with keyboard shortcuts (Z for Settings) and hold-key interactions (hold X to activate options). Screenshots require borderless fullscreen (not exclusive fullscreen) to allow capture.

#### Issues & Fixes

| Issue | Root Cause | Fix |
|-------|-----------|-----|
| Black screenshots | Exclusive fullscreen blocks capture | Set borderless fullscreen in preset XML |
| Settings not opening | Main menu uses Z key, not click | Changed to `type: key` with `key: z` |
| GRAPHICS submenu not entering | Clicking tile only highlights it | Added step to press Enter after clicking tile |
| Benchmark not starting | Used mouse hold_click | Changed to `type: hold_key` with `key: x` for 2s |
| Exit confirmation failed | Tried clicking YES | Changed to `type: key` with `key: enter` |
| Very long startup | RDR2 shader compilation | Set `startup_wait: 90s` |

#### Key Config Settings
```yaml
metadata:
  game_name: Red Dead Redemption 2
  steam_app_id: '1174180'
  process_id: RDR2.exe
  startup_wait: 90  # Slow shader compilation
  benchmark_duration: 320

steps:
  1:
    description: Press Z to open Settings from main menu
    find:
      text: Settings
    action:
      type: key
      key: z  # RDR2 uses keyboard shortcuts

  2:
    description: Click GRAPHICS tile in settings menu
    find:
      text: GRAPHICS
    action:
      type: click
      button: left
      move_duration: 0.5
      click_delay: 0.3

  3:
    description: Press Enter to enter GRAPHICS settings
    find:
      text: GRAPHICS
    action:
      type: key
      key: enter  # Clicking just highlights, Enter enters

  4:
    description: Hold X to start Benchmark
    find:
      text: ["Run Benchmark", "BENCHMARK", "Benchmark"]
    action:
      type: hold_key
      key: x
      duration: 2.0  # RDR2 requires hold interaction

  5:
    description: Confirm benchmark start
    find:
      text: ALERT
    action:
      type: key
      key: enter

  10:
    description: Confirm exit
    find:
      text: ["YES", "Yes", "ALERT"]
    action:
      type: key
      key: enter  # Enter confirms YES option
```

#### Preset Fix (Borderless Fullscreen)
File: `preset-manager/configs/presets/red-dead-redemption-2/ppg-high-1080p/system.xml`
```xml
<!-- Use borderless fullscreen for screenshot capture -->
<windowed value="2" />  <!-- 0=exclusive fullscreen, 1=windowed, 2=borderless -->
```

#### Technical Notes
- **Menu navigation**: Z opens Settings, Enter enters submenus, X (hold) activates options
- **Confirmation dialogs**: Both benchmark start and quit use ALERT dialog with Enter to confirm
- **Screenshot capture**: Exclusive fullscreen (`windowed value="0"`) blocks Windows screenshot APIs - use borderless (`value="2"`)
- **Benchmark duration**: ~320 seconds (5.3 minutes)

---

## Common Patterns & Lessons

### 1. Startup Wait Times
Games have wildly different startup times. Document per-game:

| Game | startup_wait | Reason |
|------|-------------|--------|
| Far Cry 6 | 180s | Unskippable intro credits |
| Tiny Tina | 100s | UE4 shader compilation |
| HZD Remastered | 90s + conditional | Launcher + shaders |
| RDR2 | 90s | Rockstar launcher + shader compilation |
| BMW | 50s | Reasonable |
| SOTR | 15s | Fast |
| F1 24 | 5s | CLI benchmark mode, Steam dialog appears quickly |

### 2. Process Detection
Use substring matching for safety:
```yaml
process_id: "b1"  # Finds b1-Win64-Shipping.exe
process_id: "sottr"  # Finds sottr.exe
```

Avoid window titles with special characters (®, ™).

### 3. OCR Configuration
For stylized/artistic fonts, use EasyOCR:
```yaml
metadata:
  use_ocr_fallback: true
  ocr_config:
    use_paddleocr: false
    text_threshold: 0.6
```

### 4. Multi-Text Matching
When OCR is inconsistent, provide alternatives:
```yaml
find:
  text: ["Wukong", "WUKONG", "WUKONO", "BLACK"]
```

### 5. Click vs Key Press
**Prefer clicks over key presses** - they're more reliable:
- Far Cry 6: All clicks, no ESC
- Most games: Click for navigation, key only when required

### 6. Verification Strategy
Verify for **unique elements** on the target screen:
- Don't verify "BENCHMARK" if it exists on multiple screens
- Verify "OPTIONS" which only exists on the options menu

### 7. Loading Transitions
After actions that trigger loading:
```yaml
expected_delay: 5  # Wait for loading to complete
verify_success:
  - text: "UNIQUE_TO_NEXT_SCREEN"
```

### 8. Optional Steps
For elements that may or may not appear:
```yaml
steps:
  2:
    find:
      text: "CONTINUE"
    optional: true  # Won't fail if not found
```

---

## Adding New Games Checklist

1. **Identify process name** - Check Task Manager, use substring if needed
2. **Measure startup time** - Time from launch to main menu
3. **Map the UI flow** - Document each screen and required actions
4. **Test OCR detection** - Use OmniParser to verify text is detected
5. **Handle variations** - Add multi-text arrays for OCR inconsistencies
6. **Add verifications** - Each step should verify it reached the right screen
7. **Test fallbacks** - Ensure ESC or BACK recovers from errors
8. **Run full automation** - Test complete flow 3+ times

---

## Revision History

| Date | Changes |
|------|---------|
| 2025-12-27 | Initial document with 7 game fixes |
| 2025-12-27 | Added F1 24 CLI benchmark mode, `launch_args` framework support |
| 2025-12-28 | Added RDR2 with hold_key support, windowed mode fix, OmniParser empty detection handler |
