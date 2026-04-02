# Graph Checkpointing for A2A Task Continuation

Status: Design proposal
Author: A2A implementation team
Date: 2026-03-28

---

## Problem Statement

Langflow's A2A server cannot correctly implement the A2A protocol's `input-required` state because there is no way to pause a flow execution mid-graph, persist its state, and resume it later when the client responds.

When an A2A agent needs clarification from the caller (e.g., "which environment should I deploy to?"), the protocol requires the server to:

1. Transition the task to `input-required` with the question
2. Return control to the client
3. Wait for the client to send a follow-up message
4. **Resume execution from the exact point it paused**, with the client's answer

Step 4 is the problem. Langflow's graph executor (`graph.arun()`) runs the entire flow as a single async operation. There is no mechanism to pause mid-execution, persist the graph state, and resume later. Without this, the only option is to re-execute the entire flow from scratch on follow-up — which is not correct A2A behavior (the client is continuing the *same task*, not starting a new one).

---

## Why This Matters Beyond A2A

Graph checkpointing is not just an A2A requirement. It enables several capabilities that Langflow currently cannot support:

### 1. Human-in-the-loop workflows

Any flow that requires human approval, review, or input at a specific step. Examples:
- A content generation flow that pauses for editor approval before publishing
- A data pipeline that asks a human to verify a classification before proceeding
- An agent that needs manager approval for actions above a threshold

### 2. Long-running flows with durability

Flows that take minutes or hours to complete (batch processing, multi-step research agents) are vulnerable to server restarts. With checkpointing, a flow can resume from the last completed step instead of starting over.

### 3. Conditional resumption

Flows that branch based on external events. A flow could pause at a decision point, wait for an external system to provide data (webhook, API callback), and resume down the correct branch.

### 4. Debugging and replay

Checkpoints enable stepping through a flow one vertex at a time, inspecting state at each point. Developers can replay a flow from a specific checkpoint with different inputs to debug issues.

### 5. Cost optimization

When a flow fails at step 8 of 10 due to a transient error (rate limit, network timeout), checkpointing allows retrying from step 8 instead of re-running steps 1-7 (which may involve expensive LLM calls).

---

## Current State: What Langflow Already Has

The codebase has **partial infrastructure** for checkpointing that was never completed:

### Snapshot system (exists, not persisted)

```python
# Graph.__init__()
self._snapshots: list[dict[str, Any]] = []
self._call_order: list[str] = []

# Graph._record_snapshot() — called during execution
def _record_snapshot(self, vertex_id=None):
    self._snapshots.append(self.get_snapshot())
    if vertex_id:
        self._call_order.append(vertex_id)

# Graph.get_snapshot() — captures execution state
def get_snapshot(self):
    return copy.deepcopy({
        "run_manager": self.run_manager.to_dict(),
        "run_queue": self._run_queue,
        "vertices_layers": self.vertices_layers,
        "first_layer": self.first_layer,
        "inactive_vertices": self.inactive_vertices,
        "activated_vertices": self.activated_vertices,
    })
```

Snapshots are recorded during execution but **only stored in memory** — they're lost when the execution completes or the server restarts.

### RunnableVerticesManager (serializable)

The manager that tracks which vertices are ready/running/completed already has serialization:

```python
class RunnableVerticesManager:
    def to_dict(self) -> dict: ...
    def from_dict(cls, data) -> RunnableVerticesManager: ...
    def __getstate__(self) -> dict: ...
    def __setstate__(self, state): ...
```

### Vertex state (partially serializable)

Vertices have `__getstate__`/`__setstate__` that handle non-serializable fields (locks, UnbuiltObject placeholders).

### Per-vertex result caching (exists)

The `build_vertex()` method already supports caching individual vertex results via a `SetCache`/`GetCache` service. On cache hit, a vertex's `built`, `artifacts`, `built_object`, and `built_result` are restored from cache.

### What's missing

1. **Persistent storage backend** — Snapshots exist in memory only
2. **Resume-from-checkpoint API** — No way to restart a graph from a saved state
3. **Suspension point abstraction** — No way for a vertex to signal "pause here"
4. **External trigger for resumption** — No mechanism for an external event to resume a paused graph

---

## Technical Design

