# System Architecture

```mermaid
graph TB
    classDef fe    fill:#DBEAFE,stroke:#3B82F6,color:#1E3A5F,font-weight:bold
    classDef llmif fill:#E0F2FE,stroke:#0284C7,color:#0C4A6E,font-weight:bold
    classDef be    fill:#DCFCE7,stroke:#16A34A,color:#14532D,font-weight:bold
    classDef llm   fill:#F3E8FF,stroke:#9333EA,color:#3B0764,font-weight:bold
    classDef store fill:#FEF9C3,stroke:#CA8A04,color:#713F12,font-weight:bold
    classDef ext   fill:#FED7AA,stroke:#EA580C,color:#7C2D12,font-weight:bold
    classDef lock  fill:#FEE2E2,stroke:#DC2626,color:#7F1D1D,font-weight:bold

    %% ── FRONTEND ─────────────────────────────────────────────────────
    subgraph FE["🖥️  FRONTEND  ·  React / Langflow Canvas"]
        PD["📁 Project Dashboard"]
        CI["💬 Chat Interface"]
        IC["🎨 Interactive Canvas"]
    end

    %% ── LLM INTERFACE ────────────────────────────────────────────────
    subgraph LLMIF["🔀  LLM INTERFACE  ·  Context & Routing Bridge"]
        CTX["🧠 Context Manager\nassembles history + diagram + spec"]
        ROUTER["🔀 Phase Router\nroutes to active engine"]
        PM["🔒 Prompt Config\nbusiness-managed · no user access"]
    end

    %% ── BACKEND SERVICES ─────────────────────────────────────────────
    subgraph BE["⚙️  BACKEND SERVICES  ·  FastAPI / Langflow Base"]
        PS["🗂️ Project Service\nphase state machine"]
        CS["💬 Conversation Service"]
        DS["📐 Diagram Service"]
        CGS["🏗️ Code Gen Service"]
        GS["🌿 Git Service"]
    end

    %% ── LLM ORCHESTRATION ────────────────────────────────────────────
    subgraph LLMO["🤖  LLM ORCHESTRATION"]
        CE["🔄 Clarification\nEngine"]
        DG["📐 Diagram\nGenerator"]
        DV["✅ Diagram\nValidator"]
        CG["🏗️ Code\nGenerator"]
    end

    %% ── STORAGE ──────────────────────────────────────────────────────
    subgraph STORE["🗄️  STORAGE"]
        GR[("🌿 Internal Git\nspecs · diagrams · code")]
        DB[("🐘 PostgreSQL\nprojects · conversations · phase state")]
    end

    %% ── DELIVERY & EXTERNAL ──────────────────────────────────────────
    subgraph EXT["🔌  DELIVERY & EXTERNAL"]
        LLMAPI["☁️ LLM API\nAnthropic / OpenAI"]
        UG["🐙 User GitHub\noptional push"]
        DL["📦 ZIP Download"]
    end

    %% ── Dashboard → Chat (UI navigation only) ────────────────────────
    PD -- "open / resume project" --> CI

    %% ── Frontend → LLM Interface ─────────────────────────────────────
    CI -- "chat messages" --> CTX
    IC -- "diagram edits" --> CTX
    CTX --> ROUTER
    PM -. "injects prompts & model config" .-> ROUTER

    %% ── LLM Interface pulls live context from Backend ────────────────
    CS -- "conversation history" --> CTX
    PS -- "current phase" --> ROUTER

    %% ── Phase Router → LLM Engines ───────────────────────────────────
    ROUTER -- "clarification phase" --> CE
    ROUTER -- "diagram gen phase" --> DG
    ROUTER -- "refinement phase" --> DV
    ROUTER -- "code gen phase" --> CG

    %% ── LLM Engines → LLM API ────────────────────────────────────────
    CE --> LLMAPI
    DG --> LLMAPI
    DV --> LLMAPI
    CG --> LLMAPI

    %% ── LLM Engines → Context Manager → Frontend (SSE) ───────────────
    CE -- "questions / clarity signal" --> CTX
    DG -- "diagram output" --> CTX
    DV -- "validated diagram" --> CTX
    CG -- "generated code" --> CTX
    CTX -- "SSE: chat responses" --> CI
    CTX -- "SSE: diagram updates" --> IC

    %% ── LLM Interface → Backend (persist & advance phase) ────────────
    CTX -- "persist turn" --> CS
    CTX -- "advance phase" --> PS
    DG -- "commit diagram" --> DS
    DV -- "commit revision" --> DS
    CG -- "commit code" --> CGS

    %% ── Backend → Storage ────────────────────────────────────────────
    CS --> DB
    PS --> DB
    DS --> GR
    CGS --> GR

    %% ── Git Service → Delivery ───────────────────────────────────────
    GR --> GS
    GS --> UG
    GS --> DL

    %% ── Apply styles ─────────────────────────────────────────────────
    class PD,CI,IC fe
    class CTX,ROUTER llmif
    class PM lock
    class PS,CS,DS,CGS,GS be
    class CE,DG,DV,CG llm
    class GR,DB store
    class LLMAPI,UG,DL ext

    style FE fill:#EFF6FF,stroke:#3B82F6,stroke-width:2px
    style LLMIF fill:#E0F2FE,stroke:#0284C7,stroke-width:2px
    style BE fill:#F0FDF4,stroke:#16A34A,stroke-width:2px
    style LLMO fill:#FAF5FF,stroke:#9333EA,stroke-width:2px
    style STORE fill:#FEFCE8,stroke:#CA8A04,stroke-width:2px
    style EXT fill:#FFF7ED,stroke:#EA580C,stroke-width:2px
```

