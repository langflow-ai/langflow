"""Database-backed A2A task store.

Drop-in replacement for the in-memory ``TaskManager`` that persists task
state to the ``a2a_task`` table via short-lived sessions. Tasks therefore
survive process restarts and are visible across workers.

The method surface mirrors ``TaskManager`` and returns the same A2A Task
dict shape, so the router is agnostic to which store backs it. One
difference: ``is_input_required`` is async here (it reads the DB).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlmodel import delete, select

from langflow.services.database.models.a2a_task import A2ATask
from langflow.services.deps import session_scope

# Terminal states — tasks here won't be re-executed on retry.
_TERMINAL_STATES = frozenset({"completed", "canceled"})
# States that indicate the task is still in progress.
_ACTIVE_STATES = frozenset({"submitted", "working", "input-required"})


class DatabaseTaskManager:
    """Manages A2A task lifecycle backed by the ``a2a_task`` table."""

    async def create_task(self, flow_id: str, context_id: str, task_id: str | None = None) -> dict:
        if task_id is None:
            task_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        async with session_scope() as session:
            # If a row already exists (idempotent re-send), reset it for re-execution.
            existing = await session.get(A2ATask, task_id)
            if existing is not None:
                existing.state = "submitted"
                existing.artifacts = []
                existing.status_message = None
                existing.context_id = context_id
                existing.flow_id = flow_id
                existing.updated_at = now
                session.add(existing)
                await session.flush()
                return existing.to_a2a_dict()

            task = A2ATask(
                task_id=task_id,
                context_id=context_id,
                flow_id=flow_id,
                state="submitted",
                artifacts=[],
                task_metadata={"flowId": flow_id},
                created_at=now,
                updated_at=now,
            )
            session.add(task)
            await session.flush()
            return task.to_a2a_dict()

    async def update_state(
        self,
        task_id: str,
        state: str,
        *,
        artifacts: list | None = None,
        error: str | None = None,
    ) -> dict:
        async with session_scope() as session:
            task = await session.get(A2ATask, task_id)
            if task is None:
                msg = f"Task {task_id} not found"
                raise KeyError(msg)
            task.state = state
            task.updated_at = datetime.now(timezone.utc)
            if artifacts is not None:
                task.artifacts = artifacts
            if error is not None:
                task.status_message = {
                    "role": "agent",
                    "parts": [{"kind": "text", "text": error}],
                }
            session.add(task)
            await session.flush()
            return task.to_a2a_dict()

    async def get_task(self, task_id: str) -> dict | None:
        async with session_scope() as session:
            task = await session.get(A2ATask, task_id)
            return task.to_a2a_dict() if task is not None else None

    async def list_tasks(self, context_id: str | None = None, flow_id: str | None = None) -> list[dict]:
        async with session_scope() as session:
            stmt = select(A2ATask)
            if context_id is not None:
                stmt = stmt.where(A2ATask.context_id == context_id)
            if flow_id is not None:
                stmt = stmt.where(A2ATask.flow_id == flow_id)
            result = await session.exec(stmt)
            return [row.to_a2a_dict() for row in result.all()]

    async def handle_retry(self, task_id: str) -> dict | None:
        """Return the cached task for completed/active tasks; None for missing/failed."""
        async with session_scope() as session:
            task = await session.get(A2ATask, task_id)
            if task is None:
                return None
            if task.state in _TERMINAL_STATES or task.state in _ACTIVE_STATES:
                return task.to_a2a_dict()
            # Failed → allow re-execution.
            return None

    async def set_input_required(self, task_id: str, question: str) -> None:
        async with session_scope() as session:
            task = await session.get(A2ATask, task_id)
            if task is None:
                msg = f"Task {task_id} not found"
                raise KeyError(msg)
            task.state = "input-required"
            task.status_message = {
                "role": "agent",
                "parts": [{"kind": "text", "text": question}],
            }
            task.updated_at = datetime.now(timezone.utc)
            session.add(task)
            await session.flush()

    async def is_input_required(self, task_id: str) -> bool:
        async with session_scope() as session:
            task = await session.get(A2ATask, task_id)
            return task is not None and task.state == "input-required"

    async def resolve_input(self, task_id: str) -> None:
        """Mark an INPUT_REQUIRED task as resumed (WORKING)."""
        async with session_scope() as session:
            task = await session.get(A2ATask, task_id)
            if task is None:
                return
            task.state = "working"
            task.updated_at = datetime.now(timezone.utc)
            session.add(task)
            await session.flush()

    async def cleanup_expired_tasks(self, ttl_seconds: int = 86400) -> int:
        """Delete terminal/abandoned tasks older than the TTL. Active tasks are kept."""
        cutoff = datetime.now(timezone.utc).timestamp() - ttl_seconds
        removed = 0
        async with session_scope() as session:
            result = await session.exec(select(A2ATask))
            stale_ids = [
                row.task_id
                for row in result.all()
                if row.state not in ("working", "input-required") and row.updated_at.timestamp() < cutoff
            ]
            if stale_ids:
                await session.exec(delete(A2ATask).where(A2ATask.task_id.in_(stale_ids)))  # type: ignore[attr-defined]
                removed = len(stale_ids)
        return removed
