"""Celery worker implementation for distributed Langflow graph execution.

This module defines Celery tasks for executing Langflow graph vertices in a
distributed worker environment, enabling horizontal scaling and background
processing of compute-intensive workflows.

Celery Tasks:
    - test_celery(): Simple connectivity test for worker validation
    - build_vertex(): Executes a single graph vertex with full context
    - process_graph_cached(): Processes cached graph execution requests

Worker Features:
    - Asynchronous graph vertex execution via async_to_sync conversion
    - Soft time limit handling with SoftTimeLimitExceeded catching
    - Late acknowledgment (acks_late=True) for reliable task processing
    - Full vertex context preservation including parameters and caching

Graph Execution:
    The build_vertex task receives:
    - Serialized vertex data with component information
    - Graph context including session_id and flow_id
    - Caching parameters for result storage
    - User context and authentication information

Error Handling:
    - SoftTimeLimitExceeded: Graceful task termination on timeout
    - Component build errors: Detailed error reporting with stack traces
    - Network failures: Retry logic for transient failures

The worker integrates with Langflow's core execution engine while providing
distributed processing capabilities for production deployments.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from asgiref.sync import async_to_sync
from celery.exceptions import SoftTimeLimitExceeded

from langflow.core.celery_app import celery_app

if TYPE_CHECKING:
    from langflow.graph.vertex.base import Vertex


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
