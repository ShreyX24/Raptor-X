# RPX Architecture Analysis & Best Practices Comparison

## Executive Summary

Your RPX platform is a **well-structured microservices-based game automation system** at approximately 80% completion. The architecture demonstrates solid engineering choices in several areas, but there are opportunities for improvement in stability, scalability, and protocol optimization for production deployment.

---

## Part 1: Current Architecture Analysis

### Communication Topology

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            CURRENT RPX ARCHITECTURE                          │
└─────────────────────────────────────────────────────────────────────────────┘

                           ┌──────────────────────┐
                           │   Service Manager    │
                           │       (GUI)          │
                           └──────────────────────┘
                                      │
    ┌─────────────────┬───────────────┼───────────────┬─────────────────┐
    ▼                 ▼               ▼               ▼                 ▼
┌────────┐     ┌───────────┐   ┌───────────┐   ┌──────────┐     ┌───────────┐
│ Queue  │     │  Gemma    │   │  Preset   │   │   SUT    │     │ OmniParser│
│Service │◄───►│  Backend  │◄──│  Manager  │──►│Discovery │     │  Servers  │
│ :9000  │     │  :5000    │   │  :5002    │   │  :5001   │     │:8000-8004 │
└───┬────┘     └─────┬─────┘   └─────┬─────┘   └─────┬────┘     └─────┬─────┘
    │                │               │               │                 │
    │                │               │               │                 │
    └────────────────┴───────────────┴───────────────┴─────────────────┘
                                      │
                                      │ HTTP (via proxy)
                                      ▼
                           ┌──────────────────────┐
                           │      SUT Client      │
                           │       :8080          │
                           │  (Gaming Machines)   │
                           └──────────────────────┘
```

### Protocol Usage Summary

| Communication Path | Protocol | Direction | Purpose |
|-------------------|----------|-----------|---------|
| Frontend ↔ Backend | WebSocket + REST | Bidirectional | Real-time updates + API |
| Backend → SUT Discovery | HTTP REST | Request/Response | Proxy all SUT commands |
| SUT Discovery → SUT Client | HTTP REST | Request/Response | Execute commands |
| SUT Client → SUT Discovery | WebSocket | SUT-initiated | Registration, heartbeat |
| SUT Client ← Discovery | UDP Broadcast | Discovery-initiated | Master announcement |
| Backend → Queue Service | HTTP REST | Request/Response | OmniParser requests |
| Queue Service → OmniParser | HTTP REST | Request/Response | Screenshot parsing |
| Preset Manager ↔ SUT Client | HTTP REST | Request/Response | Preset sync |
| Frontend ← Services | SSE | Server-push | Real-time events |

### Strengths Identified

1. **Clean Microservices Separation**: Each service has a single responsibility
2. **Centralized Gateway (SUT Discovery)**: All SUT communication proxied through one point
3. **Dual Discovery Mode**: Supports both standalone and external discovery
4. **Event Bus Pattern**: Internal pub/sub for decoupled components
5. **State Persistence**: Device registry and run manifests saved to JSON
6. **Load Balancing**: Round-robin with health-aware failover in Queue Service
7. **Comprehensive Error Handling**: Multi-layer error recovery with fallbacks
8. **Timeline Events**: Detailed tracking for debugging and UX

### Weaknesses Identified

1. **Mixed Communication Protocols**: HTTP, WebSocket, UDP, SSE all used - complexity
2. **HTTP for Command/Control**: High latency for rapid automation sequences
3. **No Message Queue**: Direct service-to-service calls create tight coupling
4. **Blocking Operations**: SUT Client uses synchronous Flask/Waitress
5. **No Circuit Breaker**: No protection against cascading failures
6. **Limited Observability**: Basic logging, no distributed tracing
7. **Manual Scaling**: No auto-scaling or container orchestration built-in
8. **Single Point of Failure**: SUT Discovery is critical path with no redundancy

---

## Part 2: Best Practices Architecture (Research-Based)

Based on industry research from [Katalon](https://katalon.com/resources-center/blog/automation-testing-best-practices), [DZone](https://dzone.com/articles/test-automation-framework-design-patterns), [BrowserStack](https://www.browserstack.com/guide/jenkins-selenium), and others:

### Ideal Distributed Test Automation Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        IDEAL ARCHITECTURE (Hub-Spoke)                        │
└─────────────────────────────────────────────────────────────────────────────┘

                              ┌─────────────────┐
                              │   Control Plane │
                              │   (API Gateway) │
                              └────────┬────────┘
                                       │
              ┌────────────────────────┼────────────────────────┐
              │                        │                        │
              ▼                        ▼                        ▼
       ┌─────────────┐         ┌─────────────┐         ┌─────────────┐
       │ Orchestrator│         │  Test Queue │         │   Results   │
       │  (Scheduler)│◄───────►│   (Redis/   │◄───────►│   Storage   │
       │             │         │  RabbitMQ)  │         │             │
       └──────┬──────┘         └──────┬──────┘         └─────────────┘
              │                       │
              │    gRPC Bidirectional Streaming
              │                       │
    ┌─────────┴─────────┬─────────────┴─────────┬─────────────────────┐
    ▼                   ▼                       ▼                     ▼
┌──────────┐     ┌──────────┐           ┌──────────┐           ┌──────────┐
│  Agent 1 │     │  Agent 2 │           │  Agent 3 │           │  Agent N │
│  (SUT)   │     │  (SUT)   │           │  (SUT)   │           │  (SUT)   │
└──────────┘     └──────────┘           └──────────┘           └──────────┘
```