### Core Concept: Layer-Boundary Checkpoints

Langflow's graph executes in topologically sorted layers. Vertices within a layer run in parallel; a layer must complete before the next begins. **Layer boundaries are natural checkpoint locations** — they represent clean state where:

- All vertices in the completed layer have results
- No vertices are mid-execution
- The next layer's inputs are fully available
- The graph structure is deterministic from this point forward

```
Layer 0: [ChatInput, Calculator, URL]     ← checkpoint after
Layer 1: [Agent]                          ← checkpoint after (PAUSE HERE)
Layer 2: [ChatOutput]                     ← checkpoint after
```

### Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    Graph Executor                         │
│                                                          │
│  for each layer:                                         │
│    execute vertices in parallel                          │
│    ─── checkpoint ───                                    │
│    if any vertex signals PAUSE:                          │
│      persist checkpoint to store                         │
│      return PausedExecution(checkpoint_id, reason)       │
│                                                          │
│  ... later, when external input arrives ...              │
│                                                          │
│  Graph.resume_from_checkpoint(checkpoint_id, input):     │
│    load checkpoint from store                            │
│    restore graph state                                   │
│    inject input into the paused vertex                   │
│    continue executing remaining layers                   │
└──────────────────────────────────────────────────────────┘
         │                           ▲
         ▼                           │
┌──────────────────┐    ┌──────────────────────┐
│ CheckpointStore  │    │  External Trigger     │
│ (DB or Redis)    │    │  (A2A follow-up,      │
│                  │    │   webhook, UI action)  │
│ save(id, state)  │    │                        │
│ load(id) → state │    │  resume(id, input)     │
└──────────────────┘    └──────────────────────┘
```

### Checkpoint Data Model

```python
class GraphCheckpoint:
    # Identity
    checkpoint_id: str          # Unique ID (UUID)
    flow_id: str                # Which flow
    session_id: str             # Which session (for multi-turn)
    run_id: str                 # Which execution run

    # Execution state
    completed_layers: int       # How many layers finished
    run_manager_state: dict     # RunnableVerticesManager.to_dict()
    vertices_to_run: set[str]   # Remaining vertex IDs
    vertices_layers: list[list[str]]  # Remaining layer structure
    inactivated_vertices: set[str]
    activated_vertices: list[str]
    call_order: list[str]       # Execution history

    # Vertex results (for completed vertices)
    vertex_results: dict[str, dict]  # vertex_id → serialized result
    # Each entry contains: built, results, artifacts, built_object, built_result

    # Pause context
    paused_vertex_id: str | None     # Which vertex requested the pause
    pause_reason: str                # Why execution paused
    pause_data: dict                 # Data associated with the pause
                                     # (e.g., the question for input-required)

    # Metadata
    created_at: datetime
    expires_at: datetime        # Auto-cleanup after TTL
```

### CheckpointStore Interface

```python
class CheckpointStore(ABC):
    """Abstract interface for checkpoint persistence."""

    async def save(self, checkpoint: GraphCheckpoint) -> str:
        """Persist a checkpoint. Returns checkpoint_id."""
        ...

    async def load(self, checkpoint_id: str) -> GraphCheckpoint | None:
        """Load a checkpoint by ID. Returns None if expired/missing."""
        ...

    async def delete(self, checkpoint_id: str) -> None:
        """Delete a checkpoint (after successful resumption)."""
        ...

    async def list_by_session(self, session_id: str) -> list[GraphCheckpoint]:
        """List checkpoints for a session (for debugging)."""
        ...
```

Two implementations:

1. **DatabaseCheckpointStore** — SQLAlchemy model, persists to the same DB as flows. Durable across restarts. Production default.

2. **InMemoryCheckpointStore** — Dict-based, for testing. Same interface.

### Graph Execution Changes

#### New: Vertex pause signal

A vertex (component) can signal that execution should pause at the current layer boundary:

```python
# In a component's build method:
class RequestInputComponent(Component):
    async def build(self):
        question = self.input_value  # or configured prompt

        # Signal the graph to pause after this layer
        self.graph.request_pause(
            vertex_id=self.vertex_id,
            reason="input-required",
            data={"question": question},
        )

        # Return the question as this component's output
        # (downstream components won't execute until resume)
        return Message(text=question)
