# LFX Cloud Integration Plan

> **Status**: Research & Planning Phase
> **Date**: 2025-12-08
> **Goal**: Make lfx serve the execution engine for Langflow Cloud

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Translation Table (Langflow → LFX)](#translation-table)
3. [Research Findings](#research-findings)
4. [Open Questions](#open-questions)
5. [Identified Gaps](#identified-gaps)
6. [Related Work](#related-work)

---

## Architecture Overview

### Current Ecosystem

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           LANGFLOW ECOSYSTEM                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    LANGFLOW (Full Application)                       │   │
│  │  src/backend/base/langflow/                                         │   │
│  │                                                                      │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐   │   │
│  │  │   FastAPI    │  │   Frontend   │  │      Database Layer      │   │   │
│  │  │   /api/v1/   │  │   (React)    │  │  (PostgreSQL/SQLite)     │   │   │
│  │  └──────────────┘  └──────────────┘  └──────────────────────────┘   │   │
│  │         │                                        │                   │   │
│  │         ▼                                        ▼                   │   │
│  │  ┌─────────────────────────────────────────────────────────────┐    │   │
│  │  │                   SERVICE LAYER                              │    │   │
│  │  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌────────┐ │    │   │
│  │  │  │  Auth   │ │ Cache   │ │ Storage │ │  Task   │ │  Chat  │ │    │   │
│  │  │  │ Service │ │ Service │ │ Service │ │ Service │ │Service │ │    │   │
│  │  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └────────┘ │    │   │
│  │  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌────────┐ │    │   │
│  │  │  │Database │ │Variable │ │ Session │ │ State   │ │Tracing │ │    │   │
│  │  │  │ Service │ │ Service │ │ Service │ │ Service │ │Service │ │    │   │
│  │  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └────────┘ │    │   │
│  │  └─────────────────────────────────────────────────────────────┘    │   │
│  │                              │                                       │   │
│  │                              │ imports from                          │   │
│  └──────────────────────────────┼───────────────────────────────────────┘   │
│                                 ▼                                           │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         LFX (Executor Package)                       │   │
│  │  src/lfx/src/lfx/                                                   │   │
│  │                                                                      │   │
│  │  ┌─────────────────────────────────────────────────────────────┐    │   │
│  │  │                    CORE EXECUTION ENGINE                     │    │   │
│  │  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │    │   │
│  │  │  │    Graph    │  │   Vertex    │  │     Components      │  │    │   │
│  │  │  │  Execution  │  │  Building   │  │  (Agents, Tools,    │  │    │   │
│  │  │  │             │  │             │  │   Models, etc.)     │  │    │   │
│  │  │  └─────────────┘  └─────────────┘  └─────────────────────┘  │    │   │
│  │  └─────────────────────────────────────────────────────────────┘    │   │
│  │                                                                      │   │
│  │  ┌─────────────────────────────────────────────────────────────┐    │   │
│  │  │                      LFX CLI                                 │    │   │
│  │  │  ┌─────────────────────┐  ┌─────────────────────────────┐   │    │   │
│  │  │  │     lfx serve       │  │         lfx run             │   │    │   │
│  │  │  │  (FastAPI Server)   │  │    (One-shot execution)     │   │    │   │
│  │  │  │                     │  │                             │   │    │   │
│  │  │  │  Endpoints:         │  │  - Execute flow once        │   │    │   │
│  │  │  │  - /flows           │  │  - Return result            │   │    │   │
│  │  │  │  - /flows/{id}/run  │  │  - Exit                     │   │    │   │
│  │  │  │  - /flows/{id}/stream│ │                             │   │    │   │
│  │  │  │  - /health          │  │                             │   │    │   │
│  │  │  └─────────────────────┘  └─────────────────────────────┘   │    │   │
│  │  └─────────────────────────────────────────────────────────────┘    │   │
│  │                                                                      │   │
│  │  ┌─────────────────────────────────────────────────────────────┐    │   │
│  │  │              MINIMAL SERVICES (for standalone)               │    │   │
│  │  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐│    │   │
│  │  │  │ Settings │ │  Noop    │ │ Storage  │ │ Variable (env)   ││    │   │
│  │  │  │ Service  │ │ Database │ │ Service  │ │ Service          ││    │   │
│  │  │  └──────────┘ └──────────┘ └──────────┘ └──────────────────┘│    │   │
│  │  └─────────────────────────────────────────────────────────────┘    │   │
│  │                                                                      │   │
│  │  ┌─────────────────────────────────────────────────────────────┐    │   │
│  │  │                    SHARED SCHEMA                             │    │   │
│  │  │  InputValueRequest, RunOutputs, Tweaks, InputType,          │    │   │
│  │  │  OutputType, OutputValue, ErrorLog, etc.                     │    │   │
│  │  └─────────────────────────────────────────────────────────────┘    │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Development vs Runtime Model

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│   LANGFLOW (Development/Management)      LFX SERVE (Execution Runtime)     │
│   ════════════════════════════════       ═══════════════════════════════   │
│                                                                             │
│   ┌─────────────────────────────┐        ┌─────────────────────────────┐   │
│   │  - Flow Editor (UI)         │        │  - Stateless executor       │   │
│   │  - Project management       │  ───►  │  - No Langflow DB           │   │
│   │  - User auth/RBAC           │ export │  - Input → Process → Output │   │
│   │  - Variables, MCP settings  │        │  - SSE or HTTP response     │   │
│   │  - Database (PostgreSQL)    │        │  - Optimized for production │   │
│   └─────────────────────────────┘        └─────────────────────────────┘   │
│                                                                             │
│   "IDE / Development Environment"        "Runtime / Production Executor"   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Execution Flow

```
                              USER REQUEST
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          REQUEST HANDLING                                   │
│                                                                             │
│   Langflow API                          LFX Serve                           │
│   POST /api/v1/run/{flow_id}            POST /flows/{flow_id}/run           │
│           │                                      │                          │
│           └──────────────┬───────────────────────┘                          │
│                          ▼                                                  │
│                  ┌───────────────┐                                          │
│                  │ SimplifiedAPI │                                          │
│                  │    Request    │                                          │
│                  └───────┬───────┘                                          │
└──────────────────────────┼──────────────────────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         GRAPH EXECUTION                                     │
│                                                                             │
│  1. Graph.from_payload(flow_json)                                          │
│     - Parse nodes and edges                                                 │
│     - Build vertex objects                                                  │
│     - Topological sort for execution order                                  │
│                                                                             │
│  2. graph.prepare()                                                         │
│     - Initialize run context (run_id, session_id)                           │
│     - Set up run manager with entry vertices                                │
│     - Create execution queue                                                │
│                                                                             │
│  3. graph.arun() / graph.async_start()                                      │
│     - Execute vertices in order                                             │
│     - For agents: AgentExecutor.astream_events()                            │
│     - Emit events via EventManager                                          │
│                                                                             │
│  4. Return RunOutputs                                                       │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Agent Execution Loop

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         AGENT EXECUTION LOOP                                │
│                                                                             │
│   AgentComponent.run_agent()                                                │
│                                                                             │
│   agent = AgentExecutor.from_agent_and_tools(                               │
│       agent=llm_with_tools,                                                 │
│       tools=[...],                                                          │
│       max_iterations=15                                                     │
│   )                                                                         │
│                                                                             │
│   async for event in agent.astream_events(input, version="v2"):             │
│                                                                             │
│     ┌─────────────────────────────────────────────────────────────────┐    │
│     │  ITERATION LOOP (up to max_iterations)                           │    │
│     │                                                                  │    │
│     │   1. on_chain_start    → Agent receives input                    │    │
│     │   2. on_chat_model_stream → LLM generates tokens (streamed)      │    │
│     │   3. on_tool_start     → Tool invocation begins                  │    │
│     │   4. on_tool_end       → Tool returns result                     │    │
│     │   5. (repeat 2-4 until agent decides to finish)                  │    │
│     │   6. on_chain_end      → AgentFinish with final answer           │    │
│     └─────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│   Events emitted via EventManager → SSE to client                           │
│                                                                             │
│   ⚠️  NO DURABLE STATE: If process dies, agent state is lost               │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Translation Table

### Legend
- ✅ = Clear mapping exists
- ⚠️ = Needs definition/clarification
- ❌ = Missing/Gap

### Core Concepts

| Langflow Concept | LFX Serve Equivalent | Status | Notes |
|------------------|---------------------|--------|-------|
| **Flow** | Flow JSON artifact | ✅ | Exported as JSON, loaded by `lfx serve` |
| **Project (Folder)** | ? | ⚠️ | No concept of "project" in lfx - just individual flows |
| **Flow ID** | Deterministic ID from flow name | ✅ | Generated at serve time |
| **Flow Version** | ? | ❌ | No versioning in lfx |

### Variables & Configuration

| Langflow Concept | LFX Serve Equivalent | Status | Notes |
|------------------|---------------------|--------|-------|
| **Global Variables** | Environment Variables | ⚠️ | Validated via `validate_global_variables_for_env()` but no formal translation |
| **Credential Variables** | Environment Variables | ⚠️ | Same as above, but secrets need secure handling |
| **Flow Tweaks** | `tweaks` parameter in request | ✅ | Runtime parameter overrides |
| **Component Defaults** | Baked into flow JSON | ✅ | Set at export time |

### Authentication & Access

| Langflow Concept | LFX Serve Equivalent | Status | Notes |
|------------------|---------------------|--------|-------|
| **User** | ? | ❌ | No user concept in lfx |
| **API Key (per user)** | `LANGFLOW_API_KEY` (single) | ⚠️ | lfx has one key for entire deployment |
| **Flow `access_type`** (PUBLIC/PRIVATE) | ? | ❌ | No access control in lfx |
| **User ownership** (`user_id`) | N/A | ✅ | Not needed - stateless |

### MCP (Model Context Protocol)

| Langflow Concept | LFX Serve Equivalent | Status | Notes |
|------------------|---------------------|--------|-------|
| **MCP Server settings** | ? | ❌ | MCP components are "deactivated" in lfx |
| **MCP Auth (OAuth, API Key)** | ? | ❌ | No equivalent |
| **MCP Tools** | ? | ❌ | Would need to be baked into flow or configured at runtime |

### Execution

| Langflow Concept | LFX Serve Equivalent | Status | Notes |
|------------------|---------------------|--------|-------|
| **Run endpoint** (`/api/v1/run/{id}`) | `/flows/{id}/run` | ✅ | Similar but different path |
| **Stream endpoint** | `/flows/{id}/stream` | ✅ | SSE streaming |
| **Session ID** | `session_id` parameter | ✅ | Passed through, but no persistence |
| **Chat History** | ? | ⚠️ | Must be passed in request (no DB storage) |
| **Message persistence** | N/A | ✅ | Not applicable - stateless |

### Input/Output Types

| Langflow Concept | LFX Serve Equivalent | Status | Notes |
|------------------|---------------------|--------|-------|
| **ChatInput component** | `input_type: "chat"` | ✅ | Works |
| **TextInput component** | `input_type: "text"` | ✅ | Works |
| **DataInput component** | ? | ❌ | Not supported yet |
| **FileInput component** | ? | ❌ | Not supported yet |
| **WebhookInput** | ? | ❌ | Not supported yet |
| **ChatOutput** | `output_type: "chat"` | ✅ | Works |
| **TextOutput** | `output_type: "text"` | ✅ | Works |
| **DataOutput** | ? | ❌ | Not supported yet |
| **Multiple outputs** | `output_component` param | ⚠️ | Can target specific component, but multi-output unclear |

### Flow Types

| Langflow Flow Type | LFX Serve Support | Status | Notes |
|--------------------|-------------------|--------|-------|
| **Chat flow** (ChatInput → ChatOutput) | Supported | ✅ | Primary use case |
| **Text flow** (TextInput → TextOutput) | Supported | ✅ | Works |
| **Data pipeline** (Data in → Data out) | ? | ❌ | Not implemented |
| **Webhook flow** (HTTP trigger) | ? | ❌ | Not implemented |
| **Batch processing** | ? | ❌ | Not implemented |
| **Multi-input flow** | ? | ❌ | Not implemented |
| **Multi-output flow** | ? | ⚠️ | Partial - can target one output |

### Services

| Langflow Service | LFX Serve Equivalent | Status | Notes |
|------------------|---------------------|--------|-------|
| **DatabaseService** | `NoopDatabaseService` | ✅ | Explicit noop mode |
| **SettingsService** | `Settings` (minimal) | ✅ | Environment-based |
| **CacheService** | ? | ⚠️ | In-memory only? |
| **StorageService** | `LocalStorageService` | ⚠️ | Local only, needs cloud options |
| **VariableService** | Environment fallback | ⚠️ | PR #10111 adds this |
| **ChatService** | ? | ⚠️ | Exists but no persistence |
| **TracingService** | Minimal (PR #10111) | ⚠️ | Needs cloud integration |
| **TelemetryService** | Logging only (PR #10111) | ⚠️ | Needs cloud integration |
| **AuthService** | API key validation | ⚠️ | Single key only |
| **SessionService** | ? | ❌ | No session persistence |
| **TaskService** | ? | ❌ | No background tasks |
| **JobQueueService** | ? | ❌ | No job queue |

### State & Persistence

| Langflow Concept | LFX Serve Equivalent | Status | Notes |
|------------------|---------------------|--------|-------|
| **TransactionTable** (execution log) | N/A | ✅ | Not needed - stateless |
| **VertexBuildTable** (snapshots) | N/A | ✅ | Not needed - stateless |
| **MessageTable** (chat history) | N/A | ✅ | Client must manage |
| **Session caching** | In-memory (request scope) | ⚠️ | Lost after request |

### Agent Execution

| Langflow Concept | LFX Serve Equivalent | Status | Notes |
|------------------|---------------------|--------|-------|
| **AgentExecutor loop** | Same (via lfx components) | ✅ | Works |
| **Tool calling** | Same | ✅ | Works |
| **Streaming tokens** | SSE events | ✅ | Works |
| **Max iterations** | Component config | ✅ | Works |
| **Agent state checkpoint** | ? | ❌ | No durability |
| **Long-running agents** | ? | ⚠️ | Works but no recovery on failure |

### Deployment Artifacts

| Langflow Concept | LFX Serve Equivalent | Status | Notes |
|------------------|---------------------|--------|-------|
| **Export flow JSON** | Input to `lfx serve` | ✅ | Works |
| **Export project** | ? | ❌ | No project bundle format |
| **Include variables** | ? | ❌ | No variable export/mapping |
| **Include MCP config** | ? | ❌ | No MCP export |
| **Deployment manifest** | ? | ❌ | No deployment descriptor |

---

## Research Findings

### LFX Serve - Current State

**Location**: `src/lfx/src/lfx/`

- Lightweight FastAPI-based REST API server for executing Langflow flows
- Supports single/multi-flow serving via `lfx serve`
- Has streaming support (`/flows/{flow_id}/stream`) using Server-Sent Events (SSE)
- Authentication via `LANGFLOW_API_KEY` environment variable
- Services architecture: Database, Settings, Chat, Storage, Tracing, Variable services

**Key Files**:
- CLI entry point: `src/lfx/src/lfx/__main__.py`
- Serve command: `src/lfx/src/lfx/cli/commands.py`
- FastAPI app: `src/lfx/src/lfx/cli/serve_app.py`
- Graph execution: `src/lfx/src/lfx/graph/graph/base.py`

### PR #10111 - Pluggable Services Architecture

**Status**: Draft

The PR introduces:
- **Service Discovery**: Decorator-based (`@register_service`), config files (`lfx.toml`), and Python entry points
- **Central ServiceManager** for orchestration
- **Built-in Services**: VariableService (env fallback), TelemetryService, TracingService, LocalStorageService

### Durable Execution / Async Tasks

| Component | Current Implementation | Gap for Agents |
|-----------|----------------------|----------------|
| **Job Queue** | `JobQueueService` - asyncio.Queue per job | In-memory only, lost on restart |
| **Task Backend** | AnyIOBackend (local) or CeleryBackend (optional) | Celery exists but not deeply integrated |
| **State Persistence** | `TransactionTable`, `VertexBuildTable`, `MessageTable` | No checkpoint/resume for long-running agents |
| **Streaming** | SSE via `consume_and_yield()` | Works well, needs consistent event format |

### Agent Execution

- Agents use iterative loop pattern via LangChain's `AgentExecutor`
- `astream_events(version="v2")` for real-time token streaming
- Tool calls tracked in `ToolContent` blocks
- **Max iterations**: default 15, configurable
- **No durable execution**: If process dies mid-agent-loop, state is lost

### Authentication & RBAC

| Aspect | Current State |
|--------|---------------|
| **Auth Methods** | JWT (web UI), API Keys (programmatic) |
| **RBAC** | Simple: `is_superuser` boolean only |
| **Multi-tenancy** | **None** - single tenant per deployment |
| **Resource Isolation** | User-level via `user_id` foreign keys |
| **Public Flows** | `access_type` field (PUBLIC/PRIVATE) |

**Key Files**:
- Auth utilities: `src/backend/base/langflow/services/auth/utils.py`
- User model: `src/backend/base/langflow/services/database/models/user/model.py`
- Auth settings: `src/lfx/src/lfx/services/settings/auth.py`

---

## Open Questions

### A. Export/Deploy Mechanism

1. **Export format**: When a flow is exported for lfx serve, what gets bundled?
   - Just the flow JSON?
   - Flow JSON + resolved global variables?
   - Flow JSON + MCP settings + variables as a "project bundle"?

2. **Variable resolution**: Since lfx is stateless and doesn't connect to Langflow DB:
   - Are variables resolved at export time (baked into flow)?
   - Or does lfx expect them as environment variables at runtime?
   - Or both options depending on configuration?

3. **MCP settings**: How should MCP server connections work in lfx?
   - Configured at deploy time?
   - Passed as part of the flow artifact?

### B. Non-Chat Flow Support

4. **Flow types to support**: What are the input/output patterns beyond chat?
   - **Chat**: `input_value` (string) → streaming text response
   - **Batch/Data**: DataFrame in → DataFrame out?
   - **API/Webhook**: JSON payload → JSON response?
   - **File processing**: File upload → processed file?

5. **Input/Output detection**: Should lfx:
   - Auto-detect flow type from components (ChatInput vs DataInput)?
   - Require explicit configuration in the export?
   - Support multiple input/output modes per flow?

### C. Durable Execution

6. **Agent execution in stateless lfx**: For long-running agents:
   - Is "stateless" per-request (single request can run for minutes)?
   - Or is there a max execution time expectation?
   - Should checkpoint/resume be handled by a separate orchestrator layer above lfx?

7. **Scaling model**: For Langflow Cloud, how do you envision lfx instances:
   - One long-running lfx serve per project?
   - Ephemeral containers spun up per request?
   - Pool of lfx workers pulling from a queue?

### D. Auth in the Cloud Context

8. **API key flow**: When lfx serve runs in Langflow Cloud:
   - Does the cloud gateway handle auth and pass requests to lfx?
   - Or does each lfx instance validate its own API key?
   - Is the API key the same one from Langflow, or generated per deployment?

### E. PR #10111 Fit

9. **Pluggable services for lfx**: Which services from PR #10111 are critical for cloud?
   - VariableService (to inject secrets at runtime)?
   - StorageService (for artifact storage)?
   - TelemetryService (for observability)?

---

## Identified Gaps

### Critical Gaps (Blocks Cloud Deployment)

1. **Project bundle format** - No way to export project as deployable unit
2. **Variable translation** - No formal Langflow Variable → Env Var mapping
3. **Non-chat flow support** - Only chat/text flows work
4. **MCP integration** - Completely missing in lfx

### Important Gaps (Limits Functionality)

5. **Multi-flow deployment** - lfx serve is single-flow focused
6. **Session/state management** - No cross-request state
7. **Cloud services** - Storage, secrets, telemetry need cloud implementations

### Nice-to-Have (Future)

8. **Flow versioning** - No version tracking
9. **Access control** - Single API key, no per-flow auth
10. **Durable execution** - No checkpoint/resume

---

## Related Work

### In Progress

- **PR #10111**: Pluggable services architecture (Draft)
- **Common API Schema**: Engineers working on unified schema between Langflow and lfx

### Key Database Tables

- `flows` - Flow definitions
- `folders` - Projects (renamed from folders)
- `variables` - Global variables
- `users` - User accounts
- `api_keys` - API key storage

### Key Code Paths

| Purpose | Langflow Path | LFX Path |
|---------|--------------|----------|
| Flow execution | `api/v1/endpoints.py` | `cli/serve_app.py` |
| Graph engine | Uses lfx | `graph/graph/base.py` |
| Services | `services/` | `services/` |
| Components | Uses lfx | `components/` |
| Schemas | `schema/` (re-exports lfx) | `schema/` |

---

## Next Steps

1. Answer open questions to clarify requirements
2. Define project bundle format specification
3. Prioritize gaps for implementation
4. Create task breakdown for engineering delegation
5. Identify dependencies between workstreams
