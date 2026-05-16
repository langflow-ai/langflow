# 3. Backend — Layered View

The backend is a classic layered FastAPI app with a **service-locator dependency-injection pattern**.

```mermaid
graph TB
    Client[HTTP / SSE Client]

    subgraph FastAPI["FastAPI app (main.py)"]
        MW[Middleware<br/>CORS · RequestCancelled ·<br/>JS-MIME · ContentSizeLimit]
        Static[Static mount<br/>React build]
    end

    subgraph Routers["API Routers (api/router.py)"]
        v1[/api/v1/<br/>chat · flows · endpoints ·<br/>models · knowledge_bases ·<br/>mcp · agentic/]
        v2[/api/v2/<br/>workflow · registration · mcp/]
    end

    subgraph Services["Service Layer (services/)"]
        Auth[AuthService]
        DBS[DatabaseService]
        Chat[ChatService]
        CacheS[CacheService]
        Storage[StorageService]
        Queue[JobQueueService]
        Trace[TracingService]
        Settings[SettingsService]
        Tele[TelemetryService]
        Vars[VariableService]
    end

    subgraph Core["Execution Core"]
        Graph[Graph engine - lfx]
        Components[Component registry<br/>200+ built-ins]
        Custom[Custom component<br/>framework]
    end

    subgraph Persistence["Persistence"]
        Models[SQLModel models<br/>Flow · User · APIKey ·<br/>Message · VertexBuild]
        Alembic[Alembic migrations]
    end

    Client --> MW --> Routers
    MW --> Static
    v1 --> Services
    v2 --> Services
    Services --> Core
    Services --> Persistence
    Core --> Components
    Core --> Custom
```

## Entry-point chain

```
langflow run              # CLI
  └── langflow_launcher:main
        └── langflow.__main__
              └── Gunicorn + Uvicorn workers (LangflowApplication, server.py)
                    └── main.py::setup_app()  ──► FastAPI instance
```

## Routers

Two versioned APIs under `api/router.py`:

- **v1** (`/api/v1`): `chat`, `flows`, `endpoints`, `models`, `knowledge_bases`, `deployments`, `mcp`, `mcp_projects`, `agentic`
- **v2** (`/api/v2`): `workflow`, `registration`, `mcp`

## Services (the DI registry)

All stateful subsystems are resolved through `services/deps.py::get_service(ServiceType.X)` — a typed singleton lookup. Services are constructed lazily, swappable in tests, and shared across requests:

| Service | Responsibility |
|---|---|
| `AuthService` | JWT auth, API-key validation |
| `DatabaseService` | SQLModel session, pool, migrations |
| `ChatService` | Flow build/run caching, session state |
| `CacheService` | In-memory or Redis cache |
| `StorageService` | File uploads / downloads |
| `JobQueueService` | Background tasks |
| `TracingService` | OpenTelemetry tracing |
| `SettingsService` | Config + env vars |
| `TelemetryService` | Anonymous usage pings |
| `VariableService` | Global variables for flows |

This keeps routers thin (just HTTP wiring) and makes the execution core unit-testable without a server.

## Middleware

Defined in `main.py`:

- `RequestCancelledMiddleware` — cleans up when clients disconnect from streams.
- `JavaScriptMIMETypeMiddleware` — content-type fixes for the React bundle.
- `ContentSizeLimitMiddleware` — bounds payload size.
- `CORSMiddleware` — standard CORS.