```

#### New: Graph.request_pause()

```python
class Graph:
    def __init__(self):
        self._pause_requested = False
        self._pause_info: dict | None = None

    def request_pause(self, vertex_id: str, reason: str, data: dict):
        """Signal that execution should pause after the current layer."""
        self._pause_requested = True
        self._pause_info = {
            "vertex_id": vertex_id,
            "reason": reason,
            "data": data,
        }
```

#### Modified: Graph.process() — check for pause after each layer

```python
async def process(self, ...):
    to_process = deque(first_layer)

    while to_process:
        current_batch = list(to_process)
        tasks = [asyncio.create_task(build_vertex(v)) for v in current_batch]
        next_runnable = await _execute_tasks(tasks)

        # NEW: Check if any vertex requested a pause
        if self._pause_requested:
            checkpoint = self._create_checkpoint()
            await self._checkpoint_store.save(checkpoint)
            raise GraphPausedException(
                checkpoint_id=checkpoint.checkpoint_id,
                reason=self._pause_info["reason"],
                data=self._pause_info["data"],
            )

        to_process.extend(next_runnable)
```

#### New: Graph.resume_from_checkpoint()

```python
@classmethod
async def resume_from_checkpoint(
    cls,
    checkpoint: GraphCheckpoint,
    input_data: dict | None = None,
) -> Graph:
    """Restore a graph from a checkpoint and prepare for continued execution."""

    # Reconstruct the graph from the flow definition
    graph = cls.from_payload(
        payload=checkpoint.flow_payload,
        flow_id=checkpoint.flow_id,
        session_id=checkpoint.session_id,
    )

    # Restore execution state
    graph.run_manager = RunnableVerticesManager.from_dict(
        checkpoint.run_manager_state
    )
    graph.vertices_to_run = checkpoint.vertices_to_run
    graph.vertices_layers = checkpoint.vertices_layers
    graph._call_order = checkpoint.call_order

    # Restore completed vertex results
    for vertex_id, result_data in checkpoint.vertex_results.items():
        vertex = graph.get_vertex(vertex_id)
        vertex.built = result_data["built"]
        vertex.artifacts = result_data["artifacts"]
        vertex.built_object = result_data["built_object"]
        vertex.built_result = result_data["built_result"]
        vertex.result = result_data.get("result")

    # Inject the external input into the paused vertex's successors
    if input_data and checkpoint.paused_vertex_id:
        # The paused vertex's output is replaced/augmented with
        # the external input, making it available to downstream vertices
        paused_vertex = graph.get_vertex(checkpoint.paused_vertex_id)
        paused_vertex.inject_external_input(input_data)

    return graph
    # Caller then calls graph.arun() which continues from remaining layers
```

### E2E Flow: V2 Workflow Pause/Resume via API

```
1. Client starts a background workflow:
   POST /api/v2/workflows  {background: true, flow_id: "...", inputs: {...}}
   → Returns {job_id: "abc-123", status: "queued"}

2. Executor picks up the job:
   - Job status → IN_PROGRESS
   - graph._checkpointing_enabled = True, graph._job_id = "abc-123"
   - Vertices execute layer by layer
   - After each vertex build, executor polls: SELECT status FROM jobs WHERE job_id = "abc-123"

3. Client sends pause signal:
   POST /api/v2/workflows/pause  {job_id: "abc-123"}
   → Job status set to PAUSED in DB
   → Returns {status: "paused", message: "..."}

4. Executor sees PAUSED status on next vertex check:
   - Creates GraphCheckpoint with all completed vertex results
   - Saves checkpoint to CheckpointStore (keyed by run_id = job_id)
   - Raises GraphPausedException
   - execute_with_status catches it (does NOT mark job as FAILED)

5. Client polls status:
   GET /api/v2/workflows?job_id=abc-123
   → Returns {status: "paused"}

6. Client resumes:
   POST /api/v2/workflows/resume  {job_id: "abc-123", inputs: {"text": "production"}}
   → Loads checkpoint by run_id
   → Calls Graph.resume_from_checkpoint(checkpoint, input_data=inputs)
   → Fires new background task to continue execution
   → Job status → IN_PROGRESS
   → Returns {status: "in_progress"}

