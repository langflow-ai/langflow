"""Durable background execution for bare ``lfx serve`` (LE-1695).

``DurableServeWorkflowHost`` upgrades the no-db serve host with
``supports_background = True``, backed by the single-node SQLite substrate
(``lfx.services.durable``): job rows, a per-job event log, and graph checkpoints
in one crash-safe file. A HITL pause suspends the job durably; resume restores
the graph from its checkpoint — in the same process or after a restart — injects
the human decision, and re-runs only what the approved branch needs.

Opt-in via ``LFX_SERVE_DURABLE_DB=<path>``: without it serve stays stateless and
``mode="background"`` keeps its 422. Multi-worker deployments share the DB file
(WAL + single-flight claims), but a stop only cancels a run executing in the
worker that received it; the durable STOP signal is still recorded.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from fastapi import HTTPException, Request, status

from lfx.cli.serve_workflow import ServeWorkflowHost
from lfx.graph.exceptions import GraphPausedException
from lfx.graph.graph.base import Graph
from lfx.log.logger import logger
from lfx.run._defaults import apply_run_defaults
from lfx.run.hitl import reroute_decision_on_timeout
from lfx.schema.schema import INPUT_FIELD_NAME
from lfx.schema.workflow import (
    ErrorDetail,
    JobStatus,
    WorkflowExecutionResponse,
    WorkflowJobResponse,
    WorkflowResumeRequest,
    WorkflowResumeResponse,
    WorkflowStopResponse,
)
from lfx.services.durable.models import JobStatus as DurableJobStatus
from lfx.services.durable.models import SignalType
from lfx.services.durable.sqlite_checkpoints import SqliteCheckpointStore
from lfx.services.durable.sqlite_store import SqliteDurableJobStore
from lfx.services.variable.request_scope import (
    activate_no_env_fallback,
    activate_request_variables,
    reset_no_env_fallback,
    reset_request_variables,
)
from lfx.workflow.converters import (
    _process_terminal_vertex,
    create_job_response,
    workflow_response_from_output_events,
)
from lfx.workflow.router import create_workflow_router

if TYPE_CHECKING:
    from pathlib import Path

    from fastapi import APIRouter

    from lfx.workflow.converters import ParsedWorkflowRun
    from lfx.workflow.host import ResolvedFlow

_NON_TERMINAL = {DurableJobStatus.QUEUED, DurableJobStatus.IN_PROGRESS, DurableJobStatus.SUSPENDED}


def _job_not_found(job_id: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"error": "Workflow job not found", "code": "JOB_NOT_FOUND", "job_id": job_id},
    )


def _not_resumable(job_id: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "error": "Job is not resumable",
            "code": "NOT_RESUMABLE",
            "message": "Job is not suspended, already resumed, or the request_id is stale.",
            "job_id": job_id,
        },
    )


class DurableServeWorkflowHost(ServeWorkflowHost):
    """Serve host with durable background runs on the SQLite substrate."""

    supports_background = True

    def __init__(self, registry, verify_api_key, *, db_path: Path) -> None:
        super().__init__(registry, verify_api_key)
        self.jobs = SqliteDurableJobStore(db_path)
        self.checkpoints = SqliteCheckpointStore(db_path)
        self._tasks: dict[str, asyncio.Task] = {}

    async def submit_background(
        self,
        parsed: ParsedWorkflowRun,
        flow: ResolvedFlow,
        caller: Any,
        *,
        stream_protocol: str,  # noqa: ARG002
    ) -> WorkflowJobResponse:
        job_id = str(uuid4())
        await self.jobs.create_job(job_id=job_id, flow_id=flow.flow_id, user_id=self._run_user_id(caller) or "")
        self._spawn(job_id, self._run_job(job_id, flow.graph, parsed, caller))
        return create_job_response(job_id, flow.flow_id)

    async def get_job_status(
        self,
        job_id: str,
        caller: Any,  # noqa: ARG002
        session: Any,  # noqa: ARG002
    ) -> WorkflowExecutionResponse | WorkflowJobResponse:
        job = await self.jobs.get_job(job_id)
        if job is None:
            raise _job_not_found(job_id)
        if job.status == DurableJobStatus.COMPLETED and job.result:
            return workflow_response_from_output_events(
                job.result.get("output_events", []), flow_id=job.flow_id, job_id=job_id
            )
        errors = [ErrorDetail(error=job.error.get("error", "unknown error"))] if job.error else []
        return WorkflowJobResponse(
            job_id=job_id,
            flow_id=job.flow_id,
            status=JobStatus(job.status.value),
            errors=errors,
        )

    async def stop_job(self, job_id: str, caller: Any) -> WorkflowStopResponse:  # noqa: ARG002
        job = await self.jobs.get_job(job_id)
        if job is None:
            raise _job_not_found(job_id)
        await self.jobs.write_signal(job_id, SignalType.STOP)
        task = self._tasks.get(job_id)
        if task is not None and not task.done():
            task.cancel()
        if job.status in _NON_TERMINAL:
            await self.jobs.update_status(job_id, DurableJobStatus.CANCELLED)
        return WorkflowStopResponse(job_id=job_id, message="Stop signal recorded; job cancelled.")

    async def pending_request(self, job_id: str) -> dict[str, Any]:
        job = await self.jobs.get_job(job_id)
        if job is None:
            raise _job_not_found(job_id)
        pending = (job.job_metadata or {}).get("pending")
        if job.status != DurableJobStatus.SUSPENDED or not pending:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "No pending human input", "code": "NO_PENDING_REQUEST", "job_id": job_id},
            )
        return pending

    async def resume_job(self, job_id: str, request: WorkflowResumeRequest) -> WorkflowResumeResponse:
        job = await self.jobs.get_job(job_id)
        if job is None:
            raise _job_not_found(job_id)
        pending = (job.job_metadata or {}).get("pending") or {}
        if pending.get("request_id") != request.request_id:
            raise _not_resumable(job_id)
        if not await self.jobs.claim_suspended_for_resume(job_id):
            raise _not_resumable(job_id)

        run_id = (job.job_metadata or {}).get("run_id")
        checkpoint = await self.checkpoints.load_by_run_id(run_id) if run_id else None
        if checkpoint is None:
            await self.jobs.set_error(job_id, {"error": "Paused run has no recoverable checkpoint."})
            raise _not_resumable(job_id)

        graph = Graph.resume_from_checkpoint(checkpoint, checkpoint_store=self.checkpoints)
        self._attach_stores(job_id, graph)
        decision = reroute_decision_on_timeout(pending, request.decision or {})
        graph.human_input_decisions = {
            **(getattr(graph, "human_input_decisions", {}) or {}),
            request.request_id: decision,
        }
        for vertex in graph.vertices:
            if f"{vertex.id}:{graph.run_id}" == request.request_id:
                vertex.built = False
        await self.jobs.update_metadata(job_id, {"pending": None})
        await self.jobs.append_event(job_id, "human_input_decision", {"request_id": request.request_id, **decision})
        self._spawn(job_id, self._drive(job_id, graph))
        return WorkflowResumeResponse(job_id=job_id, status="resuming", message="Resume accepted")

    def _spawn(self, job_id: str, coro) -> None:
        task = asyncio.create_task(coro)
        self._tasks[job_id] = task
        task.add_done_callback(lambda _t: self._tasks.pop(job_id, None))

    def _attach_stores(self, job_id: str, graph: Graph) -> None:
        graph.job_id = job_id
        graph.checkpointing_enabled = True
        graph.checkpoint_store = self.checkpoints

    async def _run_job(self, job_id: str, graph: Graph, parsed: ParsedWorkflowRun, caller: Any) -> None:
        await self.jobs.update_status(job_id, DurableJobStatus.IN_PROGRESS)
        from lfx.cli.runtime_variables import apply_global_vars_to_graph

        self._attach_stores(job_id, graph)
        user_id = self._run_user_id(caller)
        apply_run_defaults(graph, session_id=parsed.session_id, user_id=user_id, overwrite_user_id=user_id is not None)
        apply_global_vars_to_graph(graph, parsed.globals)
        if parsed.input_value:
            graph._set_inputs([], {INPUT_FIELD_NAME: parsed.input_value}, "chat")  # noqa: SLF001
        await self._drive(job_id, graph)

    async def _drive(self, job_id: str, graph: Graph) -> None:
        """Run the graph to its next terminal state and persist it on the job row."""
        from lfx.cli.runtime_variables import build_request_variables_from_global_vars

        scope_vars = build_request_variables_from_global_vars(graph.context.get("request_variables"))
        scope_token = activate_request_variables(scope_vars or None)
        no_env_token = activate_no_env_fallback(disabled=bool(graph.context.get("no_env_fallback")))
        try:
            await graph.process(fallback_to_env_vars=False)
        except GraphPausedException as pause:
            data = pause.data or {}
            await self.jobs.update_metadata(job_id, {"run_id": str(graph.run_id), "pending": data})
            await self.jobs.append_event(job_id, "human_input_request", data)
            await self.jobs.update_status(job_id, DurableJobStatus.SUSPENDED)
            return
        except asyncio.CancelledError:
            await self.jobs.update_status(job_id, DurableJobStatus.CANCELLED)
            raise
        except Exception as exc:  # noqa: BLE001
            logger.error(f"Durable background job {job_id} failed: {exc}")
            await self.jobs.set_error(job_id, {"error": str(exc), "type": type(exc).__name__})
            return
        finally:
            reset_no_env_fallback(no_env_token)
            reset_request_variables(scope_token)
        await self._complete(job_id, graph)

    async def _complete(self, job_id: str, graph: Graph) -> None:
        output_events: list[dict[str, Any]] = []
        for vertex in graph.vertices:
            is_terminal = not graph.successor_map.get(vertex.id, [])
            if not is_terminal or not vertex.built or vertex.result is None:
                continue
            component_id, component_output = _process_terminal_vertex(vertex, {vertex.id: vertex.result})
            output_events.append({"component_id": component_id, **component_output.model_dump()})
        await self.jobs.append_event(job_id, "end", {})
        await self.jobs.set_result(job_id, {"output_events": output_events})


def _register_resume_routes(router: APIRouter, host: DurableServeWorkflowHost) -> None:
    @router.post("/{job_id}/resume", summary="Resume Workflow (v2 human-in-the-loop)")
    async def resume_workflow(job_id: str, request: WorkflowResumeRequest, http_request: Request):
        await host.resolve_caller(http_request)
        return await host.resume_job(job_id, request)

    @router.get("/{job_id}/pending", summary="Pending human-input request (v2 background)")
    async def pending_request(job_id: str, http_request: Request):
        await host.resolve_caller(http_request)
        return await host.pending_request(job_id)


def create_durable_workflow_router(registry, verify_api_key, *, db_path: Path) -> APIRouter:
    """The v2 workflow router for serve with durable background + HITL resume routes."""
    host = DurableServeWorkflowHost(registry, verify_api_key, db_path=db_path)
    router = create_workflow_router(host, developer_api_guard=False)
    _register_resume_routes(router, host)
    return router