## Component Glossary

| Component | Layer | Responsibility |
|---|---|---|
| **Project Dashboard** | Frontend | List projects; open or resume — navigates user into Chat Interface |
| **Chat Interface** | Frontend | Spec input, clarification Q&A, code delivery — SSE streaming |
| **Interactive Canvas** | Frontend | Render and edit architecture diagrams (xyflow, repurposed from Langflow pipeline canvas) |
| **Context Manager** | LLM Interface | Assembles full LLM context per turn: conversation history + current diagram + spec answers |
| **Phase Router** | LLM Interface | Reads current project phase from Project Service; routes assembled context to the correct LLM engine |
| **Prompt Config** | LLM Interface | Business-managed prompt templates and model config; injected server-side, never exposed to user |
| **Project Service** | Backend | Owns the project phase state machine: `CLARIFICATION → DIAGRAM_GENERATION → DIAGRAM_REFINEMENT → CODE_GENERATION → DONE` |
| **Conversation Service** | Backend | Persists every chat turn; feeds history back to Context Manager on each request |
| **Diagram Service** | Backend | Receives diagram artifacts from LLM engines; commits each version to Git |
| **Code Gen Service** | Backend | Receives generated code from Code Generator; commits files to Git |
| **Git Service** | Backend | All Git operations — push to user GitHub, export ZIP |
| **Clarification Engine** | LLM Orchestration | Multi-turn Q&A; emits a clarity signal when spec is complete |
| **Diagram Generator** | LLM Orchestration | Converts locked spec into a sequence diagram on clarity signal |
| **Diagram Validator** | LLM Orchestration | Given a user-edited diagram + prior context, checks coherence and flags contradictions |
| **Code Generator** | LLM Orchestration | Converts approved diagram + full spec into application code files |
| **Internal Git** | Storage | System of record for all versioned artifacts — specs, diagram revisions, final code |
| **PostgreSQL** | Storage | Operational state — projects, users, conversation history, current phase |
| **LLM API** | External | Anthropic / OpenAI — provider and model fixed by business config |
| **User GitHub** | External | Optional — Git Service pushes final repo on user request |
| **ZIP Download** | External | Git Service packages codebase as a downloadable archive |

## Key Design Decisions

- **Project Dashboard is navigation-only**: It has no direct backend connections. Opening or resuming a project simply navigates to the Chat Interface, which loads the full session state (prior messages + current diagram) from the backend.
- **LLM Interface as the bridge**: Chat Interface and Interactive Canvas both funnel into the Context Manager, which assembles a complete, coherent context before any LLM call. The Phase Router then decides which engine to invoke — the frontend never calls LLM engines directly.
- **Prompt Config is server-side only**: LLM selection, model parameters, and all prompt templates are business-configured at deploy time. The frontend has no visibility into them.
- **Git as the artifact store**: Every intermediate state (spec answers, each diagram revision, final code) is a versioned Git commit. This enables future re-architecture flows — user opens an old project, modifies the diagram, and regenerates code with full history intact.
- **Canvas repurposed, not replaced**: The Interactive Canvas reuses Langflow's xyflow infrastructure but renders architecture diagram nodes, not LLM pipeline nodes. Node types and semantics are completely new.
- **SSE streaming end-to-end**: All LLM responses flow back through the Context Manager as Server-Sent Events to Chat Interface or Interactive Canvas — users see questions and diagram updates in real time.
- **Phase state machine prevents out-of-order actions**: A user cannot trigger code generation before diagram approval, and cannot modify diagrams before the clarification phase is complete.
