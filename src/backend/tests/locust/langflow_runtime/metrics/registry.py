"""Worker-local tracked state for performance-suite drain and correctness checks."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

try:
    from gevent.lock import RLock
except ImportError:
    from threading import RLock


@dataclass
class TrackedWorkflowJob:
    job_id: str
    flow_id: str
    accepted_at: datetime | None = None
    started_at: datetime | None = None
    terminal_at: datetime | None = None
    status: str | None = None
    success: bool | None = None


@dataclass
class TrackedWebhookCopy:
    copy_id: str
    endpoint: str
    accepted_count: int = 0
    completed_count: int = 0
    in_flight: int = 0


@dataclass
class TrackedHitlRequest:
    job_id: str
    request_id: str
    flow_id: str
    phase: str


@dataclass
class TrackedMcpCall:
    tool_name: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    success: bool | None = None


_TERMINAL_WORKFLOW_STATUSES = frozenset({"completed", "failed", "cancelled", "timed_out"})
_HITL_TERMINAL_PHASES = frozenset({"completed", "failed", "cancelled", "timed_out"})


class Registry:
    """Gevent-safe worker-local registry of in-flight performance-suite entities."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._workflows: dict[str, TrackedWorkflowJob] = {}
        self._webhooks: dict[str, TrackedWebhookCopy] = {}
        self._hitl: dict[str, TrackedHitlRequest] = {}
        self._mcp: list[TrackedMcpCall] = []

    def register_workflow(self, job: TrackedWorkflowJob) -> None:
        with self._lock:
            self._workflows[job.job_id] = job

    def update_workflow(self, job_id: str, **fields: Any) -> None:
        with self._lock:
            job = self._workflows.get(job_id)
            if job is None:
                return
            for key, value in fields.items():
                if hasattr(job, key):
                    setattr(job, key, value)

    def list_workflows(self) -> list[TrackedWorkflowJob]:
        with self._lock:
            return list(self._workflows.values())

    def clear_workflows(self) -> None:
        with self._lock:
            self._workflows.clear()

    def register_webhook(self, copy: TrackedWebhookCopy) -> None:
        with self._lock:
            self._webhooks[copy.copy_id] = copy

    def update_webhook(self, copy_id: str, **fields: Any) -> None:
        with self._lock:
            copy = self._webhooks.get(copy_id)
            if copy is None:
                return
            for key, value in fields.items():
                if hasattr(copy, key):
                    setattr(copy, key, value)

    def list_webhooks(self) -> list[TrackedWebhookCopy]:
        with self._lock:
            return list(self._webhooks.values())

    def clear_webhooks(self) -> None:
        with self._lock:
            self._webhooks.clear()

    def register_hitl(self, request: TrackedHitlRequest) -> None:
        with self._lock:
            self._hitl[request.request_id] = request

    def update_hitl(self, request_id: str, **fields: Any) -> None:
        with self._lock:
            row = self._hitl.get(request_id)
            if row is None:
                return
            for key, value in fields.items():
                if hasattr(row, key):
                    setattr(row, key, value)

    def list_hitl(self) -> list[TrackedHitlRequest]:
        with self._lock:
            return list(self._hitl.values())

    def clear_hitl(self) -> None:
        with self._lock:
            self._hitl.clear()

    def register_mcp(self, call: TrackedMcpCall) -> None:
        with self._lock:
            self._mcp.append(call)

    def update_mcp(self, index: int, **fields: Any) -> None:
        with self._lock:
            if index < 0 or index >= len(self._mcp):
                return
            call = self._mcp[index]
            for key, value in fields.items():
                if hasattr(call, key):
                    setattr(call, key, value)

    def list_mcp(self) -> list[TrackedMcpCall]:
        with self._lock:
            return list(self._mcp)

    def clear_mcp(self) -> None:
        with self._lock:
            self._mcp.clear()

    def clear_all(self) -> None:
        with self._lock:
            self._workflows.clear()
            self._webhooks.clear()
            self._hitl.clear()
            self._mcp.clear()

    def _outstanding_workflows_unlocked(self) -> list[TrackedWorkflowJob]:
        return [
            job
            for job in self._workflows.values()
            if job.terminal_at is None and (job.status is None or job.status not in _TERMINAL_WORKFLOW_STATUSES)
        ]

    def _outstanding_webhooks_unlocked(self) -> list[TrackedWebhookCopy]:
        return [
            copy
            for copy in self._webhooks.values()
            if copy.in_flight > 0 or copy.accepted_count != copy.completed_count
        ]

    def _residual_hitl_unlocked(self) -> list[TrackedHitlRequest]:
        return [row for row in self._hitl.values() if row.phase not in _HITL_TERMINAL_PHASES]

    def outstanding_workflows(self) -> list[TrackedWorkflowJob]:
        with self._lock:
            return self._outstanding_workflows_unlocked()

    def outstanding_webhooks(self) -> list[TrackedWebhookCopy]:
        with self._lock:
            return self._outstanding_webhooks_unlocked()

    def residual_hitl(self) -> list[TrackedHitlRequest]:
        with self._lock:
            return self._residual_hitl_unlocked()

    def drain_snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "outstanding_workflows": [job.job_id for job in self._outstanding_workflows_unlocked()],
                "outstanding_webhooks": [copy.copy_id for copy in self._outstanding_webhooks_unlocked()],
                "residual_hitl": [row.request_id for row in self._residual_hitl_unlocked()],
            }


_REGISTRY: Registry | None = None


def get_registry() -> Registry:
    """Return the process-local registry singleton."""
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = Registry()
    return _REGISTRY
