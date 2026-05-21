from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from asgiref.sync import async_to_sync
from celery.exceptions import SoftTimeLimitExceeded

from langflow.core.celery_app import celery_app

if TYPE_CHECKING:
    from lfx.graph.vertex.base import Vertex


@celery_app.task(acks_late=True)
def test_celery(word: str) -> str:
    return f"test task return {word}"


@celery_app.task(bind=True, soft_time_limit=30, max_retries=3)
def build_vertex(self, vertex: Vertex) -> Vertex:
    """Build a vertex.

    Returns:
        The built vertex.
    """
    try:
        vertex.task_id = self.request.id
        async_to_sync(vertex.build)()
    except SoftTimeLimitExceeded as e:
        raise self.retry(exc=SoftTimeLimitExceeded("Task took too long"), countdown=2) from e
    return vertex


@celery_app.task(acks_late=True)
def process_graph_cached_task() -> dict[str, Any]:
    msg = "This task is not implemented yet"
    raise NotImplementedError(msg)


@celery_app.task(name="langflow.worker.run_workflow_job", acks_late=True)
def run_workflow_job(
    *,
    job_id: str,
    flow_id: str,
    user_id: str,
    flow_name: str | None,
    graph_data: dict[str, Any],
    tweaks: dict[str, dict[str, Any]],
    session_id: str | None,
    request_variables: dict[str, str] | None = None,
) -> None:
    """Run a background workflow from serializable inputs in a Celery worker."""
    async_to_sync(_run_workflow_job)(
        job_id=job_id,
        flow_id=flow_id,
        user_id=user_id,
        flow_name=flow_name,
        graph_data=graph_data,
        tweaks=tweaks,
        session_id=session_id,
        request_variables=request_variables,
    )


async def _run_workflow_job(
    *,
    job_id: str,
    flow_id: str,
    user_id: str,
    flow_name: str | None,
    graph_data: dict[str, Any],
    tweaks: dict[str, dict[str, Any]],
    session_id: str | None,
    request_variables: dict[str, str] | None = None,
) -> None:
    """Reconstruct and execute a workflow graph inside the Celery worker process."""
    from copy import deepcopy

    from lfx.graph.graph.base import Graph

    from langflow.processing.process import process_tweaks, run_graph_internal
    from langflow.services.deps import get_job_service

    context = {"request_variables": request_variables} if request_variables else None
    processed_graph_data = process_tweaks(deepcopy(graph_data), tweaks, stream=False)
    graph = Graph.from_payload(
        processed_graph_data,
        flow_id=flow_id,
        user_id=user_id,
        flow_name=flow_name,
        context=context,
    )
    graph.set_run_id(UUID(job_id))
    outputs = graph.get_terminal_nodes()

    job_service = get_job_service()
    await job_service.execute_with_status(
        UUID(job_id),
        run_graph_internal,
        graph=graph,
        flow_id=flow_id,
        session_id=session_id,
        inputs=None,
        outputs=outputs,
        stream=False,
    )