### Protocol Recommendations from Research

From [Ably's comparison](https://ably.com/topic/grpc-vs-websocket), [Resolute Software](https://www.resolutesoftware.com/blog/rest-vs-graphql-vs-grpc-vs-websocket/), and [Baseten](https://www.baseten.co/blog/http-vs-websockets-vs-grpc/):

| Use Case | Recommended Protocol | Reason |
|----------|---------------------|--------|
| Master → Agent Commands | **gRPC** | 2.5x throughput, 50-70% lower latency, bidirectional streaming |
| Agent Registration | **gRPC Streaming** | Persistent connection, native heartbeat |
| Real-time UI Updates | **WebSocket/SSE** | Browser compatibility |
| File Transfer (Presets) | **HTTP/gRPC** | Chunked transfer, progress tracking |
| Service Discovery | **UDP** for LAN, **Consul/etcd** for scale | Current approach is acceptable |
| Inter-service Async | **Message Queue** | Decoupling, retry, dead-letter |

### Key Best Practices

From [PrimeQA](https://primeqasolutions.com/scaling-test-automation-in-distributed-systems-a-comprehensive-guide-for-qa-engineers/) and [AWS Scalable Gaming Patterns](https://d1.awsstatic.com/whitepapers/aws-scalable-gaming-patterns.pdf):

1. **Test Independence**: Each run should be fully isolated
2. **Idempotent Operations**: Commands can be safely retried
3. **Graceful Degradation**: System continues with reduced functionality
4. **Circuit Breakers**: Prevent cascading failures
5. **Message Queues**: Decouple producers from consumers
6. **Containerization**: Consistent deployment, easy scaling
7. **Observability**: Distributed tracing, metrics, centralized logging

---

## Part 3: Detailed Comparison

### 1. Command/Control Protocol

| Aspect | Your Architecture | Best Practice | Gap |
|--------|------------------|---------------|-----|
| Protocol | HTTP REST | gRPC bidirectional streaming | **Significant** |
| Latency | ~50-200ms per request | ~5-20ms with gRPC | High |
| Connection | New per request | Persistent streaming | Overhead |
| Typing | JSON (runtime validation) | Protobuf (compile-time) | Safety |
| Streaming | Not supported | Native bidirectional | Missing |

**Impact**: During rapid automation (click → screenshot → parse → click), each round-trip adds 50-200ms latency. A 10-step sequence could take 2-4 seconds just in network overhead.

**Recommendation**: For MVP/current stage, HTTP is acceptable. For production with many SUTs running simultaneously, migrate to gRPC.

### 2. Service Communication

| Aspect | Your Architecture | Best Practice | Gap |
|--------|------------------|---------------|-----|
| Pattern | Direct HTTP calls | Message Queue (RabbitMQ/Redis) | **Moderate** |
| Coupling | Tight (synchronous) | Loose (async) | Coupling |
| Retry | Manual in each client | Queue-handled with DLQ | Reliability |
| Scaling | Limited | Independent per service | Scalability |

**Impact**: If Queue Service is slow/down, Gemma Backend blocks. If OmniParser takes long, the whole automation waits synchronously.

**Recommendation**: Introduce Redis pub/sub or RabbitMQ for:
- OmniParser request queue (already partially implemented!)
- Run status updates
- Inter-service events

### 3. Discovery & Registration

| Aspect | Your Architecture | Best Practice | Gap |
|--------|------------------|---------------|-----|
| Discovery | UDP broadcast | UDP (LAN) / Service Registry (Scale) | **Acceptable** |
| Registration | WebSocket + heartbeat | gRPC streaming or dedicated registry | Minor |
| Health Check | TCP ping + HTTP | gRPC health protocol | Minor |

**Your Approach is Good**: UDP broadcast for LAN discovery is industry-standard (similar to Selenium Grid node discovery). The WebSocket registration with heartbeat is solid.

### 4. State Management

| Aspect | Your Architecture | Best Practice | Gap |
|--------|------------------|---------------|-----|
| Run State | In-memory + JSON | Database (SQLite/PostgreSQL) | **Minor** |
| Device Registry | JSON file | Database with TTL | Minor |
| Distributed State | None | Redis/etcd for shared state | Future need |

**Your Approach is Acceptable**: For single-instance deployment, JSON persistence works. For multi-instance orchestrator or HA, you'd need a shared database.

### 5. Error Handling & Resilience

| Aspect | Your Architecture | Best Practice | Gap |
|--------|------------------|---------------|-----|
| Retry Logic | Manual per client | Exponential backoff library | Minor |
| Circuit Breaker | None | Hystrix/Resilience4j pattern | **Moderate** |
| Timeout Handling | Per-request timeout | Cascading timeouts | Minor |
| Fallback | Some (Steam dialogs) | Comprehensive | Minor |

**Recommendation**: Add circuit breaker pattern for OmniParser and SUT communication to prevent cascading failures.

### 6. Scalability

| Aspect | Your Architecture | Best Practice | Gap |
|--------|------------------|---------------|-----|
| Concurrent Runs | ThreadPoolExecutor(5) | Worker queue with auto-scale | **Minor** |
| SUT Scaling | Manual add | Auto-discovery + registration | Good |
| Service Scaling | Single instance | Container orchestration | Future |

**Your Approach is Good for Current Scale**: 5 concurrent runs with ThreadPool is reasonable for initial deployment. The Queue Service already handles OmniParser scaling well.

### 7. Observability

| Aspect | Your Architecture | Best Practice | Gap |
|--------|------------------|---------------|-----|
| Logging | Python logging, per-service | Centralized (ELK/Loki) | **Moderate** |
| Tracing | None | OpenTelemetry/Jaeger | Significant |
| Metrics | Basic stats in Queue | Prometheus/Grafana | Moderate |
| Alerting | None | PagerDuty/Alertmanager | Future |

**Recommendation**: For debugging multi-SUT issues, distributed tracing would be invaluable. Consider OpenTelemetry.

---

## Part 4: Stability & Deployability Assessment

### Current Stability Score: 7/10

**Strengths**:
- Comprehensive error handling in SUT Client
- Health checks in Queue Service and SUT Discovery
- Graceful shutdown handling
- State persistence for recovery

**Risks**:
- Single point of failure (SUT Discovery)
- No circuit breakers for external services
- Synchronous blocking in critical paths
- Limited retry mechanisms

### Current Deployability Score: 6/10

**Strengths**:
- CLI entry points for all services
- Service Manager for orchestration
- Configuration via environment variables
- JSON-based persistence (no external DB required)

**Gaps**:
- No containerization (Dockerfiles)
- No orchestration configs (Kubernetes/docker-compose)
- No automated deployment pipeline
- No health-check endpoints standardized across all services

---

## Part 5: Recommended Modifications

### Priority 1: Immediate (Stability)

1. **Standardize Health Endpoints**
   - All services: `GET /health` returning `{status: "healthy"|"degraded"|"unhealthy"}`
   - Already done in some services, ensure consistency

2. **Add Circuit Breaker for OmniParser**
   ```python
   # In queue_service - add circuit breaker state
   class CircuitBreaker:
       def __init__(self, failure_threshold=5, reset_timeout=60):
           self.failures = 0
           self.state = "closed"  # closed, open, half-open
   ```

3. **Improve SUT Command Retry**
   - Add exponential backoff to proxy calls
   - Add idempotency keys for critical operations

### Priority 2: Short-term (Reliability)

4. **Add Message Queue for Async Operations**
   - Use Redis pub/sub (already have Redis-like patterns)
   - Decouple OmniParser requests from run execution
   - Enable retry with dead-letter queue

5. **Implement Run Recovery**
   - Save run state before each step
   - Resume from last successful step on restart

6. **Add SUT Discovery Redundancy**
   - Allow multiple discovery service instances
   - SUTs connect to any available instance

### Priority 3: Medium-term (Scalability)

7. **Containerize Services**
   - Create Dockerfiles for each service
   - Create docker-compose.yml for local deployment
   - Enables consistent deployment across environments

8. **Consider gRPC for SUT Communication**
   - Define `.proto` files for SUT commands
   - Bidirectional streaming for real-time operations
   - Significant performance improvement

9. **Add Distributed Tracing**
   - Integrate OpenTelemetry
   - Trace request flow across services
   - Essential for debugging multi-SUT issues

### Priority 4: Long-term (Production)

10. **Database for State**
    - SQLite minimum, PostgreSQL for scale
    - Proper run history with querying
    - Device registry with TTL

11. **Kubernetes Deployment**
    - Helm charts for deployment
    - Horizontal pod autoscaling
    - Service mesh for observability

---

## Part 6: Protocol Recommendation for Master ↔ SUT

### Current State: HTTP (Acceptable)
Your current HTTP-based command protocol through SUT Discovery proxy works and is acceptable for:
- Small fleet (< 10 SUTs)
- Sequential automation (one command at a time)
- Development/testing phase

### Recommended Future State: Hybrid

```
┌─────────────────────────────────────────────────────────────────┐
│                    RECOMMENDED PROTOCOL MIX                      │
└─────────────────────────────────────────────────────────────────┘

1. REGISTRATION & HEARTBEAT
   ├─ Current: WebSocket ✓ (Keep this)
   └─ Alternative: gRPC bidirectional streaming

2. COMMAND EXECUTION (click, key, launch)
   ├─ Current: HTTP REST via proxy
   ├─ Short-term: HTTP with connection pooling (improve)
   └─ Long-term: gRPC unary calls (optimal)

3. STREAMING OPERATIONS (screenshots, logs)
   ├─ Current: HTTP GET with binary response
   └─ Long-term: gRPC server streaming

4. REAL-TIME UPDATES (to frontend)
   ├─ Current: WebSocket + SSE ✓ (Keep this)
   └─ Alternative: Consolidate to WebSocket only

5. SERVICE DISCOVERY
   ├─ Current: UDP broadcast ✓ (Keep this for LAN)
   └─ Scale: Add Consul/etcd for multi-subnet
```

### Why Not Pure gRPC Everywhere?

1. **Browser Compatibility**: Frontend needs WebSocket/SSE (gRPC-Web is complex)
2. **Simplicity**: HTTP is easier to debug, test with curl
3. **Current Investment**: Significant code already written for HTTP
4. **Diminishing Returns**: For < 20 SUTs, HTTP overhead is acceptable

### Why Not Pure WebSocket Everywhere?

1. **Stateful Complexity**: WebSocket requires connection management
2. **Scaling Challenge**: Sticky sessions needed for load balancing
3. **Not Request/Response**: Awkward for synchronous commands
4. **Your Current Use is Good**: Registration/heartbeat via WebSocket is appropriate

---

## Final Assessment

### Verdict: **Production-Ready with Caveats**

Your architecture is **deployable for small-to-medium scale** (5-15 SUTs, single orchestrator instance) with the following conditions:

| Deployment Scenario | Ready? | Notes |
|---------------------|--------|-------|
| Development/Testing | ✅ Yes | Fully functional |
| Single-site Production (< 10 SUTs) | ✅ Yes | Add circuit breakers |
| Multi-site Production (10-50 SUTs) | ⚠️ Partial | Need message queue, DB |
| Enterprise Scale (50+ SUTs) | ❌ No | Need gRPC, Kubernetes, full observability |

### What Makes Your Architecture Good

1. **Correct Microservices Boundaries**: Each service has clear responsibility
2. **Appropriate Technology Choices**: FastAPI, Flask-SocketIO are solid
3. **Thoughtful State Management**: Timeline events, run persistence
4. **Good Error Recovery**: Fallbacks, Steam dialog detection
5. **Load Balancing Done Right**: Queue Service is well-designed

### What Needs Improvement for Production

1. **Circuit Breakers**: Prevent cascade failures
2. **Message Queue**: Decouple async operations
3. **Containerization**: Consistent deployment
4. **Observability**: Distributed tracing for debugging

---

## Sources

- [Katalon - Automation Testing Best Practices](https://katalon.com/resources-center/blog/automation-testing-best-practices)
- [PrimeQA - Scaling Test Automation in Distributed Systems](https://primeqasolutions.com/scaling-test-automation-in-distributed-systems-a-comprehensive-guide-for-qa-engineers/)
- [Ably - gRPC vs WebSocket](https://ably.com/topic/grpc-vs-websocket)
- [Resolute Software - REST vs GraphQL vs gRPC vs WebSocket](https://www.resolutesoftware.com/blog/rest-vs-graphql-vs-grpc-vs-websocket/)
- [Baseten - HTTP vs WebSockets vs gRPC](https://www.baseten.co/blog/http-vs-websockets-vs-grpc/)
- [AWS - Scalable Gaming Patterns](https://d1.awsstatic.com/whitepapers/aws-scalable-gaming-patterns.pdf)
- [DZone - Test Automation Framework Design Patterns](https://dzone.com/articles/test-automation-framework-design-patterns)
- [BrowserStack - Jenkins Selenium Integration](https://www.browserstack.com/guide/jenkins-selenium)
- [Medium - RabbitMQ RPC for Scalable Microservices](https://medium.com/swlh/scalable-microservice-architecture-using-rabbitmq-rpc-d07fa8faac32)
- [AWS - RabbitMQ vs Redis Comparison](https://aws.amazon.com/compare/the-difference-between-rabbitmq-and-redis/)

---

## Appendix A: Service-by-Service Summary

### RPX Backend (Gemma Backend) - Port 5000
- **Framework**: Flask 3.0+ with Flask-SocketIO
- **Communication**: HTTP REST API + WebSocket for real-time
- **Key Features**: Run orchestration, timeline events, campaign management
- **State**: In-memory + JSON persistence
- **Workers**: ThreadPoolExecutor(5) for concurrent runs

### Preset Manager - Port 5002
- **Framework**: FastAPI + Uvicorn
- **Communication**: HTTP REST + WebSocket (SUT registration) + SSE
- **Key Features**: Filesystem-based preset storage, sync to SUTs
- **State**: JSON files, device registry
- **Discovery**: Dual mode (internal UDP or external service)

### SUT Client - Port 8080
- **Framework**: Flask + Waitress WSGI (8 threads)
- **Communication**: HTTP REST (receives commands) + WebSocket (to master)
- **Key Features**: Game launch, input automation, screenshot, preset apply
- **Platform**: Windows with admin elevation, DPI-aware
- **Discovery**: UDP listener + WebSocket registration

### SUT Discovery Service - Port 5001
- **Framework**: FastAPI + Uvicorn
- **Communication**: HTTP REST + WebSocket + UDP broadcast + SSE
- **Key Features**: Device registry, proxy to SUTs, SSH key management
- **State**: JSON persistence for paired devices
- **Role**: Central gateway for all SUT communication

### Queue Service - Port 9000
- **Framework**: FastAPI + httpx async
- **Communication**: HTTP REST
- **Key Features**: Load balancing, round-robin, health-aware failover
- **State**: In-memory stats, job history
- **Workers**: Configurable (default: 1 per OmniParser, min 2)

---

## Appendix B: Data Flow Examples

### Run Execution Flow
```
1. Frontend POST /api/runs → Backend
2. Backend queues run → ThreadPoolExecutor
3. Backend GET /api/suts/{id}/status → Discovery → SUT (health check)
4. Backend POST /api/sync/gemma → Preset Manager → SUT (preset sync)
5. Backend POST /api/suts/{id}/launch → Discovery → SUT (game launch)
6. Loop for each step:
   a. Backend GET /api/suts/{id}/screenshot → Discovery → SUT
   b. Backend POST /parse → Queue Service → OmniParser
   c. Backend POST /api/suts/{id}/action → Discovery → SUT
   d. Backend emits timeline event → WebSocket → Frontend
7. Backend POST /api/suts/{id}/terminate-game → Discovery → SUT
8. Backend emits run_completed → WebSocket → Frontend
```

### SUT Registration Flow
```
1. SUT Discovery broadcasts UDP MASTER_ANNOUNCE (port 9999)
2. SUT Client receives broadcast, extracts master IP:port
3. SUT Client connects WebSocket: ws://master:5001/api/ws/sut/{id}
4. SUT Client sends registration JSON (hostname, CPU, capabilities)
5. Discovery registers in device_registry, emits SUT_DISCOVERED
6. Discovery sends register_ack with SSH status
7. SSE clients receive sut_online event
8. SUT Client sends periodic heartbeats
```

---

*Document generated: 2026-01-19*
*Analysis based on codebase exploration and industry research*
