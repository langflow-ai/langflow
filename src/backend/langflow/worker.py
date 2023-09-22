from langflow.core.celery_app import celery_app
from typing import Any, Dict, Optional
from typing import TYPE_CHECKING

from celery.exceptions import SoftTimeLimitExceeded  # type: ignore
from langflow.processing.process import (
    Result,
    generate_result,
    process_inputs,
)
from langflow.services.manager import initialize_session_service
from langflow.services.getters import get_session_service

if TYPE_CHECKING:
    from langflow.graph.vertex.base import Vertex


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
        vertex.build()
        return vertex
    except SoftTimeLimitExceeded as e:
        raise self.retry(
            exc=SoftTimeLimitExceeded("Task took too long"), countdown=2
        ) from e


@celery_app.task(acks_late=True)
def process_graph_cached_task(
    data_graph: Dict[str, Any],
    inputs: Optional[dict] = None,
    clear_cache=False,
    session_id=None,
) -> Dict[str, Any]:
    initialize_session_service()
    session_service = get_session_service()
    if clear_cache:
        session_service.clear_session(session_id)
    if session_id is None:
        session_id = session_service.generate_key(
            session_id=session_id, data_graph=data_graph
        )
    # Load the graph using SessionService
    graph, artifacts = session_service.load_session(session_id, data_graph)
    built_object = graph.build()
    processed_inputs = process_inputs(inputs, artifacts)
    result = generate_result(built_object, processed_inputs)
    # langchain_object is now updated with the new memory
    # we need to update the cache with the updated langchain_object
    session_service.update_session(session_id, (graph, artifacts))

    return Result(result=result, session_id=session_id).dict()