7. Executor continues from checkpoint:
   - Only unbuilt vertices execute
   - Completed vertices have their results restored from checkpoint
   - Flow completes normally
   - Job status → COMPLETED

8. Client polls:
   GET /api/v2/workflows?job_id=abc-123
   → Returns full WorkflowExecutionResponse with outputs
```

The critical difference from re-execution: **steps 1-2 don't re-run**. All completed vertex results (LLM calls, tool usage, API calls) are preserved in the checkpoint. Only remaining vertices execute.

### A2A Integration (Future)

A2A INPUT_REQUIRED will use the same checkpointing infrastructure. When an Agent component decides it needs clarification, the A2A router will write a PAUSE signal and the same checkpoint/resume flow applies.

### ~~RequestInput Component Design~~ (REMOVED)

> **Decision:** A dedicated RequestInput canvas component was removed from scope. Flow authors should not have to manually place "pause here" components — the framework handles checkpointing transparently at every component boundary, and agents decide dynamically when they need clarification. Pause/resume signals come from API requests, not from components.

### V2 Workflow API: Pause and Resume Endpoints

Pause and resume are exposed as first-class operations in the v2 workflow API:

```
POST /api/v2/workflows/pause   — Send a PAUSE signal to a running job
POST /api/v2/workflows/resume  — Resume a PAUSED job from its checkpoint
```

**Pause request:**
```json
{
  "job_id": "uuid",
  "reason": "user-requested",
  "data": {}
}
```

**Resume request:**
```json
{
  "job_id": "uuid",
  "inputs": {
    "text": "production"
  }
}
```

**Job status transitions:**
```
QUEUED → IN_PROGRESS → PAUSED → IN_PROGRESS → COMPLETED
                     → CANCELLED
                     → FAILED
                     → TIMED_OUT
