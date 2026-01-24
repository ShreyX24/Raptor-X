# Game Menu FSM (Finite State Machine)

## Status: Pending

## Overview

Add partial FSM (Finite State Machine) for each game's menu system. By mapping out the entire menu structure (each option and what it leads to), the automation can understand where it currently is and navigate to where it needs to go.

---

## Problem

**Current approach**: Linear step sequence
- Steps are executed in order
- No understanding of menu state
- Fails if game is in unexpected state
- Can't recover from navigation errors

**Example failure**:
1. Automation expects "Main Menu"
2. Game shows "Settings > Graphics" (from previous run)
3. Automation clicks expecting "Settings" button
4. Clicks wrong element, run fails

---

## Solution: Menu State Machine

Map each game's menu as a graph where:
- **Nodes** = Menu screens/states
- **Edges** = Actions to transition between states

```
┌──────────────────────────────────────────────────────────────────┐
│                    Far Cry 6 Menu FSM                             │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│    ┌─────────┐      Press Enter      ┌─────────────┐            │
│    │  Intro  │ ─────────────────────→│  Main Menu  │            │
│    │ Screen  │                       │             │            │
│    └─────────┘                       └──────┬──────┘            │
│                                            │                    │
│                    ┌───────────────────────┼───────────────┐    │
│                    │                       │               │    │
│                    ▼                       ▼               ▼    │
│            ┌─────────────┐         ┌─────────────┐  ┌─────────┐ │
│            │  Continue   │         │   Options   │  │  Exit   │ │
│            │   Game      │         │             │  │  Game   │ │
│            └─────────────┘         └──────┬──────┘  └─────────┘ │
│                                          │                      │
│                    ┌─────────────────────┼─────────────────┐    │
│                    │                     │                 │    │
│                    ▼                     ▼                 ▼    │
│            ┌─────────────┐       ┌─────────────┐   ┌──────────┐ │
│            │   Video     │       │   Audio     │   │ Controls │ │
│            │  Settings   │       │  Settings   │   │          │ │
│            └──────┬──────┘       └─────────────┘   └──────────┘ │
│                   │                                             │
│                   ▼                                             │
│            ┌─────────────┐                                      │
│            │  Benchmark  │                                      │
│            │             │                                      │
│            └─────────────┘                                      │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

---

## Benefits

### 1. State Awareness
- Know exactly where the game is at any moment
- Detect unexpected states via OmniParser

### 2. Dynamic Navigation
- Calculate shortest path from current → target state
- Re-route if something goes wrong

### 3. Recovery
- If lost, navigate back to known state (Main Menu)
- Retry navigation from clean state

### 4. Flexibility
- Same FSM works for different automation goals
- "Go to Graphics Settings" works from any starting point

---

## Data Structure

### Menu State Definition

```yaml
# config/games/far-cry-6-fsm.yaml
name: far-cry-6
states:
  intro_screen:
    identifiers:
      - text: "Press any key"
      - text: "Press Enter"
    transitions:
      main_menu:
        action: key
        value: enter
        expected_delay: 2

  main_menu:
    identifiers:
      - text: "Continue"
      - text: "New Game"
      - text: "Options"
    transitions:
      continue_game:
        action: click
        target: "Continue"
      options:
        action: click
        target: "Options"
      exit_game:
        action: click
        target: "Exit"

  options:
    identifiers:
      - text: "Video"
      - text: "Audio"
      - text: "Controls"
    back_to: main_menu
    back_action:
      action: key
      value: escape
    transitions:
      video_settings:
        action: click
        target: "Video"
      audio_settings:
        action: click
        target: "Audio"

  video_settings:
    identifiers:
      - text: "Resolution"
      - text: "Quality"
      - text: "Benchmark"
    back_to: options
    transitions:
      benchmark:
        action: click
        target: "Benchmark"
```

### Python Implementation

```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class MenuState:
    name: str
    identifiers: list[dict]  # Text/icons that identify this state
    transitions: dict[str, dict]  # state_name -> action
    back_to: Optional[str] = None
    back_action: Optional[dict] = None

class GameMenuFSM:
    def __init__(self, game_name: str):
        self.game_name = game_name
        self.states: dict[str, MenuState] = {}
        self.current_state: Optional[str] = None

    def load_from_yaml(self, path: str):
        """Load FSM definition from YAML file."""
        pass

    def detect_current_state(self, parsed_screen: dict) -> Optional[str]:
        """Use OmniParser results to determine current menu state."""
        for state_name, state in self.states.items():
            if self._matches_identifiers(parsed_screen, state.identifiers):
                return state_name
        return None

    def get_path_to(self, target_state: str) -> list[tuple[str, dict]]:
        """Calculate action sequence from current state to target.
        Returns: [(state_name, action), ...]
        """
        # BFS/Dijkstra through state graph
        pass

    def navigate_to(self, target_state: str) -> bool:
        """Execute navigation to target state with verification."""
        path = self.get_path_to(target_state)
        for state_name, action in path:
            self._execute_action(action)
            # Verify we reached expected state
            if not self._verify_state(state_name):
                return self._recover_and_retry(target_state)
        return True
```

---

## Integration with Automation

### Current Flow (Linear)
```python
for step in game_config["steps"]:
    execute_step(step)  # Fails if unexpected state
```

### New Flow (FSM-aware)
```python
fsm = GameMenuFSM(game_name)
fsm.load_from_yaml(f"config/games/{game_name}-fsm.yaml")

# Detect where we are
fsm.current_state = fsm.detect_current_state(parse_screen())

# Navigate to target
if not fsm.navigate_to("video_settings"):
    raise NavigationError("Could not reach video settings")

# Now execute benchmark-specific steps
execute_benchmark_steps()
```

---

## Implementation Phases

### Phase 1: FSM Data Structure
- [ ] Define YAML schema for FSM
- [ ] Create FSM loader
- [ ] State detection using OmniParser
- [ ] Create FSM for one game (Far Cry 6)

### Phase 2: Navigation
- [ ] Path finding algorithm (BFS)
- [ ] Action execution
- [ ] State verification after each transition
- [ ] Basic recovery (back to main menu)

### Phase 3: Integration
- [ ] Modify automation_orchestrator to use FSM
- [ ] Fallback to linear steps if no FSM defined
- [ ] Timeline events for FSM transitions

### Phase 4: Expansion
- [ ] Create FSMs for all supported games
- [ ] Visual FSM editor in frontend (optional)
- [ ] Learn FSM from successful runs (ML - future)

---

## Game-Specific Considerations

| Game | Menu Complexity | Notes |
|------|-----------------|-------|
| Far Cry 6 | Medium | Standard Ubisoft menu |
| Hitman 3 | High | Multiple sub-menus, location select |
| Cyberpunk 2077 | Medium | Settings nested deeply |
| F1 24 | Low | Simple options menu |
| AC Mirage | Medium | Similar to FC6 |

---

## Related

- See [automation-sequence.md](./automation-sequence.md) for current linear flow
- OmniParser provides the screen parsing for state detection
