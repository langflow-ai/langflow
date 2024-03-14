from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

from asgiref.sync import async_to_sync
from celery.exceptions import SoftTimeLimitExceeded  # type: ignore

from langflow_base.core.celery_app import celery_app
from langflow_base.processing.process import Result, generate_result, process_inputs
from langflow_base.services.deps import get_session_service
from langflow_base.services.manager import initialize_session_service

if TYPE_CHECKING:
    from langflow_base.graph.vertex.base import Vertex


@celery_app.task(acks_late=True)
def test_celery(word: str) -> str:
    return f"test task return {word}"


@celery_app.task(bind=True, soft_time_limit=30, max_retries=3)
def build_vertex(self, vertex: "Vertex") -> "Vertex":
    """
    Build a vertex
    """
    try:
        vertex.task_id = self.request.id
        async_to_sync(vertex.build)()
        return vertex
    except SoftTimeLimitExceeded as e:
        raise self.retry(exc=SoftTimeLimitExceeded("Task took too long"), countdown=2) from e


@celery_app.task(acks_late=True)
def process_graph_cached_task(
    data_graph: Dict[str, Any],
    inputs: Optional[Union[dict, List[dict]]] = None,
    clear_cache=False,
    session_id=None,
) -> Dict[str, Any]:
    raise NotImplementedError("This task is not implemented yet")
