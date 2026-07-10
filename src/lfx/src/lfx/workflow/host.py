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

    from fastapi import BackgroundTasks, Request
    from starlette.responses import Response

    from lfx.schema.workflow import (
        WorkflowExecutionResponse,
        WorkflowJobResponse,
        WorkflowStopResponse,
    )
    from lfx.workflow.actions import WorkflowAction
    from lfx.workflow.converters import ParsedWorkflowRun


class ResolvedFlow(BaseModel):
    """Post-auth, post-RBAC artifact the router runs.

    No tenant fields leak into the router body. ``flow_id`` is the identifier the
    caller requested (an endpoint name or a UUID), kept so error bodies can echo
    it instead of the resolved internal id. ``graph`` is a host-defined execution
    artifact, NOT necessarily an ``lfx`` ``Graph``: bare serve stores a run-ready
    ``Graph`` (the default ``run_sync``/``stream_response`` consume it directly),
    while the langflow host stores a ``FlowRead`` and overrides those methods. The
    host owns any deepcopy/stamp semantics before handing it back.
    """

    model_config = {"arbitrary_types_allowed": True}

    flow_id: str  # the caller-requested identifier (endpoint name or UUID)
    graph: Any  # host-defined execution artifact (Graph for serve, FlowRead for langflow)
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

    async def run_sync(
        self,
        parsed: ParsedWorkflowRun,
        flow: ResolvedFlow,
        caller: Any,
        *,
        http_request: Request,
        background_tasks: BackgroundTasks,
    ) -> WorkflowExecutionResponse: ...

    def stream_response(
        self,
        parsed: ParsedWorkflowRun,
        flow: ResolvedFlow,
        caller: Any,
        *,
        stream_protocol: str,
        http_request: Request,
        background_tasks: BackgroundTasks,
    ) -> Response: ...

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

    def _run_user_id(self, caller: Any) -> str | None:  # noqa: ARG002
        """The verified caller identity to thread into a run, or ``None``.

        Default: the caller is opaque, so no per-user identity is threaded. A host
        whose ``resolve_caller`` returns a user id overrides this to surface it, so
        the lfx-default run/stream path pins it onto the graph.
        """
        return None

    async def run_sync(
        self,
        parsed: ParsedWorkflowRun,
        flow: ResolvedFlow,
        caller: Any,
        *,
        http_request: Request,  # noqa: ARG002
        background_tasks: BackgroundTasks,  # noqa: ARG002
    ) -> WorkflowExecutionResponse:
        """No-db default: run the resolved graph to completion via the lfx primitive."""
        from lfx.workflow.router import run_workflow_sync

        return await run_workflow_sync(flow.graph, parsed, flow.flow_id, user_id=self._run_user_id(caller))

    def stream_response(
        self,
        parsed: ParsedWorkflowRun,
        flow: ResolvedFlow,
        caller: Any,
        *,
        stream_protocol: str,
        http_request: Request,  # noqa: ARG002
        background_tasks: BackgroundTasks,  # noqa: ARG002
    ) -> Response:
        """No-db default: stream the resolved graph through the lfx SSE loop."""
        from uuid import uuid4

        from starlette.responses import StreamingResponse

        from lfx.workflow.adapters import StreamAdapterContext, get_stream_adapter
        from lfx.workflow.router import stream_workflow_frames

        thread_id = parsed.session_id or flow.session_id_default or flow.flow_id
        adapter = get_stream_adapter(
            stream_protocol,
            StreamAdapterContext(run_id=str(uuid4()), thread_id=thread_id),
        )
        return StreamingResponse(
            stream_workflow_frames(flow.graph, parsed, adapter, user_id=self._run_user_id(caller)),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

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
