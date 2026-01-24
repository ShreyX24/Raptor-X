# Temporary Steam Accounts Feature

## Status: Pending
## Created: 2026-01-09

## Overview

Allow using personal/temporary Steam accounts for automation runs. These accounts may require Steam Guard authentication (code or QR), requiring user interaction during the automation flow.

---

## Problem

Current system assumes Steam accounts are:
- Pre-logged in on SUTs
- No 2FA required during automation
- Part of a managed account pool

**Reality**: Users often want to use their personal Steam accounts or temporary accounts that have Steam Guard enabled.

---

## Solution Components

### 1. Frontend Acknowledgment Dialog

Before each run with a temp account, user must confirm they will handle authentication.

```
┌─────────────────────────────────────────────────────┐
│  ⚠️ Temporary Account Selected                       │
│                                                     │
│  This run will use account: [personal_account]      │
│                                                     │
│  Steam Guard may require:                           │
│  • 6-digit code from Steam app                      │
│  • QR code scan from Steam mobile                   │
│                                                     │
│  You must be available to complete authentication   │
│  when prompted.                                     │
│                                                     │
│  ☑ I understand and will be available               │
│                                                     │
│  [Start Run]  [Cancel]                              │
└─────────────────────────────────────────────────────┘
```

---

### 2. Steam Guard Code Entry

When Steam asks for a code, show input field in frontend.

**Detection Flow**:
```
SUT Client detects Steam Guard prompt
     │
     ▼
Screenshot + OmniParser
     │
     ▼
Detect text: "Enter the code" or similar
     │
     ▼
Emit STEAM_GUARD_CODE_REQUIRED event
     │
     ▼
Frontend shows code input dialog
     │
     ▼
User enters 6-digit code
     │
     ▼
SUT Client types code into Steam
     │
     ▼
Verify login success, continue automation
```

**Frontend UI**:
```
┌─────────────────────────────────────────────────────┐
│  🔐 Steam Guard Code Required                        │
│                                                     │
│  Steam is requesting a verification code.           │
│  Check your Steam mobile app or email.              │
│                                                     │
│  Enter code: [  ][  ][  ][  ][  ][  ]               │
│                                                     │
│  ⏱ Code expires in: 0:28                             │
│                                                     │
│  [Submit]  [Cancel Run]                             │
└─────────────────────────────────────────────────────┘
```

**SUT Client Endpoints**:
```
POST /steam/detect-guard
Returns: { "guard_required": true, "type": "code" }

POST /steam/enter-code
Body: { "code": "123456" }
Returns: { "success": true }
```

---

### 3. Steam Guard QR Code Display

When Steam shows QR code for login, display in frontend for user to scan.

**Flow**:
```
SUT Client detects QR code prompt
     │
     ▼
Screenshot captures QR code
     │
     ▼
Emit STEAM_GUARD_QR_REQUIRED with screenshot
     │
     ▼
Frontend displays QR code image
     │
     ▼
User scans with Steam mobile app
     │
     ▼
SUT Client polls for login completion
     │
     ▼
Continue automation
```

**Frontend UI**:
```
┌─────────────────────────────────────────────────────┐
│  📱 Scan QR Code with Steam Mobile                   │
│                                                     │
│  ┌─────────────────────────┐                        │
│  │                         │                        │
│  │      [QR CODE IMAGE]    │                        │
│  │                         │                        │
│  └─────────────────────────┘                        │
│                                                     │
│  Open Steam mobile app → Guard → Scan QR            │
│                                                     │
│  ⏱ Waiting for scan... (polling)                    │
│                                                     │
│  [Cancel Run]                                       │
└─────────────────────────────────────────────────────┘
```

---

### 4. Account Pool Integration

Add "temp" or "personal" account type to account configuration.

**Account Config**:
```json
{
  "accounts": [
    {
      "username": "benchmark_account_1",
      "type": "managed",
      "requires_interaction": false,
      "auto_retry_on_conflict": true
    },
    {
      "username": "personal_steam",
      "type": "personal",
      "requires_interaction": true,
      "auto_retry_on_conflict": false
    }
  ]
}
```

**Behavior Differences**:

| Feature | Managed Account | Personal Account |
|---------|----------------|------------------|
| Auto-retry on conflict | Yes | No |
| Steam Guard handling | Skip (pre-authed) | Interactive |
| Account pool sharing | Yes | No (single user) |
| Requires acknowledgment | No | Yes |

---

### 5. Timeline Events

New event types for Steam Guard states:

```python
class EventType(Enum):
    # ... existing events ...

    # Steam Guard events
    STEAM_GUARD_CODE_REQUIRED = "steam_guard_code_required"
    STEAM_GUARD_QR_REQUIRED = "steam_guard_qr_required"
    STEAM_GUARD_WAITING_USER = "steam_guard_waiting_user"
    STEAM_GUARD_COMPLETED = "steam_guard_completed"
    STEAM_GUARD_FAILED = "steam_guard_failed"
    STEAM_GUARD_TIMEOUT = "steam_guard_timeout"
```

**Event Payloads**:
```python
# Code required
{
    "type": "steam_guard_code_required",
    "metadata": {
        "account": "personal_steam",
        "timeout_seconds": 60
    }
}

# QR required
{
    "type": "steam_guard_qr_required",
    "metadata": {
        "account": "personal_steam",
        "qr_screenshot_b64": "...",
        "timeout_seconds": 120
    }
}
```

---

## Implementation Phases

### Phase 1: Account Types
- [ ] Add `type` field to account config
- [ ] Add `requires_interaction` flag
- [ ] Update account pool logic to skip auto-retry for personal accounts

### Phase 2: Detection
- [ ] Add `/steam/detect-guard` endpoint to SUT Client
- [ ] OmniParser patterns for Steam Guard prompts
- [ ] Emit timeline events on detection

### Phase 3: Code Entry
- [ ] Frontend code input dialog
- [ ] WebSocket event handling for code prompt
- [ ] SUT Client `/steam/enter-code` endpoint
- [ ] Timeout handling

### Phase 4: QR Code
- [ ] Screenshot QR code region
- [ ] Frontend QR display component
- [ ] Polling for login completion
- [ ] Mobile app deep link (optional)

### Phase 5: Polish
- [ ] Acknowledgment dialog before run
- [ ] Timeout countdown UI
- [ ] Error recovery (wrong code, etc.)
- [ ] Run history shows Steam Guard events

---

## Related

- **Alternative**: "No Steam Login" feature (`skip_steam_login`) was implemented for users who pre-login manually
- See [automation-sequence.md](./automation-sequence.md) for full run flow
