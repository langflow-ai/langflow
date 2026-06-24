"""Host seam for the shared v2 workflow router.

lfx owns the env-neutral HTTP router (:mod:`lfx.workflow.router`); the host
supplies only the DB/tenant-bound capabilities the router cannot have in bare
serve: resolve the caller's identity (an opaque token), fetch-and-authorize a
flow, hand back a read-only request session (or ``None``), and answer whether
durable background runs are available.

Identity is opaque ``Any`` on purpose: lfx must never read ``.id`` /
``.is_superuser`` off the caller. langflow passes a ``UserRead``; bare serve
passes the validated api-key ``str``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from pydantic import BaseModel

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from fastapi import Request

    from lfx.schema.workflow import (
        WorkflowExecutionResponse,
        WorkflowJobResponse,
        WorkflowStopResponse,
    )
    from lfx.workflow.actions import WorkflowAction
    from lfx.workflow.converters import ParsedWorkflowRun


class ResolvedFlow(BaseModel):
    """Post-auth, post-RBAC artifact the router runs.

    No tenant fields leak into the router body. ``graph`` is the run-ready
    ``Graph``; the host owns any deepcopy/stamp semantics before handing it back.
    """

    model_config = {"arbitrary_types_allowed": True}

    flow_id: str
    graph: Any  # the run-ready Graph (deep-copied/stamped by the host)
    session_id_default: str | None = None  # SSE thread_id / session fallback


@runtime_checkable
class WorkflowHost(Protocol):
    """The capabilities the router needs from its host."""

    async def resolve_caller(self, request: Request) -> Any: ...
    async def get_flow(self, flow_id: str, caller: Any) -> ResolvedFlow: ...
    async def authorize(self, caller: Any, flow: ResolvedFlow, action: WorkflowAction) -> None: ...

    @asynccontextmanager
    async def session(self) -> AsyncIterator[Any | None]: ...

    @property
    def supports_background(self) -> bool: ...

    @property
    def supports_request_overrides(self) -> bool: ...

    async def submit_background(
        self,
        parsed: ParsedWorkflowRun,
        flow: ResolvedFlow,
        caller: Any,
        *,
        stream_protocol: str,
    ) -> WorkflowJobResponse: ...

    async def get_job_status(
        self, job_id: str, caller: Any, session: Any
    ) -> WorkflowExecutionResponse | WorkflowJobResponse: ...

    async def stop_job(self, job_id: str, caller: Any) -> WorkflowStopResponse: ...


class WorkflowHostBase(ABC):
    """Minimal base for a no-db host: implement only ``resolve_caller`` + ``get_flow``.

    The background methods raise ``NotImplementedError`` by default; the router
    never calls them unless ``supports_background`` is ``True``.
    """

    supports_background: bool = False
    supports_request_overrides: bool = False

    @abstractmethod
    async def resolve_caller(self, request: Request) -> Any: ...

    @abstractmethod
    async def get_flow(self, flow_id: str, caller: Any) -> ResolvedFlow: ...

    async def authorize(self, caller: Any, flow: ResolvedFlow, action: WorkflowAction) -> None:  # noqa: ARG002
        """Single-tenant default: no-op."""
        return

    @asynccontextmanager
    async def session(self) -> AsyncIterator[Any | None]:
        """No-db default: no request session."""
        yield None

    async def submit_background(
        self,
        parsed: ParsedWorkflowRun,
        flow: ResolvedFlow,
        caller: Any,
        *,
        stream_protocol: str,
    ) -> WorkflowJobResponse:
        raise NotImplementedError

    async def get_job_status(
        self, job_id: str, caller: Any, session: Any
    ) -> WorkflowExecutionResponse | WorkflowJobResponse:
        raise NotImplementedError

    async def stop_job(self, job_id: str, caller: Any) -> WorkflowStopResponse:
        raise NotImplementedError
