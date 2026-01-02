# Learnings - Dos and Don'ts

Patterns that work, common pitfalls, and things that break easily.

## Path Handling

### DO
- Use Unix-style paths (`/c/Users/...`) in Git Bash background tasks
- Quote paths with spaces: `cd "/path/with spaces/"`
- Use forward slashes in Python code on Windows

### DON'T
- Use Windows backslash paths in bash background tasks (they get mangled)
- Assume current directory - always use absolute paths

## Service Startup

### DO
- Wait for OmniParser to load models (~30s) before sending requests
- Check service health before starting automation runs
- Use `run_in_background: true` for services to avoid terminal popups

### DON'T
- Use `uvicorn.run(..., reload=True)` for production - causes import issues
- Start Queue Service before OmniParser is ready
- Kill services without checking for active runs

## OmniParser Integration

### DO
- Use Queue Service for all OmniParser requests (load balancing)
- Include reasonable timeouts for parse requests
- Focus Steam window before taking screenshots for dialog detection

### DON'T
- Call OmniParser directly from Gemma - always go through Queue Service
- Send screenshots larger than necessary (scale down first)
- Assume OmniParser will always find elements (handle empty results)

## Timeline Events

### DO
- Use `replaces_event_id` when updating event status (waiting → detected)
- Include countdown metadata for timed operations
- Fail all in_progress events when run fails

### DON'T
- Create duplicate events with same event_id
- Leave events in "in_progress" state when operation completes
- Forget to persist timeline to disk after updates

## SUT Communication

### DO
- Use SUT Discovery proxy for all SUT communication
- Handle connection timeouts gracefully
- Verify SUT is online before starting automation

### DON'T
- Hardcode SUT IP addresses - use discovery service
- Assume SUT Client is always running
- Send commands without checking game state first

## Process Detection

### DO
- Wait for process with configurable timeout (default 60s)
- Focus window by process name for reliable screenshots
- Use countdown events to show progress in UI

### DON'T
- Use infinite loops for process detection
- Assume process name matches game name exactly
- Forget to update timeline when process is detected

## React Frontend

### DO
- Use React Query for API calls with proper caching
- Handle loading and error states in components
- Use WebSocket for real-time updates (runs, timeline)

### DON'T
- Poll API endpoints when WebSocket is available
- Store derived state that can be computed
- Forget to cleanup WebSocket connections on unmount

## Common Gotchas

1. **Port 8000 conflicts**: OmniParser default port often occupied, use 8100
2. **Steam dialogs**: Always check for Steam update/sync dialogs before game launch
3. **Window focus**: Screenshots may capture wrong window if not focused first
4. **Run state**: Always check for existing active runs before starting new one
5. **Timeline path**: Ensure timeline saves to correct run directory
6. **Empty string includes**: In JavaScript, `"anything".includes("")` returns `true`! Always guard against empty strings in fuzzy matching logic: `(str && target.includes(str))`
7. **React useEffect array deps**: Using `Object.values(obj)` as dependency causes infinite re-renders (new array reference each render). Use `Object.values(obj).length` or a stable reference instead

## Performance Tips

1. Parallel health checks - don't wait for each service sequentially
2. Cache game configs - don't reload YAML on every request
3. Use connection pooling for SUT requests
4. Batch timeline updates when possible
