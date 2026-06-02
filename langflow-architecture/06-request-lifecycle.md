# 6. End-to-End Request Lifecycle

What actually happens when a user creates a flow and clicks **Run**?

```mermaid
sequenceDiagram
    actor U as User
    participant FE as React UI
    participant FS as flowStore (Zustand)
    participant API as FastAPI Router
    participant Auth as AuthService
    participant DB as DatabaseService
    participant CS as ChatService
    participant G as Graph (LFX)
    participant V as Vertex / Component
    participant LLM as LLM Provider

    U->>FE: drag nodes, connect edges, set params
    FE->>FS: update nodes/edges state
    U->>FE: click "Save"
    FE->>API: POST /api/v1/flows  {name, data: graph JSON}
    API->>Auth: verify JWT
    API->>DB: INSERT Flow row
    DB-->>API: flow_id
    API-->>FE: 200 {flow_id}

    U->>FE: click "Run"
    FE->>API: POST /api/v1/chat/{flow_id}  (SSE)
    API->>Auth: get_current_active_user
    API->>CS: build_graph_from_db(flow_id)
    CS->>DB: SELECT Flow
    CS->>G: Graph.from_payload(flow.data)
    G->>G: validate + topo sort

    loop for each layer
        loop for each vertex in layer
            G->>V: build() → instantiate Component
            V->>V: pull upstream artifacts
            V->>LLM: call (if LLM component)
            LLM-->>V: completion
            V-->>G: built_result
            G-->>API: emit SSE "message" event
            API-->>FE: stream chunk
            FE->>FS: update node output
        end
    end

    G-->>API: SSE "end"
    API->>DB: persist Messages + VertexBuilds
    API-->>FE: close stream
    FE->>U: render final output
```

## What's happening at each phase

### Authoring
The canvas is purely client-side state in `flowStore`. **Save** serializes nodes + edges to JSON and posts to `/api/v1/flows`, which writes a `Flow` row. No execution yet.

### Run
`POST /api/v1/chat/{flow_id}` is a **streaming** endpoint (`StreamingResponse` of Server-Sent Events). The handler in `api/v1/chat.py`:

1. Authenticates via `AuthService`.
2. Asks `ChatService` to build (or reuse a cached) `Graph` from the flow's JSON.
3. Calls `Graph.async_start()`, iterating async over emitted events.
4. Each event is forwarded as SSE to the browser.

### Per-vertex
Inside the engine each `Vertex` is **built** (its `Component` is instantiated and its parameters are bound) and then **run** (the method named in the wired `Output` is called). If the component is an LLM node, this is where the external call happens.

### Persistence
On `end`, the chat router persists:
- Conversation messages → `Message` table
- Per-vertex build artifacts → `VertexBuild` table

These feed the Playground's history view and the observability integrations.

### Frontend response
The frontend's SSE consumer pushes each chunk into `flowStore`, which causes the corresponding canvas node to update its output preview live. When the `end` event arrives, the stream closes and the final state is committed.