```

The `PAUSED` status was added to the `JobStatus` enum. A paused job holds a reference to its checkpoint, which contains the serialized graph state. On resume, the checkpoint is loaded, new inputs are injected, and execution continues from the next unbuilt vertex.

---

## Implementation Plan

### Phase A: CheckpointStore and data model

1. Define `GraphCheckpoint` Pydantic model
2. Implement `InMemoryCheckpointStore` for testing
3. Implement `DatabaseCheckpointStore` (SQLAlchemy model + Alembic migration)
4. Add `CheckpointStore` to Langflow's service manager

**Tests:** CRUD operations, TTL expiry, session listing.

### Phase B: Graph pause and checkpoint creation

1. Add `request_pause()` and `_pause_requested` to Graph
2. Add `GraphPausedException`
3. Modify `Graph.process()` to check for pause after each layer
4. Add `_create_checkpoint()` that serializes current state
5. Verify checkpoint contains everything needed for resumption

**Tests:** Pause at each layer boundary, checkpoint data completeness.

### Phase C: Graph resumption from checkpoint

1. Implement `Graph.resume_from_checkpoint()`
2. Implement vertex result restoration
3. Implement external input injection into paused vertex
4. Verify resumed graph executes only remaining layers

**Tests:** Resume from layer 0, 1, 2. Verify completed vertices not re-executed. Verify input flows to correct downstream vertex.

### Phase D: V2 Workflow API pause/resume endpoints

1. Add `PAUSED` to `JobStatus` enum
2. Add `POST /workflows/pause` endpoint — writes PAUSE signal, transitions job to PAUSED
3. Add `POST /workflows/resume` endpoint — loads checkpoint, resumes graph, transitions to IN_PROGRESS
4. Add pause/resume request/response schemas

**Tests:** Pause a running job, verify status transition. Resume a paused job, verify execution continues.

### Phase E: execution_signals DB table and per-vertex polling

1. Create `execution_signals` DB model (id, flow_id, run_id, signal_type, data, created_at, consumed_at)
2. Alembic migration for the new table
3. Modify `build_vertex()` to poll `execution_signals` after each vertex build (when checkpointing enabled)
4. Wire pause endpoint to write PAUSE signal instead of updating job status directly
5. Wire resume endpoint to load checkpoint from `DatabaseCheckpointStore` and resume graph

**Tests:** Write signal → executor picks it up → checkpoint created. Full round-trip: API pause → checkpoint → API resume → completion.

### Phase F: A2A integration

1. Update A2A router to catch `GraphPausedException`
2. Save checkpoint, transition task to `input-required`
3. On follow-up, load checkpoint and resume
4. Wire to both `message:send` and `message:stream`

**Tests:** Full A2A round-trip with checkpoint: send → pause → follow-up → complete.

### Phase G: Frontend support for PAUSED state

The frontend currently has no awareness of the `PAUSED` job status. A paused job will render as "in progress" or fall through to an unknown/default state. Needed:

1. Add `PAUSED` to the frontend `JobStatus` type/enum
2. Render paused state in the job/workflow status UI (distinct icon, color, label)
3. Add "Pause" and "Resume" action buttons to the workflow execution panel
4. Wire buttons to `POST /api/v2/workflows/pause` and `POST /api/v2/workflows/resume`
5. Handle the resume input flow — if the pause was triggered by an agent needing clarification, the UI should prompt the user for input and include it in the resume request
6. Poll or subscribe for status transitions: `in_progress → paused → in_progress → completed`

### Phase H: Durability and cleanup

1. `DatabaseCheckpointStore` implementation (SQLAlchemy model + Alembic migration)
2. Background task to prune expired checkpoints
3. Handle server restart (checkpoints survive, flows can be resumed)
4. Handle checkpoint-not-found (task expired)
5. Metrics: checkpoint size, save/load latency

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Vertex results contain non-serializable objects | High | Medium | Use `__getstate__`/`__setstate__` already on Vertex. Test serialization for each component type. Fallback to re-execution for non-serializable vertices. |
| Checkpoint size too large (LLM context, embeddings) | Medium | Low | Compress checkpoint data. Set max size limit. Large objects stored by reference (e.g., file path) not value. |
| Graph structure changes between pause and resume (user edited flow) | Low | High | Validate checkpoint's graph hash matches current flow before resuming. Reject stale checkpoints. |
| Long pause times (hours/days) | Medium | Low | Configurable TTL. Database-backed store survives restarts. Inform client when checkpoint expires. |
| Component side effects on re-execution after failed resume | Low | Medium | Checkpoints record which vertices completed. Only unbuilt vertices execute on resume. |

---

## Open Questions

1. **Should the Agent component itself support pause/resume?** The Agent runs a LangChain AgentExecutor internally with its own tool-calling loop. Pausing mid-agent-reasoning (between tool calls) would require checkpointing the AgentExecutor state, which is significantly more complex than pausing at graph layer boundaries.

2. **What about streaming + checkpointing?** For `message:stream`, the SSE connection is held open during execution. On pause, should the stream close (client reconnects for next turn) or stay open (client sends follow-up on a separate request)?

3. **Checkpoint storage limits?** Should there be a per-user or per-flow limit on active checkpoints to prevent abuse?

---

## Design Decisions: Opt-In, Multi-Worker, and Signal Polling

### Opt-in mechanism

Checkpointing must be **opt-in**, not enabled by default. The feature adds overhead:
- Database writes after each component execution (for signal checking)
- Serialization cost for checkpoint data
- Storage consumption for persisted checkpoints

**Enablement model:**
- **Flow-level flag:** `flow.checkpointing_enabled = True` — set in flow metadata or via API when configuring a flow for A2A or human-in-the-loop use.
- **When disabled (default):** The graph executor skips all signal checks and checkpoint logic. Zero overhead on the hot path.
- **When enabled:** After each vertex build, the executor checks the database for pause/stop signals and creates checkpoints at layer boundaries.

### Multi-worker coordination via database signals

In production, Langflow runs behind multiple workers (gunicorn/uvicorn). An in-memory `_pause_requested` flag set on one worker's Graph instance is invisible to other workers and to external callers. **The database is the coordination mechanism.**

**Signal flow:**

```
External caller (A2A client, UI, API)
        │
        ▼
  ┌─────────────────────────┐
  │  execution_signals table │  ← source of truth
  │  (flow_id, run_id,       │
  │   signal: PAUSE|STOP,    │
  │   created_at, data)      │
  └─────────────────────────┘
        ▲               │
        │               ▼
  Worker 1          Worker 2
  (sends signal)    (executing graph, polls for signals)
