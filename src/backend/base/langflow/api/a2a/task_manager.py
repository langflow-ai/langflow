"""A2A task lifecycle management.

Tracks A2A task state in memory (v1). Provides create, update, get,
list, cancel, and idempotent retry operations.

The task state machine follows the A2A spec:
    SUBMITTED → WORKING → COMPLETED
                        → FAILED
                        → INPUT_REQUIRED (Phase 5)
    Any non-terminal    → CANCELED

For v1, tasks are stored in memory (dict). This is acceptable for
team-scale use. A DB-backed store can be added later without changing
the interface.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

# Terminal states — tasks in these states won't be re-executed
_TERMINAL_STATES = frozenset({"completed", "canceled"})

# States that indicate the task is still in progress
_ACTIVE_STATES = frozenset({"submitted", "working", "input-required"})


class TaskManager:
    """Manages A2A task lifecycle with in-memory storage."""

    def __init__(self):
        # task_id → task dict
        self._tasks: dict[str, dict] = {}
        # task_id → {"event": asyncio.Event, "response_holder": dict}
        # Tracks pending INPUT_REQUIRED requests
        self._pending_inputs: dict[str, dict] = {}

    async def create_task(
        self,
        flow_id: str,
        context_id: str,
        task_id: str | None = None,
    ) -> dict:
        """Create a new task in SUBMITTED state.

        Args:
            flow_id: The Langflow flow being executed.
            context_id: The A2A conversation context.
            task_id: Optional caller-provided ID (for idempotent retry).

        Returns:
            The created task dict.
        """
        if task_id is None:
            task_id = str(uuid.uuid4())

        now = datetime.now(timezone.utc).isoformat()

        task = {
            "id": task_id,
            "kind": "task",
            "contextId": context_id,
            "status": {
                "state": "submitted",
                "timestamp": now,
            },
            "artifacts": [],
            "metadata": {
                "flowId": flow_id,
            },
            "_created_at": now,
            "_updated_at": now,
        }

        self._tasks[task_id] = task
        return task

    async def update_state(
        self,
        task_id: str,
        state: str,
        *,
        artifacts: list | None = None,
        error: str | None = None,
    ) -> dict:
        """Update a task's state.

        Args:
            task_id: The task to update.
            state: New state (submitted, working, completed, failed, canceled).
            artifacts: Output artifacts (for completed state).
            error: Error message (for failed state).

        Returns:
            The updated task dict.

        Raises:
            KeyError: If the task doesn't exist.
        """
        task = self._tasks.get(task_id)
        if task is None:
            msg = f"Task {task_id} not found"
            raise KeyError(msg)

        now = datetime.now(timezone.utc).isoformat()

        task["status"]["state"] = state
        task["status"]["timestamp"] = now
        task["_updated_at"] = now

        if artifacts is not None:
            task["artifacts"] = artifacts

        if error is not None:
            task["status"]["message"] = {
                "role": "agent",
                "parts": [{"kind": "text", "text": error}],
            }

        return task

    async def get_task(self, task_id: str) -> dict | None:
        """Retrieve a task by ID.

        Returns None if the task doesn't exist.
        """
        return self._tasks.get(task_id)

    async def list_tasks(
        self,
        context_id: str | None = None,
        flow_id: str | None = None,
    ) -> list[dict]:
        """List tasks, optionally filtered by contextId and/or flow.

        Args:
            context_id: If provided, only return tasks in this conversation.
            flow_id: If provided, only return tasks belonging to this flow.
                     This scopes results to a single agent so one agent's
                     endpoint cannot enumerate another agent's tasks.

        Returns:
            List of task dicts.
        """
        tasks = list(self._tasks.values())
        if context_id is not None:
            tasks = [t for t in tasks if t.get("contextId") == context_id]
        if flow_id is not None:
            tasks = [t for t in tasks if (t.get("metadata") or {}).get("flowId") == flow_id]
        return tasks

    async def handle_retry(self, task_id: str) -> dict | None:
        """Handle an idempotent retry for a given taskId.

        Returns:
            - The existing task if it's completed or still active (don't re-execute)
            - None if the task doesn't exist or failed (allow re-execution)
        """
        task = self._tasks.get(task_id)
        if task is None:
            return None

        state = task["status"]["state"]

        # Terminal (completed, canceled) or active (working) → return cached
        if state in _TERMINAL_STATES or state in _ACTIVE_STATES:
            # Failed tasks should be retried
            return task

        # Failed → allow re-execution
        return None

    async def set_input_required(self, task_id: str, question: str) -> None:
        """Transition a task to INPUT_REQUIRED with a question.

        Called by the request_input tool or detected from flow output.
        The task state is updated and the question is stored so the
        client can see what the agent is asking.

        No execution suspension — the flow completes normally. When
        the client responds, a new flow execution starts.

        Args:
            task_id: The task requesting input.
            question: The question to present to the client.
        """
        await self.update_state(task_id, "input-required")
        self._tasks[task_id]["status"]["message"] = {
            "role": "agent",
            "parts": [{"kind": "text", "text": question}],
        }
        self._pending_inputs[task_id] = {"question": question}

    def is_input_required(self, task_id: str) -> bool:
        """Check if a task is in INPUT_REQUIRED state."""
        task = self._tasks.get(task_id)
        if not task:
            return False
        return task["status"]["state"] == "input-required"

    def has_pending_input(self, task_id: str) -> bool:
        """Check if a task has a pending INPUT_REQUIRED request."""
        return task_id in self._pending_inputs

    async def resolve_input(self, task_id: str) -> None:
        """Mark an INPUT_REQUIRED task as resumed (WORKING).

        Called when the client sends a follow-up. The router will
        start a new flow execution with the response.

        Args:
            task_id: The task to resume.
        """
        self._pending_inputs.pop(task_id, None)
        await self.update_state(task_id, "working")

    async def cleanup_expired_tasks(self, ttl_seconds: int = 86400) -> int:
        """Remove expired terminal tasks older than the TTL.

        Rules:
        - Completed/Failed/Canceled tasks older than ttl_seconds → pruned
        - Working/Input-Required tasks → NEVER pruned (still active)
        - Submitted tasks older than TTL → pruned (likely abandoned)

        Args:
            ttl_seconds: Maximum age in seconds before pruning (default 24h).

        Returns:
            Number of tasks pruned.
        """
        now = datetime.now(timezone.utc)
        to_prune = []

        for task_id, task in self._tasks.items():
            state = task["status"]["state"]

            # Never prune active tasks
            if state in ("working", "input-required"):
                continue

            # Check age
            updated_at_str = task.get("_updated_at", "")
            try:
                updated_at = datetime.fromisoformat(updated_at_str)
                if updated_at.tzinfo is None:
                    updated_at = updated_at.replace(tzinfo=timezone.utc)
            except (ValueError, TypeError):
                continue

            age = (now - updated_at).total_seconds()
            if age > ttl_seconds:
                to_prune.append(task_id)

        for task_id in to_prune:
            del self._tasks[task_id]
            # Also clean up any stale pending inputs
            self._pending_inputs.pop(task_id, None)

        return len(to_prune)
