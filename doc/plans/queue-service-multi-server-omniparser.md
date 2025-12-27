# Plan: Queue-Service Multi-Server OmniParser Support

## Problem

Queue-service ignores `OMNIPARSER_URLS` env var and defaults to `localhost:8000`:
- Service Manager passes: `OMNIPARSER_URLS=http://192.168.0.103:8000,http://192.168.0.103:8001`
- Queue-service reads: `OMNIPARSER_URL` (singular) → not found → defaults to localhost

## Solution: Full Multi-Server Support with Round-Robin

---

## Files to Modify

| File | Purpose |
|------|---------|
| `queue_service/src/queue_service/config.py` | Parse OMNIPARSER_URLS into list |
| `queue_service/src/queue_service/queue_manager.py` | Round-robin server selection + per-server health |
| `queue_service/src/queue_service/api/health.py` | Report all server statuses in /probe |
| `queue_service/src/queue_service/main.py` | Update startup logging |

---

## Implementation Details

### 1. config.py (lines 10-46)

**Change `omniparser_url: str` to `omniparser_urls: List[str]`**

```python
from typing import Optional, List

def _parse_omniparser_urls() -> List[str]:
    """Parse OmniParser URLs from environment."""
    # Check plural form first (from Service Manager)
    urls_str = os.getenv("OMNIPARSER_URLS", "")
    if urls_str:
        return [url.strip() for url in urls_str.split(",") if url.strip()]
    # Fall back to singular form
    single = os.getenv("OMNIPARSER_URL", "http://localhost:8000")
    return [single]

@dataclass
class QueueServiceConfig:
    # Change line 19:
    omniparser_urls: List[str] = field(default_factory=lambda: ["http://localhost:8000"])

    # In from_env() line 39:
    omniparser_urls=_parse_omniparser_urls(),
```

### 2. queue_manager.py

**Add server selection and per-server health tracking**

```python
class QueueManager:
    def __init__(self, target_urls: List[str] = None, timeout: int = None):
        config = get_config()
        self.target_urls = target_urls or config.omniparser_urls
        self.timeout = timeout or config.request_timeout

        # Round-robin state
        self._current_server_index = 0
        self._server_health: Dict[str, bool] = {url: True for url in self.target_urls}

        logger.info(f"QueueManager initialized with {len(self.target_urls)} server(s): {self.target_urls}")

    def _get_next_server(self) -> str:
        """Round-robin server selection, skipping unhealthy servers."""
        attempts = 0
        while attempts < len(self.target_urls):
            url = self.target_urls[self._current_server_index]
            self._current_server_index = (self._current_server_index + 1) % len(self.target_urls)

            if self._server_health.get(url, True):
                return url
            attempts += 1

        # All unhealthy - try first server anyway
        return self.target_urls[0]

    async def _forward_to_omniparser(self, queued_request: QueuedRequest) -> Dict[str, Any]:
        """Forward request to next available OmniParser server."""
        target_url = self._get_next_server()

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{target_url}/parse/",
                json=queued_request.payload,
                headers={"Content-Type": "application/json"},
            )

            if response.status_code != 200:
                self._server_health[target_url] = False
                raise Exception(f"OmniParser error {response.status_code}: {response.text}")

            self._server_health[target_url] = True
            return response.json()

    async def health_check(self) -> List[Dict[str, Any]]:
        """Check health of all OmniParser servers."""
        results = []
        async with httpx.AsyncClient(timeout=5) as client:
            for url in self.target_urls:
                try:
                    response = await client.get(f"{url}/probe")
                    response.raise_for_status()
                    self._server_health[url] = True
                    results.append({
                        "url": url,
                        "status": "healthy",
                        "response": response.json(),
                    })
                except Exception as e:
                    self._server_health[url] = False
                    results.append({
                        "url": url,
                        "status": "unhealthy",
                        "error": str(e),
                    })
        return results
```

### 3. api/health.py

**Update /probe to return list of server statuses**

```python
@router.get("/probe")
async def probe():
    manager = get_queue_manager()
    server_statuses = await manager.health_check()  # Now returns List
    stats = manager.get_stats()

    return {
        "service": "queue-service",
        "version": "1.0.0",
        "queue_service_status": "running",
        "omniparser_status": server_statuses,  # List of {url, status, ...}
        "stats": stats.to_dict(),
    }
```

### 4. main.py

**Update startup logging (around line 134)**

```python
# Change from:
logger.info(f"Forwarding to OmniParser at {args.omniparser_url}")

# To:
config = get_config()
logger.info(f"OmniParser servers: {config.omniparser_urls}")
```

---

## Request Flow After Changes

```
Service Manager                          Queue-service
     |                                        |
     |-- OMNIPARSER_URLS=url1,url2 --------> |
     |                                        |-- parses to ["url1", "url2"]
     |                                        |
Request 1 ---------------------------------> url1 (round-robin)
Request 2 ---------------------------------> url2
Request 3 ---------------------------------> url1
     |                                        |
     |  (if url1 fails)                       |
Request 4 ---------------------------------> url2 (skip unhealthy)
```

---

## Testing

1. Start Service Manager
2. Configure 2 OmniParser servers: `http://192.168.0.103:8000`, `http://192.168.0.103:8001`
3. Start queue-service
4. Verify logs: `OmniParser servers: ['http://192.168.0.103:8000', 'http://192.168.0.103:8001']`
5. Dashboard shows health of both servers
6. Send multiple requests - verify round-robin distribution in logs