```

**Database table:** `execution_signals`
- `id` (UUID, PK)
- `flow_id` (str, indexed)
- `run_id` (str, indexed)
- `signal_type` (enum: PAUSE, STOP, RESUME)
- `data` (JSON — e.g., `{"reason": "input-required", "question": "..."}`)
- `created_at` (datetime)
- `consumed_at` (datetime, nullable — set when the executor processes the signal)

**How it works:**
1. External caller writes a PAUSE signal to `execution_signals` for a specific `run_id`
2. The graph executor, after each vertex build, queries: `SELECT ... FROM execution_signals WHERE run_id = ? AND signal_type = 'PAUSE' AND consumed_at IS NULL`
3. If a signal is found, the executor creates a checkpoint and raises `GraphPausedException`
4. The signal is marked as consumed (`consumed_at = now()`)

This replaces the in-memory `request_pause()` mechanism for production use. The in-memory path remains available for single-process/testing scenarios, but the database signal path is the primary coordination mechanism in multi-worker deployments.

### Per-vertex signal checking (not just per-layer)

The current implementation checks for pause after each layer completes. This is insufficient because:
- A layer with a single long-running Agent vertex could take minutes
- During that time, external pause/stop signals would be ignored

**Revised check points:**
1. **After each vertex build** — The `build_vertex()` method checks for signals after the vertex completes. This is the primary check point.
2. **At layer boundaries** — Redundant check, but ensures no signal is missed between vertex completion and next-layer start.

```python
async def build_vertex(self, vertex_id, ...):
    result = await vertex.build(...)

    # Check for external signals (only if checkpointing enabled)
    if self._checkpointing_enabled:
        await self._check_for_signals()

    return result
```

The overhead per vertex is one lightweight DB query (indexed on `run_id`). For flows with 5-10 vertices, this adds 5-10 queries — negligible compared to LLM call latency.

### Long-running agent signal polling

Agents run an internal tool-calling loop (LangChain AgentExecutor) that may execute many steps within a single vertex build. The graph executor cannot check for signals during this internal loop — it only sees the vertex as "building."

**Future enhancement (not v1):** Inject a signal-checking callback into the Agent's tool-calling loop:

```python
class AgentComponent(Component):
    async def build(self):
        def on_tool_call_complete(tool_name, result):
            # Periodically check for pause signals
            if self.graph._checkpointing_enabled:
                signal = await self.graph._check_for_signals()
                if signal:
                    raise AgentPausedException(...)

        executor = AgentExecutor(
            callbacks=[on_tool_call_complete],
            ...
        )
```

This would allow pausing an agent between tool calls (e.g., after the agent calls a search tool but before it calls a code execution tool). The agent's intermediate state (conversation history, tool results so far) would need to be included in the checkpoint.

**v1 scope:** For v1, we only support pausing at vertex boundaries. If a PAUSE signal arrives while an Agent is mid-execution, it will be processed after the Agent vertex completes. This is acceptable for most use cases — the Agent typically runs for seconds, not minutes.

### Revised architecture diagram

```
┌──────────────────────────────────────────────────────────────┐
│                    Graph Executor                              │
│                                                                │
│  for each vertex (if checkpointing enabled):                  │
│    build vertex                                                │
│    ─── check execution_signals table ───                      │
│    if PAUSE signal found:                                      │
│      persist checkpoint to CheckpointStore (DB)                │
│      mark signal as consumed                                   │
│      raise GraphPausedException(checkpoint_id)                 │
│    if STOP signal found:                                       ��
│      cancel remaining execution                                │
│      raise GraphStoppedException(run_id)                       │
│                                                                │
│  ... later, when external input arrives ...                   │
│                                                                │
│  RESUME signal written to execution_signals                   │
│  API handler loads checkpoint, calls resume_from_checkpoint   │
└──────────────────────────────────────────────────────────────┘
         │                           ▲
         ▼                           │
┌────────────────────────┐  ┌──────────────────────────┐
│ execution_signals (DB) │  │  External Trigger         │
│ CheckpointStore (DB)   │  │  (A2A, webhook, UI)       │
└────────────────────────┘  └──────────────────────────┘
```
