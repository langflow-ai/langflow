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
    """Build a vertex."""
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
