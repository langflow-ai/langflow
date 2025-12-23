# Human-In-The-Loop (HITL) Approval System for Langflow

## Executive Summary

This document outlines the architecture and implementation plan for a Human-In-The-Loop (HITL) approval system in Langflow. The system enables human oversight and intervention during flow execution, allowing designated approvers to review, approve, or reject specific actions before they proceed.

The design prioritizes:
- **Scalability**: Ready for cloud deployment with Knative pod scaling
- **Statelessness**: Execution state persisted to database, not in-memory
- **Resilience**: Graceful handling of approver disconnections and timeouts
- **Extensibility**: Plugin architecture for custom approval logic

This plan incorporates lessons learned from analyzing LangGraph and Agno HITL implementations.

---

## Table of Contents

1. [Framework Comparison & Design Decisions](#1-framework-comparison--design-decisions)
2. [System Requirements](#2-system-requirements)
3. [Architecture Overview](#3-architecture-overview)
4. [Database Schema](#4-database-schema)
5. [Backend Implementation](#5-backend-implementation)
6. [Frontend Implementation](#6-frontend-implementation)
7. [Scalability & Cloud Readiness](#7-scalability--cloud-readiness)
8. [Implementation Phases](#8-implementation-phases)
9. [API Reference](#9-api-reference)

---

## 1. Framework Comparison & Design Decisions

### 1.1 LangGraph HITL Analysis

**Source Code Review**: `/tmp/hitl-research/langgraph/libs/langgraph/langgraph/types.py`, `interrupt.py`, `checkpoint/base/__init__.py`

LangGraph implements HITL through an **interrupt/resume pattern**:

```python
# LangGraph's interrupt mechanism (simplified)
def interrupt(value: Any) -> Any:
    """Interrupt the graph with a resumable exception from within a node."""
    raise GraphInterrupt(Interrupt(value=value, resumable=True))

@dataclass
class Command:
    graph: str | None = None     # Target subgraph
    update: Any | None = None    # State updates to apply
    resume: dict | Any = None    # Value to return from interrupt
    goto: Send | Sequence = ()   # Node routing on resume
```

**Key LangGraph Patterns:**

| Pattern | Description | Langflow Applicability |
|---------|-------------|------------------------|
| `interrupt()` function | Raises `GraphInterrupt` exception to pause | ✅ Adopt - Clean pattern for pausing execution |
| `Command` for resume | Structured resume with state updates | ✅ Adopt - Allows modifying state on resume |
| `BaseCheckpointSaver` | Abstract checkpointer for state persistence | ✅ Adopt - Matches our pluggable backend design |
| `thread_id` scoping | State scoped to conversation threads | ⚠️ Adapt - Use flow_id + run_id instead |
| `HumanInterruptConfig` | Configurable response types (accept/ignore/respond/edit) | ✅ Adopt - Flexible approval options |
| Super-step checkpoints | Checkpoint at every node boundary | ⚠️ Partial - Only checkpoint at approval gates |

**LangGraph Response Types:**
```python
class HumanInterruptConfig(TypedDict):
    allow_ignore: bool   # Skip the interrupt entirely
    allow_respond: bool  # Provide text feedback
    allow_edit: bool     # Modify the pending action
    allow_accept: bool   # Approve as-is
```

### 1.2 Agno HITL Analysis

**Source Code Review**: `/tmp/hitl-research/agno/libs/agno/agno/run/requirement.py`, `tools/decorator.py`, `models/response.py`

Agno implements HITL through a **tool decorator pattern**:

```python
# Agno's tool decorator approach (simplified)
@tool(requires_confirmation=True)
def get_data(query: str) -> str:
    """Tool that requires user confirmation before execution."""
    return fetch_data(query)

# Usage pattern
run_response = agent.run("Get the data")
for requirement in run_response.active_requirements:
    if requirement.needs_confirmation:
        requirement.confirm()  # or requirement.reject()

# Resume execution
run_response = agent.continue_run(
    run_id=run_response.run_id,
    requirements=run_response.requirements,
)
```

**Key Agno Patterns:**

| Pattern | Description | Langflow Applicability |
|---------|-------------|------------------------|
| `@tool` decorator flags | `requires_confirmation`, `requires_user_input`, `external_execution` | ✅ Adopt - Component-level HITL config |
| `RunRequirement` class | Tracks what's needed to resume | ✅ Adopt - Clean abstraction for pending approvals |
| `ToolExecution` state | `is_paused`, `confirmed`, `answered` properties | ✅ Adopt - Track execution state |
| `continue_run()` method | Explicit resume with updated requirements | ✅ Adopt - Clear API for resumption |
| Exclusive flags | Only one HITL type at a time | ❌ Skip - Allow combinations in Langflow |
| DB persistence (SqliteDb) | State stored for cross-session resume | ✅ Already planned |

**Agno HITL Types:**
```python
@dataclass
class RunRequirement:
    needs_confirmation: bool      # Approval required
    needs_user_input: bool        # Form input required
    needs_external_execution: bool # Async/webhook execution

    def confirm(self): ...
    def reject(self): ...
    def is_resolved(self) -> bool: ...
```

### 1.3 Pattern Comparison

| Aspect | LangGraph | Agno | Langflow Design |
|--------|-----------|------|-----------------|
| **Interrupt Model** | Exception-based (`GraphInterrupt`) | Return-based (`active_requirements`) | Exception-based (cleaner flow control) |
| **Resume Model** | `Command` with state updates | `continue_run()` with requirements | Hybrid: Command-style with requirement tracking |
| **State Persistence** | Pluggable `CheckpointSaver` | Database (SqliteDb) | Pluggable `ExecutionStateBackend` |
| **HITL Types** | Single flexible `interrupt()` | Three exclusive types | Multiple non-exclusive types |
| **Configuration** | Per-node via code | Per-tool via decorator | Per-component via UI + config |
| **Response Options** | accept/ignore/respond/edit | confirm/reject + input | approve/reject/request_changes/timeout |
| **Multi-approver** | Not built-in | Not built-in | First-class support |
| **Timeout Handling** | Application-level | Not built-in | Built-in with configurable actions |

### 1.4 Design Decisions for Langflow

Based on the analysis, Langflow's HITL system will adopt the following patterns:

**From LangGraph:**
1. **Exception-based interrupts** - Use `ApprovalPendingException` (like `GraphInterrupt`) for clean control flow
2. **Structured resume commands** - Support state modifications on approval (like `Command.update`)
3. **Flexible response types** - Allow approve, reject, and request_changes (like `HumanInterruptConfig`)
4. **Pluggable state backends** - Abstract `ExecutionStateBackend` interface (like `BaseCheckpointSaver`)

**From Agno:**
1. **Requirement tracking** - `ApprovalRequirement` class to track pending approvals (like `RunRequirement`)
2. **Component-level configuration** - Configure HITL via component inputs (like `@tool` decorator)
3. **Explicit resume API** - Clear `resume_after_approval()` endpoint (like `continue_run()`)
4. **Serializable state** - Full execution state serialization with `to_dict()`/`from_dict()` patterns

**Langflow-Specific Additions:**
1. **Multi-approver workflows** - Multiple approvers with configurable quorum
2. **Timeout policies** - Configurable timeout actions (approve/reject/escalate)
3. **Audit trail** - Full decision history for compliance
4. **Visual configuration** - UI-based checkpoint configuration in flow editor
5. **SSE notifications** - Real-time approval events (vs polling)

### 1.5 Core Classes (Informed by Research)

```python
# ApprovalRequirement - Inspired by Agno's RunRequirement
@dataclass
class ApprovalRequirement:
    """Tracks what's needed to resume a paused flow."""

    request_id: UUID
    checkpoint_name: str
    requires_approval: bool = True
    requires_input: bool = False
    requires_external: bool = False

    # Resolution state
    approved: Optional[bool] = None
    user_input: Optional[dict] = None
    external_result: Optional[str] = None

    @property
    def is_resolved(self) -> bool:
        """Check if all requirements are satisfied."""
        if self.requires_approval and self.approved is None:
            return False
        if self.requires_input and self.user_input is None:
            return False
        if self.requires_external and self.external_result is None:
            return False
        return True

    def approve(self, comment: Optional[str] = None) -> None:
        self.approved = True

    def reject(self, comment: Optional[str] = None) -> None:
        self.approved = False


# ApprovalCommand - Inspired by LangGraph's Command
@dataclass
class ApprovalCommand:
    """Command to resume flow execution after approval."""

    request_id: UUID
    action: Literal["resume", "terminate", "retry"]

    # Optional state modifications (like Command.update)
    state_updates: Optional[dict] = None

    # Value to inject at resume point (like Command.resume)
    resume_value: Optional[Any] = None

    # Routing override (like Command.goto)
    goto_vertex: Optional[str] = None


# ApprovalPendingException - Inspired by LangGraph's GraphInterrupt
class ApprovalPendingException(Exception):
    """Raised to pause flow execution at an approval checkpoint."""

    def __init__(
        self,
        request_id: UUID,
        checkpoint_name: str,
        description: str,
        context: dict,
    ):
        self.request_id = request_id
        self.checkpoint_name = checkpoint_name
        self.description = description
        self.context = context
        super().__init__(f"Approval pending: {checkpoint_name}")
```

---

## 2. System Requirements

### 2.1 Functional Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-1 | Flows can define approval checkpoints at specific vertices | Must Have |
| FR-2 | Execution pauses at approval checkpoints until human decision | Must Have |
| FR-3 | Approvers can approve, reject, or request changes | Must Have |
| FR-4 | Rejected flows terminate with appropriate error handling | Must Have |
| FR-5 | Approval requests include context (inputs, outputs, metadata) | Must Have |
| FR-6 | Multiple approvers can be required for a single checkpoint | Should Have |
| FR-7 | Approval requests can have configurable timeouts | Should Have |
| FR-8 | Approvers receive real-time notifications | Should Have |
| FR-9 | Approval history is auditable | Must Have |
| FR-10 | Flows can define conditional approval rules | Could Have |

### 2.2 Non-Functional Requirements

| ID | Requirement | Target |
|----|-------------|--------|
| NFR-1 | Approval state survives pod restarts | 100% |
| NFR-2 | Horizontal scaling support (Knative) | Yes |
| NFR-3 | Approval request latency | < 500ms |
| NFR-4 | Concurrent approval requests | 10,000+ |
| NFR-5 | Audit log retention | Configurable |

### 2.3 Constraints

- Must integrate with existing Langflow authentication system
- Must use existing database infrastructure (PostgreSQL/SQLite)
- Must not require additional message queue infrastructure initially
- Must use SSE for real-time updates (WebSocket not available in Langflow)

---

## 3. Architecture Overview

### 3.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              LANGFLOW HITL SYSTEM                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐    ┌──────────────┐    ┌─────────────┐    ┌────────────┐  │
│  │   Frontend  │◄──►│   API Layer  │◄──►│  Approval   │◄──►│  State     │  │
│  │  (React UI) │    │  (FastAPI)   │    │   Service   │    │  Service   │  │
│  └─────────────┘    └──────────────┘    └─────────────┘    └────────────┘  │
│        │                   │                   │                  │         │
│        │ SSE               │                   │                  ▼         │
│        ▼                   ▼                   ▼           ┌────────────┐  │
│  ┌─────────────┐    ┌──────────────┐    ┌─────────────┐   │ DB/Redis/  │  │
│  │ Notification│    │    Event     │    │   Graph     │   │ Custom     │  │
│  │   Center    │    │   Manager    │◄──►│  Execution  │   └────────────┘  │
│  └─────────────┘    └──────────────┘    └─────────────┘                    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Component Diagram

```
┌────────────────────────────────────────────────────────────────────────────┐
│                            APPROVAL FLOW                                    │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  1. TRIGGER                 2. PAUSE                  3. NOTIFY            │
│  ┌──────────────┐          ┌──────────────┐         ┌──────────────┐      │
│  │  Approval    │          │   Graph      │         │   Event      │      │
│  │  Component   │─────────►│   Engine     │────────►│   Manager    │      │
│  │  Executes    │          │   Pauses     │         │   Emits      │      │
│  └──────────────┘          └──────────────┘         └──────────────┘      │
│                                   │                        │               │
│                                   ▼                        ▼               │
│                            ┌──────────────┐         ┌──────────────┐      │
│                            │   Approval   │         │     SSE      │      │
│                            │   Request    │         │    Stream    │      │
│                            │   (State)    │         │  (Frontend)  │      │
│                            └──────────────┘         └──────────────┘      │
│                                   │                        │               │
│  4. DECIDE                        │                        │               │
│  ┌──────────────┐                 │                        │               │
│  │   Approver   │◄────────────────┼────────────────────────┘               │
│  │   Reviews    │                 │                                        │
│  └──────────────┘                 │                                        │
│         │                         │                                        │
│         ▼                         ▼                                        │
│  ┌──────────────┐          ┌──────────────┐                               │
│  │   Decision   │─────────►│   Resume/    │                               │
│  │   Submitted  │          │   Terminate  │                               │
│  └──────────────┘          └──────────────┘                               │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

### 3.3 State Machine

```
                              ┌─────────────┐
                              │   CREATED   │
                              └──────┬──────┘
                                     │ Execution reaches checkpoint
                                     ▼
                              ┌─────────────┐
                              │   PENDING   │◄────────────────┐
                              └──────┬──────┘                 │
                                     │                        │
                    ┌────────────────┼────────────────┐       │
                    │                │                │       │
                    ▼                ▼                ▼       │
             ┌───────────┐   ┌─────────────┐   ┌───────────┐  │
             │ APPROVED  │   │  REJECTED   │   │  EXPIRED  │  │
             └─────┬─────┘   └──────┬──────┘   └─────┬─────┘  │
                   │                │                │        │
                   │                │                │        │
                   ▼                ▼                ▼        │
             ┌───────────┐   ┌─────────────┐   ┌───────────┐  │
             │  Resume   │   │  Terminate  │   │  Retry?   │──┘
             │ Execution │   │    Flow     │   │  (Config) │
             └───────────┘   └─────────────┘   └───────────┘
```

---

## 4. Database Schema

### 4.1 New Tables

#### ApprovalCheckpoint Table
Stores checkpoint definitions within flows.

```sql
CREATE TABLE approval_checkpoint (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    flow_id UUID NOT NULL REFERENCES flow(id) ON DELETE CASCADE,
    vertex_id VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,

    -- Approval configuration
    required_approvers INTEGER DEFAULT 1,
    timeout_seconds INTEGER DEFAULT 86400,  -- 24 hours default
    auto_action_on_timeout VARCHAR(20) DEFAULT 'reject',  -- 'approve', 'reject', 'escalate'

    -- Approver configuration (JSON array of user IDs or roles)
    allowed_approvers JSONB DEFAULT '[]',

    -- Conditional approval (optional expression)
    condition_expression TEXT,

    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(flow_id, vertex_id)
);

CREATE INDEX idx_approval_checkpoint_flow_id ON approval_checkpoint(flow_id);
CREATE INDEX idx_approval_checkpoint_vertex_id ON approval_checkpoint(vertex_id);
```

#### ApprovalRequest Table
Stores individual approval requests during execution.

```sql
CREATE TABLE approval_request (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    checkpoint_id UUID NOT NULL REFERENCES approval_checkpoint(id) ON DELETE CASCADE,
    flow_id UUID NOT NULL REFERENCES flow(id) ON DELETE CASCADE,
    run_id UUID NOT NULL,
    session_id VARCHAR(255) NOT NULL,

    -- Status tracking
    status VARCHAR(20) NOT NULL DEFAULT 'pending',  -- pending, approved, rejected, expired, cancelled

    -- Context snapshot (immutable after creation)
    vertex_inputs JSONB,
    vertex_outputs JSONB,
    execution_context JSONB,

    -- Timing
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP WITH TIME ZONE,
    resolved_at TIMESTAMP WITH TIME ZONE,

    -- Resolution details
    resolved_by_user_id UUID REFERENCES "user"(id),
    resolution_comment TEXT,

    -- For multi-approver scenarios
    approvals_received INTEGER DEFAULT 0,
    approvals_required INTEGER DEFAULT 1
);

CREATE INDEX idx_approval_request_status ON approval_request(status);
CREATE INDEX idx_approval_request_flow_id ON approval_request(flow_id);
CREATE INDEX idx_approval_request_run_id ON approval_request(run_id);
CREATE INDEX idx_approval_request_session_id ON approval_request(session_id);
CREATE INDEX idx_approval_request_expires_at ON approval_request(expires_at) WHERE status = 'pending';
```

#### ApprovalDecision Table
Stores individual approver decisions (for audit trail and multi-approver).

```sql
CREATE TABLE approval_decision (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id UUID NOT NULL REFERENCES approval_request(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES "user"(id),

    -- Decision
    decision VARCHAR(20) NOT NULL,  -- approved, rejected, request_changes
    comment TEXT,

    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- Prevent duplicate decisions from same user
    UNIQUE(request_id, user_id)
);

CREATE INDEX idx_approval_decision_request_id ON approval_decision(request_id);
CREATE INDEX idx_approval_decision_user_id ON approval_decision(user_id);
```

#### ExecutionState Table
Persists execution state for resumption after approval.

```sql
CREATE TABLE execution_state (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    approval_request_id UUID NOT NULL REFERENCES approval_request(id) ON DELETE CASCADE,
    flow_id UUID NOT NULL REFERENCES flow(id) ON DELETE CASCADE,
    run_id UUID NOT NULL,
    session_id VARCHAR(255) NOT NULL,

    -- Serialized graph state
    graph_state JSONB NOT NULL,

    -- Execution position
    current_vertex_id VARCHAR(255) NOT NULL,
    completed_vertices JSONB DEFAULT '[]',
    pending_vertices JSONB DEFAULT '[]',

    -- Artifacts and results
    vertex_results JSONB DEFAULT '{}',
    artifacts JSONB DEFAULT '{}',

    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(approval_request_id)
);

CREATE INDEX idx_execution_state_flow_id ON execution_state(flow_id);
CREATE INDEX idx_execution_state_run_id ON execution_state(run_id);
```

### 4.2 Existing Table Modifications

#### Flow Table Extension
```sql
ALTER TABLE flow ADD COLUMN hitl_enabled BOOLEAN DEFAULT FALSE;
ALTER TABLE flow ADD COLUMN hitl_config JSONB DEFAULT '{}';
```

#### Message Table Extension
```sql
ALTER TABLE message ADD COLUMN approval_request_id UUID REFERENCES approval_request(id);
ALTER TABLE message ADD COLUMN message_type VARCHAR(50) DEFAULT 'chat';  -- 'chat', 'approval_request', 'approval_decision'
```

---

## 5. Backend Implementation

### 5.1 Directory Structure

```
src/backend/base/langflow/
├── services/
│   ├── approval/
│   │   ├── __init__.py
│   │   ├── service.py              # ApprovalService class
│   │   ├── models.py               # Pydantic models
│   │   ├── exceptions.py           # Custom exceptions
│   │   └── strategies/
│   │       ├── __init__.py
│   │       ├── base.py             # Base approval strategy
│   │       ├── simple.py           # Single approver
│   │       ├── multi.py            # Multi-approver (all/any)
│   │       └── conditional.py      # Condition-based
│   └── execution_state/
│       ├── __init__.py
│       ├── service.py              # ExecutionStateService (abstract)
│       ├── factory.py              # Factory for backend selection
│       ├── backends/
│       │   ├── __init__.py
│       │   ├── base.py             # Abstract backend interface
│       │   ├── database.py         # PostgreSQL/SQLite backend (OSS default)
│       │   └── redis.py            # Redis backend (cloud/scale)
│       └── serializers.py          # Graph state serialization
├── api/
│   └── v1/
│       └── approvals.py            # Approval API endpoints
├── components/
│   └── approval/
│       ├── __init__.py
│       ├── approval_gate.py        # Approval Gate component
│       └── approval_result.py      # Approval Result component
└── database/
    └── models/
        └── approval/
            ├── __init__.py
            ├── checkpoint.py       # ApprovalCheckpoint model
            ├── request.py          # ApprovalRequest model
            ├── decision.py         # ApprovalDecision model
            ├── execution_state.py  # ExecutionState model (DB backend)
            └── crud.py             # CRUD operations
```

### 5.2 Pluggable Execution State Service

The `ExecutionStateService` is designed with a pluggable backend architecture to support different deployment scenarios:

- **Database Backend (Default)**: Uses PostgreSQL/SQLite for OSS/local deployments
- **Redis Backend**: Uses Redis for cloud deployments requiring faster access and TTL
- **Custom Backends**: Extensible for other storage systems (e.g., DynamoDB, Memcached)

```python
# src/backend/base/langflow/services/execution_state/backends/base.py

from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID
from datetime import timedelta

class ExecutionStateBackend(ABC):
    """
    Abstract base class for execution state storage backends.

    Implementations must be stateless and thread-safe to support
    horizontal scaling with Knative pods.
    """

    @abstractmethod
    async def save_state(
        self,
        request_id: UUID,
        state: dict,
        ttl: Optional[timedelta] = None,
    ) -> None:
        """
        Persist execution state.

        Args:
            request_id: Unique identifier for the approval request
            state: Serialized graph execution state
            ttl: Optional time-to-live for automatic cleanup
        """
        ...

    @abstractmethod
    async def get_state(self, request_id: UUID) -> Optional[dict]:
        """
        Retrieve execution state.

        Args:
            request_id: Unique identifier for the approval request

        Returns:
            Serialized state dict or None if not found/expired
        """
        ...

    @abstractmethod
    async def delete_state(self, request_id: UUID) -> bool:
        """
        Delete execution state after successful resumption.

        Args:
            request_id: Unique identifier for the approval request

        Returns:
            True if deleted, False if not found
        """
        ...

    @abstractmethod
    async def extend_ttl(
        self,
        request_id: UUID,
        ttl: timedelta,
    ) -> bool:
        """
        Extend TTL for pending approvals (e.g., when timeout is extended).

        Args:
            request_id: Unique identifier for the approval request
            ttl: New time-to-live duration

        Returns:
            True if extended, False if not found
        """
        ...


# src/backend/base/langflow/services/execution_state/backends/database.py

from sqlalchemy.ext.asyncio import AsyncSession
from langflow.services.execution_state.backends.base import ExecutionStateBackend
from langflow.services.database.models.approval.execution_state import ExecutionStateTable

class DatabaseExecutionStateBackend(ExecutionStateBackend):
    """
    Database-backed execution state storage.

    Default backend for OSS/local deployments using PostgreSQL or SQLite.
    State is stored in the execution_state table with full ACID guarantees.
    """

    def __init__(self, session_factory):
        self._session_factory = session_factory

    async def save_state(
        self,
        request_id: UUID,
        state: dict,
        ttl: Optional[timedelta] = None,
    ) -> None:
        async with self._session_factory() as session:
            # Upsert execution state
            execution_state = ExecutionStateTable(
                approval_request_id=request_id,
                graph_state=state["graph_state"],
                current_vertex_id=state["current_vertex_id"],
                completed_vertices=state["completed_vertices"],
                pending_vertices=state["pending_vertices"],
                vertex_results=state["vertex_results"],
                artifacts=state["artifacts"],
                expires_at=datetime.utcnow() + ttl if ttl else None,
            )
            session.add(execution_state)
            await session.commit()

    async def get_state(self, request_id: UUID) -> Optional[dict]:
        async with self._session_factory() as session:
            result = await session.get(ExecutionStateTable, request_id)
            if not result:
                return None
            if result.expires_at and result.expires_at < datetime.utcnow():
                return None  # Expired
            return {
                "graph_state": result.graph_state,
                "current_vertex_id": result.current_vertex_id,
                "completed_vertices": result.completed_vertices,
                "pending_vertices": result.pending_vertices,
                "vertex_results": result.vertex_results,
                "artifacts": result.artifacts,
            }

    async def delete_state(self, request_id: UUID) -> bool:
        async with self._session_factory() as session:
            result = await session.get(ExecutionStateTable, request_id)
            if result:
                await session.delete(result)
                await session.commit()
                return True
            return False

    async def extend_ttl(self, request_id: UUID, ttl: timedelta) -> bool:
        async with self._session_factory() as session:
            result = await session.get(ExecutionStateTable, request_id)
            if result:
                result.expires_at = datetime.utcnow() + ttl
                await session.commit()
                return True
            return False


# src/backend/base/langflow/services/execution_state/backends/redis.py

import json
from redis.asyncio import Redis
from langflow.services.execution_state.backends.base import ExecutionStateBackend

class RedisExecutionStateBackend(ExecutionStateBackend):
    """
    Redis-backed execution state storage.

    Recommended for cloud deployments with Knative scaling.
    Provides faster access and native TTL support.
    """

    def __init__(self, redis_client: Redis, key_prefix: str = "langflow:exec_state:"):
        self._redis = redis_client
        self._key_prefix = key_prefix

    def _make_key(self, request_id: UUID) -> str:
        return f"{self._key_prefix}{request_id}"

    async def save_state(
        self,
        request_id: UUID,
        state: dict,
        ttl: Optional[timedelta] = None,
    ) -> None:
        key = self._make_key(request_id)
        value = json.dumps(state)

        if ttl:
            await self._redis.setex(key, int(ttl.total_seconds()), value)
        else:
            await self._redis.set(key, value)

    async def get_state(self, request_id: UUID) -> Optional[dict]:
        key = self._make_key(request_id)
        value = await self._redis.get(key)

        if value is None:
            return None

        return json.loads(value)

    async def delete_state(self, request_id: UUID) -> bool:
        key = self._make_key(request_id)
        deleted = await self._redis.delete(key)
        return deleted > 0

    async def extend_ttl(self, request_id: UUID, ttl: timedelta) -> bool:
        key = self._make_key(request_id)
        return await self._redis.expire(key, int(ttl.total_seconds()))


# src/backend/base/langflow/services/execution_state/factory.py

from langflow.services.execution_state.backends.base import ExecutionStateBackend
from langflow.services.execution_state.backends.database import DatabaseExecutionStateBackend
from langflow.services.execution_state.backends.redis import RedisExecutionStateBackend
from langflow.services.settings.service import SettingsService

class ExecutionStateBackendFactory:
    """
    Factory for creating execution state backends based on configuration.
    """

    @staticmethod
    def create(settings: SettingsService) -> ExecutionStateBackend:
        """
        Create the appropriate backend based on settings.

        Configuration via environment variables:
        - LANGFLOW_EXECUTION_STATE_BACKEND: "database" (default) or "redis"
        - LANGFLOW_REDIS_URL: Redis connection URL (required for redis backend)
        """
        backend_type = settings.settings.execution_state_backend or "database"

        if backend_type == "redis":
            redis_url = settings.settings.redis_url
            if not redis_url:
                raise ValueError(
                    "LANGFLOW_REDIS_URL must be set when using redis execution state backend"
                )
            from redis.asyncio import Redis
            redis_client = Redis.from_url(redis_url)
            return RedisExecutionStateBackend(redis_client)

        elif backend_type == "database":
            from langflow.services.deps import get_session_factory
            return DatabaseExecutionStateBackend(get_session_factory())

        else:
            raise ValueError(f"Unknown execution state backend: {backend_type}")


# src/backend/base/langflow/services/execution_state/service.py

from langflow.services.base import Service
from langflow.services.execution_state.backends.base import ExecutionStateBackend
from langflow.services.execution_state.factory import ExecutionStateBackendFactory
from langflow.services.execution_state.serializers import GraphStateSerializer

class ExecutionStateService(Service):
    """
    Service for managing execution state during HITL approval workflows.

    This service abstracts the storage backend, allowing the same API
    to be used regardless of whether state is stored in a database or Redis.
    """

    name = "execution_state_service"

    def __init__(self, settings_service: SettingsService):
        self._backend: ExecutionStateBackend = ExecutionStateBackendFactory.create(
            settings_service
        )
        self._serializer = GraphStateSerializer()

    async def save_execution_state(
        self,
        request_id: UUID,
        graph: "Graph",
        current_vertex_id: str,
        ttl: Optional[timedelta] = None,
    ) -> None:
        """
        Save the current graph execution state for later resumption.
        """
        state = self._serializer.serialize(graph, current_vertex_id)
        await self._backend.save_state(request_id, state, ttl)

    async def restore_execution_state(
        self,
        request_id: UUID,
    ) -> Optional["Graph"]:
        """
        Restore graph execution state for resumption after approval.

        Returns None if state not found or expired.
        """
        state = await self._backend.get_state(request_id)
        if state is None:
            return None

        return self._serializer.deserialize(state)

    async def cleanup_execution_state(self, request_id: UUID) -> bool:
        """
        Clean up execution state after flow completion or rejection.
        """
        return await self._backend.delete_state(request_id)

    async def extend_approval_timeout(
        self,
        request_id: UUID,
        additional_time: timedelta,
    ) -> bool:
        """
        Extend the TTL when approval timeout is extended.
        """
        return await self._backend.extend_ttl(request_id, additional_time)
```

**Configuration Options:**

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `LANGFLOW_EXECUTION_STATE_BACKEND` | `database` | Backend type: `database` or `redis` |
| `LANGFLOW_REDIS_URL` | - | Redis connection URL (required for redis backend) |
| `LANGFLOW_EXECUTION_STATE_TTL` | `86400` | Default TTL in seconds (24 hours) |

**Deployment Recommendations:**

| Deployment | Backend | Rationale |
|------------|---------|-----------|
| Local/Development | `database` | Simpler setup, no additional infrastructure |
| Single-server OSS | `database` | SQLite/PostgreSQL sufficient for moderate load |
| Multi-server OSS | `database` | PostgreSQL provides shared state across servers |
| Cloud/Knative | `redis` | Faster access, native TTL, better for high concurrency |

### 5.3 Core Approval Service Implementation

```python
# src/backend/base/langflow/services/approval/service.py

from datetime import datetime, timedelta
from uuid import UUID
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from langflow.services.base import Service

class ApprovalService(Service):
    """
    Manages the lifecycle of approval requests.

    This service is designed to be stateless - all state is persisted to the database,
    making it compatible with horizontal scaling via Knative.
    """

    name = "approval_service"

    async def create_approval_request(
        self,
        session: AsyncSession,
        *,
        checkpoint_id: UUID,
        flow_id: UUID,
        run_id: UUID,
        session_id: str,
        vertex_inputs: dict,
        vertex_outputs: dict,
        execution_context: dict,
        graph_state: dict,
    ) -> ApprovalRequest:
        """
        Creates a new approval request and persists execution state.

        This method:
        1. Creates the approval request record
        2. Snapshots the current execution state
        3. Emits notification event to approvers
        4. Returns the created request
        """
        # Get checkpoint configuration
        checkpoint = await self._get_checkpoint(session, checkpoint_id)

        # Calculate expiration
        expires_at = datetime.utcnow() + timedelta(seconds=checkpoint.timeout_seconds)

        # Create approval request
        request = ApprovalRequest(
            checkpoint_id=checkpoint_id,
            flow_id=flow_id,
            run_id=run_id,
            session_id=session_id,
            status=ApprovalStatus.PENDING,
            vertex_inputs=vertex_inputs,
            vertex_outputs=vertex_outputs,
            execution_context=execution_context,
            expires_at=expires_at,
            approvals_required=checkpoint.required_approvers,
        )
        session.add(request)
        await session.flush()

        # Persist execution state for resumption
        execution_state = ExecutionState(
            approval_request_id=request.id,
            flow_id=flow_id,
            run_id=run_id,
            session_id=session_id,
            graph_state=graph_state,
            current_vertex_id=execution_context.get("current_vertex_id"),
            completed_vertices=execution_context.get("completed_vertices", []),
            pending_vertices=execution_context.get("pending_vertices", []),
            vertex_results=execution_context.get("vertex_results", {}),
            artifacts=execution_context.get("artifacts", {}),
        )
        session.add(execution_state)
        await session.commit()

        # Emit notification event (will be picked up by SSE stream)
        await self._emit_approval_request_event(request)

        return request

    async def submit_decision(
        self,
        session: AsyncSession,
        *,
        request_id: UUID,
        user_id: UUID,
        decision: str,  # 'approved', 'rejected', 'request_changes'
        comment: Optional[str] = None,
    ) -> ApprovalRequest:
        """
        Submits an approval decision.

        For multi-approver scenarios, this may not immediately resolve the request.
        """
        request = await self._get_request(session, request_id)

        # Validate user can approve
        await self._validate_approver(session, request, user_id)

        # Check request is still pending
        if request.status != ApprovalStatus.PENDING:
            raise ApprovalAlreadyResolvedException(request_id, request.status)

        # Record the decision
        decision_record = ApprovalDecision(
            request_id=request_id,
            user_id=user_id,
            decision=decision,
            comment=comment,
        )
        session.add(decision_record)

        # Update request based on decision and strategy
        await self._process_decision(session, request, decision_record)

        await session.commit()

        # Emit decision event
        await self._emit_decision_event(request, decision_record)

        # If approved, trigger flow resumption
        if request.status == ApprovalStatus.APPROVED:
            await self._trigger_flow_resumption(request)

        return request

    async def get_pending_approvals(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        flow_id: Optional[UUID] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[ApprovalRequest]:
        """
        Gets pending approval requests for a user.

        Filters based on:
        - User is in allowed_approvers list
        - User has appropriate role
        - Request is still pending and not expired
        """
        # Implementation details...
        pass

    async def check_and_expire_requests(self, session: AsyncSession) -> int:
        """
        Background task to expire timed-out requests.

        Called periodically by a background worker or cron job.
        """
        # Find expired pending requests
        # Update status to EXPIRED
        # Emit expiration events
        # Handle auto_action_on_timeout configuration
        pass
```

### 5.4 Approval Gate Component

```python
# src/backend/base/langflow/components/approval/approval_gate.py

from langflow.custom import Component
from langflow.io import (
    MessageInput,
    StrInput,
    IntInput,
    BoolInput,
    DropdownInput,
    Output,
)
from langflow.schema import Data
from langflow.services.deps import get_approval_service

class ApprovalGateComponent(Component):
    """
    Human-In-The-Loop approval gate.

    This component pauses flow execution and waits for human approval
    before allowing data to pass through.
    """

    display_name = "Approval Gate"
    description = "Pauses execution and waits for human approval before continuing."
    icon = "UserCheck"
    name = "ApprovalGate"

    inputs = [
        MessageInput(
            name="input_data",
            display_name="Input Data",
            info="The data to be reviewed for approval.",
        ),
        StrInput(
            name="checkpoint_name",
            display_name="Checkpoint Name",
            info="A descriptive name for this approval checkpoint.",
            value="Approval Required",
        ),
        StrInput(
            name="description",
            display_name="Description",
            info="Description shown to approvers explaining what they're approving.",
            value="",
        ),
        IntInput(
            name="timeout_seconds",
            display_name="Timeout (seconds)",
            info="How long to wait for approval before timing out. Default: 86400 (24 hours)",
            value=86400,
            advanced=True,
        ),
        DropdownInput(
            name="timeout_action",
            display_name="Timeout Action",
            info="Action to take when approval times out.",
            options=["reject", "approve", "escalate"],
            value="reject",
            advanced=True,
        ),
        IntInput(
            name="required_approvers",
            display_name="Required Approvers",
            info="Number of approvers required. Default: 1",
            value=1,
            advanced=True,
        ),
    ]

    outputs = [
        Output(
            display_name="Approved",
            name="approved_output",
            method="approved_response",
            description="Output when approval is granted.",
        ),
        Output(
            display_name="Rejected",
            name="rejected_output",
            method="rejected_response",
            description="Output when approval is denied.",
        ),
    ]

    async def _request_approval(self) -> dict:
        """
        Creates an approval request and pauses execution.

        This method:
        1. Serializes current execution state
        2. Creates approval request in database
        3. Notifies approvers via event system
        4. Raises ApprovalPendingException to pause execution
        """
        approval_service = get_approval_service()

        # Get or create checkpoint configuration
        checkpoint = await self._ensure_checkpoint_exists()

        # Capture execution context
        execution_context = {
            "current_vertex_id": self._vertex.id,
            "completed_vertices": list(self.graph.get_completed_vertices()),
            "pending_vertices": list(self.graph.get_pending_vertices()),
            "vertex_results": self.graph.get_all_results(),
            "artifacts": self.graph.get_all_artifacts(),
        }

        # Create approval request
        request = await approval_service.create_approval_request(
            session=self._session,
            checkpoint_id=checkpoint.id,
            flow_id=self.graph.flow_id,
            run_id=self.graph.run_id,
            session_id=self.graph.session_id,
            vertex_inputs={"input_data": self.input_data},
            vertex_outputs={},
            execution_context=execution_context,
            graph_state=self.graph.serialize_state(),
        )

        # Log the approval request
        self.log(f"Approval requested: {request.id}")

        # Raise exception to pause execution
        # This will be caught by the graph execution engine
        raise ApprovalPendingException(
            request_id=request.id,
            checkpoint_name=self.checkpoint_name,
            description=self.description,
        )

    async def approved_response(self) -> Data:
        """Called when approval is granted."""
        # Check if we have a pending approval
        approval_context = self.ctx.get(f"{self._vertex.id}_approval")

        if not approval_context:
            # First execution - request approval
            await self._request_approval()

        if approval_context.get("status") == "approved":
            return self.input_data

        # Should not reach here - route to rejected
        self.stop("approved_output")
        self.start("rejected_output")
        return Data(text="")

    async def rejected_response(self) -> Data:
        """Called when approval is denied."""
        approval_context = self.ctx.get(f"{self._vertex.id}_approval")

        if approval_context and approval_context.get("status") == "rejected":
            return Data(
                text=f"Approval rejected: {approval_context.get('comment', 'No reason provided')}",
                data={
                    "status": "rejected",
                    "comment": approval_context.get("comment"),
                    "rejected_by": approval_context.get("resolved_by"),
                }
            )

        return Data(text="")
```

### 5.5 Event Integration

```python
# src/backend/base/langflow/events/approval_events.py

from typing import Any
from langflow.events.event_manager import EventManager

def register_approval_events(event_manager: EventManager) -> None:
    """Register approval-related events with the event manager."""

    event_manager.register_event(
        "on_approval_request",
        "approval_request",
    )

    event_manager.register_event(
        "on_approval_decision",
        "approval_decision",
    )

    event_manager.register_event(
        "on_approval_expired",
        "approval_expired",
    )

    event_manager.register_event(
        "on_approval_cancelled",
        "approval_cancelled",
    )


class ApprovalEventData:
    """Standard structure for approval events."""

    @staticmethod
    def request_created(request: "ApprovalRequest") -> dict:
        return {
            "type": "approval_request_created",
            "request_id": str(request.id),
            "checkpoint_name": request.checkpoint.name,
            "description": request.checkpoint.description,
            "flow_id": str(request.flow_id),
            "run_id": str(request.run_id),
            "session_id": request.session_id,
            "expires_at": request.expires_at.isoformat(),
            "vertex_inputs": request.vertex_inputs,
            "vertex_outputs": request.vertex_outputs,
            "approvals_required": request.approvals_required,
            "approvals_received": request.approvals_received,
        }

    @staticmethod
    def decision_made(request: "ApprovalRequest", decision: "ApprovalDecision") -> dict:
        return {
            "type": "approval_decision_made",
            "request_id": str(request.id),
            "decision": decision.decision,
            "decided_by": str(decision.user_id),
            "comment": decision.comment,
            "request_status": request.status,
            "approvals_received": request.approvals_received,
            "approvals_required": request.approvals_required,
        }
```

### 5.6 Graph Execution Integration

```python
# Modifications to src/backend/base/langflow/api/build.py

async def _build_vertex(
    vertex_id: str,
    graph: Graph,
    event_manager: EventManager,
    # ... other params
) -> VertexBuildResponse:
    """
    Build a single vertex, handling approval gates.
    """
    try:
        # Standard vertex build
        result = await graph.build_vertex(vertex_id, ...)
        return result

    except ApprovalPendingException as e:
        # Approval requested - pause execution
        event_manager.on_approval_request(
            data=ApprovalEventData.request_created(e.request)
        )

        # Return special response indicating paused state
        return VertexBuildResponse(
            id=vertex_id,
            status=BuildStatus.AWAITING_APPROVAL,
            approval_request_id=e.request_id,
            data={
                "checkpoint_name": e.checkpoint_name,
                "description": e.description,
            }
        )


# New endpoint for resuming after approval
async def resume_after_approval(
    request_id: UUID,
    session: AsyncSession,
    event_manager: EventManager,
) -> None:
    """
    Resumes flow execution after approval is granted.
    """
    # Get execution state
    execution_state = await get_execution_state(session, request_id)

    # Reconstruct graph from state
    graph = Graph.from_serialized_state(execution_state.graph_state)
    graph.restore_results(execution_state.vertex_results)
    graph.restore_artifacts(execution_state.artifacts)

    # Inject approval decision into context
    approval_request = await get_approval_request(session, request_id)
    graph.context[f"{execution_state.current_vertex_id}_approval"] = {
        "status": approval_request.status,
        "comment": approval_request.resolution_comment,
        "resolved_by": str(approval_request.resolved_by_user_id),
    }

    # Resume from the approval vertex
    await generate_flow_events(
        graph=graph,
        event_manager=event_manager,
        start_vertex_id=execution_state.current_vertex_id,
        # ... other params
    )
```

### 5.7 API Endpoints

```python
# src/backend/base/langflow/api/v1/approvals.py

from fastapi import APIRouter, Depends, HTTPException, Query
from uuid import UUID
from typing import Optional, List

from langflow.api.utils.core import CurrentActiveUser, DbSession
from langflow.services.approval.service import ApprovalService
from langflow.services.approval.models import (
    ApprovalRequestRead,
    ApprovalDecisionCreate,
    ApprovalCheckpointCreate,
    ApprovalCheckpointRead,
)

router = APIRouter(prefix="/approvals", tags=["Approvals"])


@router.get("/pending", response_model=List[ApprovalRequestRead])
async def get_pending_approvals(
    session: DbSession,
    current_user: CurrentActiveUser,
    flow_id: Optional[UUID] = Query(None),
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0),
):
    """
    Get pending approval requests for the current user.

    Returns requests where the user is an authorized approver.
    """
    approval_service = get_approval_service()
    return await approval_service.get_pending_approvals(
        session,
        user_id=current_user.id,
        flow_id=flow_id,
        limit=limit,
        offset=offset,
    )


@router.get("/{request_id}", response_model=ApprovalRequestRead)
async def get_approval_request(
    request_id: UUID,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    """
    Get details of a specific approval request.
    """
    approval_service = get_approval_service()
    request = await approval_service.get_request(session, request_id)

    if not request:
        raise HTTPException(status_code=404, detail="Approval request not found")

    # Check user has access
    await approval_service.validate_viewer(session, request, current_user.id)

    return request


@router.post("/{request_id}/decide", response_model=ApprovalRequestRead)
async def submit_decision(
    request_id: UUID,
    decision: ApprovalDecisionCreate,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    """
    Submit an approval decision.

    Decisions: 'approved', 'rejected', 'request_changes'
    """
    approval_service = get_approval_service()

    return await approval_service.submit_decision(
        session,
        request_id=request_id,
        user_id=current_user.id,
        decision=decision.decision,
        comment=decision.comment,
    )


@router.post("/{request_id}/cancel", response_model=ApprovalRequestRead)
async def cancel_approval_request(
    request_id: UUID,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    """
    Cancel a pending approval request.

    Only the flow owner or superuser can cancel.
    """
    approval_service = get_approval_service()
    return await approval_service.cancel_request(
        session,
        request_id=request_id,
        cancelled_by=current_user.id,
    )


# SSE endpoint for real-time approval updates
@router.get("/events/stream")
async def stream_approval_events(
    session: DbSession,
    current_user: CurrentActiveUser,
    flow_id: Optional[UUID] = Query(None),
):
    """
    Server-Sent Events stream for approval notifications.

    Streams:
    - New approval requests
    - Decision updates
    - Expiration notices
    """
    async def event_generator():
        # Subscribe to approval events for this user
        async for event in approval_event_stream(current_user.id, flow_id):
            yield f"data: {event.json()}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
    )


# Checkpoint management endpoints
@router.post("/checkpoints", response_model=ApprovalCheckpointRead)
async def create_checkpoint(
    checkpoint: ApprovalCheckpointCreate,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    """Create an approval checkpoint for a flow."""
    # Validate user owns the flow
    # Create checkpoint
    pass


@router.get("/checkpoints/{flow_id}", response_model=List[ApprovalCheckpointRead])
async def get_flow_checkpoints(
    flow_id: UUID,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    """Get all approval checkpoints for a flow."""
    pass
```

---

## 6. Frontend Implementation

### 6.1 Component Structure

```
src/frontend/src/
├── components/
│   └── approval/
│       ├── ApprovalBadge.tsx           # Status indicator
│       ├── ApprovalCard.tsx            # Request summary card
│       ├── ApprovalDetails.tsx         # Full request details
│       ├── ApprovalActions.tsx         # Approve/Reject buttons
│       └── ApprovalHistory.tsx         # Decision history
├── modals/
│   └── approvalModal/
│       ├── index.tsx                   # Main modal
│       ├── ApprovalContext.tsx         # Context display
│       └── ApprovalForm.tsx            # Decision form
├── stores/
│   └── approvalStore.ts                # Zustand store
├── pages/
│   └── ApprovalCenterPage/
│       └── index.tsx                   # Dedicated approval page
└── hooks/
    └── useApprovals.ts                 # Approval data hooks
```

### 6.2 Approval Store

```typescript
// src/frontend/src/stores/approvalStore.ts

import { create } from "zustand";
import { ApprovalRequest, ApprovalDecision } from "@/types/approval";

interface ApprovalState {
  // Pending approvals for current user
  pendingApprovals: ApprovalRequest[];

  // Currently selected approval for modal
  selectedApproval: ApprovalRequest | null;

  // Loading states
  isLoading: boolean;
  isSubmitting: boolean;

  // Actions
  fetchPendingApprovals: () => Promise<void>;
  selectApproval: (approval: ApprovalRequest | null) => void;
  submitDecision: (requestId: string, decision: ApprovalDecision) => Promise<void>;

  // Real-time updates
  addApprovalRequest: (request: ApprovalRequest) => void;
  updateApprovalRequest: (requestId: string, updates: Partial<ApprovalRequest>) => void;
  removeApprovalRequest: (requestId: string) => void;

  // SSE connection management
  connectToApprovalStream: () => void;
  disconnectFromApprovalStream: () => void;
}

export const useApprovalStore = create<ApprovalState>((set, get) => ({
  pendingApprovals: [],
  selectedApproval: null,
  isLoading: false,
  isSubmitting: false,

  fetchPendingApprovals: async () => {
    set({ isLoading: true });
    try {
      const response = await api.get("/api/v1/approvals/pending");
      set({ pendingApprovals: response.data });
    } finally {
      set({ isLoading: false });
    }
  },

  selectApproval: (approval) => {
    set({ selectedApproval: approval });
  },

  submitDecision: async (requestId, decision) => {
    set({ isSubmitting: true });
    try {
      await api.post(`/api/v1/approvals/${requestId}/decide`, decision);
      // Remove from pending list
      set((state) => ({
        pendingApprovals: state.pendingApprovals.filter((a) => a.id !== requestId),
        selectedApproval: null,
      }));
    } finally {
      set({ isSubmitting: false });
    }
  },

  addApprovalRequest: (request) => {
    set((state) => ({
      pendingApprovals: [request, ...state.pendingApprovals],
    }));
  },

  updateApprovalRequest: (requestId, updates) => {
    set((state) => ({
      pendingApprovals: state.pendingApprovals.map((a) =>
        a.id === requestId ? { ...a, ...updates } : a
      ),
    }));
  },

  removeApprovalRequest: (requestId) => {
    set((state) => ({
      pendingApprovals: state.pendingApprovals.filter((a) => a.id !== requestId),
    }));
  },

  connectToApprovalStream: () => {
    const eventSource = new EventSource("/api/v1/approvals/events/stream");

    eventSource.onmessage = (event) => {
      const data = JSON.parse(event.data);

      switch (data.type) {
        case "approval_request_created":
          get().addApprovalRequest(data.request);
          // Show notification
          useAlertStore.getState().setNoticeData({
            title: `Approval Required: ${data.request.checkpoint_name}`,
            link: `/approvals/${data.request.id}`,
          });
          break;

        case "approval_decision_made":
          if (data.request_status !== "pending") {
            get().removeApprovalRequest(data.request_id);
          } else {
            get().updateApprovalRequest(data.request_id, {
              approvals_received: data.approvals_received,
            });
          }
          break;

        case "approval_expired":
          get().removeApprovalRequest(data.request_id);
          break;
      }
    };

    // Store reference for cleanup
    (window as any).__approvalEventSource = eventSource;
  },

  disconnectFromApprovalStream: () => {
    const eventSource = (window as any).__approvalEventSource;
    if (eventSource) {
      eventSource.close();
    }
  },
}));
```

### 6.3 Approval Modal Component

```typescript
// src/frontend/src/modals/approvalModal/index.tsx

import { useState } from "react";
import BaseModal from "@/modals/baseModal";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { useApprovalStore } from "@/stores/approvalStore";
import { ApprovalRequest } from "@/types/approval";
import { formatDistanceToNow } from "date-fns";
import { CheckCircle, XCircle, Clock, AlertTriangle } from "lucide-react";
import ReactMarkdown from "react-markdown";

interface ApprovalModalProps {
  approval: ApprovalRequest;
  open: boolean;
  onClose: () => void;
}

export default function ApprovalModal({ approval, open, onClose }: ApprovalModalProps) {
  const [comment, setComment] = useState("");
  const { submitDecision, isSubmitting } = useApprovalStore();

  const handleDecision = async (decision: "approved" | "rejected") => {
    await submitDecision(approval.id, { decision, comment });
    onClose();
  };

  const timeRemaining = formatDistanceToNow(new Date(approval.expires_at), {
    addSuffix: true,
  });

  return (
    <BaseModal size="large" open={open} setOpen={onClose}>
      <BaseModal.Header description="Review and decide on this approval request">
        <div className="flex items-center gap-2">
          <AlertTriangle className="h-5 w-5 text-warning" />
          {approval.checkpoint_name}
        </div>
      </BaseModal.Header>

      <BaseModal.Content>
        <div className="space-y-6">
          {/* Timing info */}
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Clock className="h-4 w-4" />
            <span>Expires {timeRemaining}</span>
          </div>

          {/* Description */}
          {approval.description && (
            <div className="rounded-lg bg-muted p-4">
              <h4 className="font-medium mb-2">Description</h4>
              <ReactMarkdown>{approval.description}</ReactMarkdown>
            </div>
          )}

          {/* Input data preview */}
          <div className="rounded-lg border p-4">
            <h4 className="font-medium mb-2">Data for Review</h4>
            <pre className="overflow-auto max-h-64 text-sm bg-background p-2 rounded">
              {JSON.stringify(approval.vertex_inputs, null, 2)}
            </pre>
          </div>

          {/* Comment input */}
          <div>
            <label className="block text-sm font-medium mb-2">
              Comment (optional)
            </label>
            <Textarea
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              placeholder="Add a comment explaining your decision..."
              rows={3}
            />
          </div>

          {/* Multi-approver progress */}
          {approval.approvals_required > 1 && (
            <div className="text-sm text-muted-foreground">
              Approvals: {approval.approvals_received} / {approval.approvals_required}
            </div>
          )}
        </div>
      </BaseModal.Content>

      <BaseModal.Footer>
        <div className="flex justify-end gap-3">
          <Button
            variant="outline"
            onClick={onClose}
            disabled={isSubmitting}
          >
            Cancel
          </Button>
          <Button
            variant="destructive"
            onClick={() => handleDecision("rejected")}
            loading={isSubmitting}
          >
            <XCircle className="h-4 w-4 mr-2" />
            Reject
          </Button>
          <Button
            variant="default"
            onClick={() => handleDecision("approved")}
            loading={isSubmitting}
          >
            <CheckCircle className="h-4 w-4 mr-2" />
            Approve
          </Button>
        </div>
      </BaseModal.Footer>
    </BaseModal>
  );
}
```

### 6.4 Approval Center Page

```typescript
// src/frontend/src/pages/ApprovalCenterPage/index.tsx

import { useEffect } from "react";
import { useApprovalStore } from "@/stores/approvalStore";
import ApprovalCard from "@/components/approval/ApprovalCard";
import ApprovalModal from "@/modals/approvalModal";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Inbox, History, Settings } from "lucide-react";

export default function ApprovalCenterPage() {
  const {
    pendingApprovals,
    selectedApproval,
    isLoading,
    fetchPendingApprovals,
    selectApproval,
    connectToApprovalStream,
    disconnectFromApprovalStream,
  } = useApprovalStore();

  useEffect(() => {
    fetchPendingApprovals();
    connectToApprovalStream();

    return () => {
      disconnectFromApprovalStream();
    };
  }, []);

  return (
    <div className="container mx-auto py-6">
      <div className="mb-6">
        <h1 className="text-2xl font-bold">Approval Center</h1>
        <p className="text-muted-foreground">
          Review and manage approval requests for your flows
        </p>
      </div>

      <Tabs defaultValue="pending">
        <TabsList>
          <TabsTrigger value="pending" className="flex items-center gap-2">
            <Inbox className="h-4 w-4" />
            Pending
            {pendingApprovals.length > 0 && (
              <Badge variant="secondary">{pendingApprovals.length}</Badge>
            )}
          </TabsTrigger>
          <TabsTrigger value="history" className="flex items-center gap-2">
            <History className="h-4 w-4" />
            History
          </TabsTrigger>
          <TabsTrigger value="settings" className="flex items-center gap-2">
            <Settings className="h-4 w-4" />
            Settings
          </TabsTrigger>
        </TabsList>

        <TabsContent value="pending" className="mt-6">
          {isLoading ? (
            <div className="text-center py-12">Loading...</div>
          ) : pendingApprovals.length === 0 ? (
            <div className="text-center py-12 text-muted-foreground">
              <Inbox className="h-12 w-12 mx-auto mb-4 opacity-50" />
              <p>No pending approvals</p>
            </div>
          ) : (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {pendingApprovals.map((approval) => (
                <ApprovalCard
                  key={approval.id}
                  approval={approval}
                  onClick={() => selectApproval(approval)}
                />
              ))}
            </div>
          )}
        </TabsContent>

        <TabsContent value="history">
          {/* Approval history component */}
        </TabsContent>

        <TabsContent value="settings">
          {/* Notification settings, default timeout, etc. */}
        </TabsContent>
      </Tabs>

      {/* Approval Modal */}
      {selectedApproval && (
        <ApprovalModal
          approval={selectedApproval}
          open={!!selectedApproval}
          onClose={() => selectApproval(null)}
        />
      )}
    </div>
  );
}
```

---

## 7. Scalability & Cloud Readiness

### 7.1 Stateless Design Principles

The HITL system is designed for horizontal scaling with Knative:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        KNATIVE SCALING MODEL                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   ┌─────────┐  ┌─────────┐  ┌─────────┐                               │
│   │  Pod 1  │  │  Pod 2  │  │  Pod N  │   ◄── Stateless API Pods      │
│   └────┬────┘  └────┬────┘  └────┬────┘                               │
│        │            │            │                                     │
│        └────────────┼────────────┘                                     │
│                     │                                                   │
│                     ▼                                                   │
│   ┌─────────────────────────────────────────┐                         │
│   │           Shared Database               │  ◄── PostgreSQL         │
│   │  (Approval State, Execution State)      │      (Persistent)       │
│   └─────────────────────────────────────────┘                         │
│                                                                         │
│   Key Design Decisions:                                                │
│   • No in-memory state between requests                                │
│   • All state persisted to database                                    │
│   • Execution can resume on any pod                                    │
│   • SSE connections can reconnect to any pod                           │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 7.2 State Persistence Strategy

```python
# All execution state is serializable and database-backed

class ExecutionStateSerializer:
    """
    Serializes graph execution state for persistence.

    This enables:
    - Pod restart recovery
    - Load balancing across pods
    - Delayed approval scenarios (hours/days)
    """

    @staticmethod
    def serialize(graph: Graph) -> dict:
        return {
            "flow_data": graph.to_dict(),
            "vertex_states": {
                v.id: {
                    "state": v.state.value,
                    "built": v.built,
                    "built_result": v.built_result,
                    "artifacts": v.artifacts,
                }
                for v in graph.vertices
            },
            "context": dict(graph.context),
            "run_queue": list(graph._run_queue),
            "completed": list(graph.get_completed_vertices()),
        }

    @staticmethod
    def deserialize(data: dict) -> Graph:
        graph = Graph.from_payload(data["flow_data"])

        # Restore vertex states
        for vertex_id, state_data in data["vertex_states"].items():
            vertex = graph.get_vertex(vertex_id)
            vertex.state = VertexStates(state_data["state"])
            vertex.built = state_data["built"]
            vertex.built_result = state_data["built_result"]
            vertex.artifacts = state_data["artifacts"]

        # Restore context
        graph.context.update(data["context"])

        # Restore run queue
        graph._run_queue = deque(data["run_queue"])

        return graph
```

### 7.3 Database Considerations for Scale

```sql
-- Partitioning for large-scale deployments
CREATE TABLE approval_request (
    -- ... columns ...
) PARTITION BY RANGE (created_at);

-- Create monthly partitions
CREATE TABLE approval_request_2024_01 PARTITION OF approval_request
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

-- Index for common queries
CREATE INDEX CONCURRENTLY idx_approval_request_pending_user
ON approval_request (status, flow_id)
WHERE status = 'pending';

-- Cleanup old data
CREATE OR REPLACE FUNCTION cleanup_old_approvals()
RETURNS void AS $$
BEGIN
    DELETE FROM approval_request
    WHERE status != 'pending'
    AND created_at < NOW() - INTERVAL '90 days';
END;
$$ LANGUAGE plpgsql;
```

### 7.4 Future Message Queue Integration

When scaling beyond database-backed events, the system can integrate with message queues:

```python
# Future: Redis Pub/Sub or Kafka integration

class ApprovalEventBus(Protocol):
    """Abstract event bus for approval notifications."""

    async def publish(self, channel: str, event: dict) -> None:
        """Publish an event to subscribers."""
        ...

    async def subscribe(self, channel: str) -> AsyncIterator[dict]:
        """Subscribe to events on a channel."""
        ...


class DatabaseEventBus(ApprovalEventBus):
    """Current implementation: polling-based using database."""
    pass


class RedisEventBus(ApprovalEventBus):
    """Future: Redis pub/sub for real-time notifications."""
    pass


class KafkaEventBus(ApprovalEventBus):
    """Future: Kafka for durable, ordered event streaming."""
    pass
```

### 7.5 Knative Configuration (Reference)

```yaml
# knative-service.yaml (for future reference)
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: langflow-api
spec:
  template:
    metadata:
      annotations:
        # Scale based on concurrent requests
        autoscaling.knative.dev/target: "100"
        autoscaling.knative.dev/metric: "concurrency"
        # Keep minimum instances for approval handling
        autoscaling.knative.dev/min-scale: "2"
    spec:
      containers:
        - image: langflow/langflow:latest
          env:
            # Database connection (shared state)
            - name: LANGFLOW_DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: langflow-secrets
                  key: database-url
            # Stateless mode
            - name: LANGFLOW_CACHE_TYPE
              value: "redis"  # or "database"
            - name: LANGFLOW_APPROVAL_ENABLED
              value: "true"
```

---

## 8. Implementation Phases

### Phase 1: Core Infrastructure

**Deliverables:**
- [ ] Database migrations for approval tables
- [ ] ApprovalService core implementation
- [ ] Basic CRUD operations for approvals
- [ ] Unit tests for approval service

**Files to Create:**
```
src/backend/base/langflow/
├── services/approval/
│   ├── __init__.py
│   ├── service.py
│   ├── models.py
│   └── exceptions.py
├── database/models/approval/
│   ├── __init__.py
│   ├── checkpoint.py
│   ├── request.py
│   ├── decision.py
│   └── crud.py
└── alembic/versions/
    └── xxxx_add_approval_tables.py
```

### Phase 2: Flow Integration

**Deliverables:**
- [ ] ApprovalGate component
- [ ] Graph execution pause/resume logic
- [ ] Execution state serialization
- [ ] Integration tests

**Files to Create/Modify:**
```
src/backend/base/langflow/
├── components/approval/
│   ├── __init__.py
│   └── approval_gate.py
├── api/build.py (modify)
└── graph/graph/base.py (modify - in lfx)
```

### Phase 3: API Layer

**Deliverables:**
- [ ] REST API endpoints
- [ ] SSE streaming endpoint
- [ ] Authentication integration
- [ ] API documentation

**Files to Create:**
```
src/backend/base/langflow/api/v1/
└── approvals.py
```

### Phase 4: Frontend - Core

**Deliverables:**
- [ ] Approval store (Zustand)
- [ ] Approval modal component
- [ ] SSE event handling
- [ ] Basic approval workflow

**Files to Create:**
```
src/frontend/src/
├── stores/approvalStore.ts
├── types/approval.ts
├── modals/approvalModal/
│   └── index.tsx
└── hooks/useApprovals.ts
```

### Phase 5: Frontend - Polish

**Deliverables:**
- [ ] Approval Center page
- [ ] Notification integration
- [ ] Approval history view
- [ ] Settings UI

**Files to Create:**
```
src/frontend/src/
├── pages/ApprovalCenterPage/
│   └── index.tsx
└── components/approval/
    ├── ApprovalCard.tsx
    ├── ApprovalBadge.tsx
    └── ApprovalHistory.tsx
```

### Phase 6: Testing & Documentation

**Deliverables:**
- [ ] End-to-end tests
- [ ] Performance testing
- [ ] User documentation
- [ ] API documentation updates

### Phase 7: Advanced Features

**Optional Deliverables:**
- [ ] Multi-approver workflows
- [ ] Conditional approval rules
- [ ] Approval delegation
- [ ] Escalation policies
- [ ] Slack/Teams integration

---

## 9. API Reference

### 9.1 Approval Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/approvals/pending` | List pending approvals for current user |
| GET | `/api/v1/approvals/{id}` | Get approval request details |
| POST | `/api/v1/approvals/{id}/decide` | Submit approval decision |
| POST | `/api/v1/approvals/{id}/cancel` | Cancel pending approval |
| GET | `/api/v1/approvals/events/stream` | SSE stream for real-time updates |
| GET | `/api/v1/approvals/history` | Get approval history |
| POST | `/api/v1/approvals/checkpoints` | Create approval checkpoint |
| GET | `/api/v1/approvals/checkpoints/{flow_id}` | List flow checkpoints |

### 9.2 Event Types

| Event | Description | Payload |
|-------|-------------|---------|
| `approval_request_created` | New approval request | `{request_id, checkpoint_name, flow_id, expires_at, ...}` |
| `approval_decision_made` | Decision submitted | `{request_id, decision, decided_by, comment, ...}` |
| `approval_expired` | Request timed out | `{request_id, auto_action}` |
| `approval_cancelled` | Request cancelled | `{request_id, cancelled_by}` |

### 9.3 Request/Response Models

```typescript
// ApprovalRequest
interface ApprovalRequest {
  id: string;
  checkpoint_id: string;
  checkpoint_name: string;
  description?: string;
  flow_id: string;
  run_id: string;
  session_id: string;
  status: "pending" | "approved" | "rejected" | "expired" | "cancelled";
  vertex_inputs: Record<string, any>;
  vertex_outputs: Record<string, any>;
  created_at: string;
  expires_at: string;
  resolved_at?: string;
  resolved_by_user_id?: string;
  resolution_comment?: string;
  approvals_received: number;
  approvals_required: number;
}

// ApprovalDecision (request body)
interface ApprovalDecisionCreate {
  decision: "approved" | "rejected" | "request_changes";
  comment?: string;
}
```

---

## Appendix A: Existing Patterns Leveraged

This design builds upon existing Langflow patterns:

1. **State Vertices** (`notify.py`, `listen.py`) - Context-based state management
2. **Conditional Router** - Branch control with `stop()`/`start()`
3. **EventManager** - Event emission and SSE streaming
4. **JobQueueService** - Async job management with queues
5. **BaseModal** - Frontend modal patterns
6. **SSE Streaming** - Real-time event delivery via Server-Sent Events
7. **Zustand Stores** - Frontend state management pattern

## Appendix B: Security Considerations

1. **Authentication**: All approval endpoints require valid JWT
2. **Authorization**: Approvers validated against checkpoint configuration
3. **Audit Trail**: All decisions logged with user ID and timestamp
4. **Data Isolation**: Users can only see approvals they're authorized for
5. **Input Sanitization**: Approval comments sanitized before storage
6. **Rate Limiting**: Consider rate limits on decision submission

## Appendix C: Monitoring & Observability

Recommended metrics to track:

- `approval_requests_created_total` - Counter of requests created
- `approval_requests_pending` - Gauge of current pending requests
- `approval_decision_latency_seconds` - Histogram of time to decision
- `approval_timeout_rate` - Rate of expired requests
- `approval_rejection_rate` - Rate of rejected requests

---

*Document Version: 1.2*
*Last Updated: December 2024*
*Author: Claude Code Assistant*

## Changelog

- **v1.2**: Added comprehensive LangGraph and Agno HITL analysis (Section 1); introduced `ApprovalRequirement`, `ApprovalCommand`, and `ApprovalPendingException` classes based on research; removed time estimates from phases; pattern comparison table added
- **v1.1**: Added pluggable ExecutionStateService with database/Redis backends; removed WebSocket references (not available in Langflow); removed Observer pattern references (dead code)
- **v1.0**: Initial plan document
