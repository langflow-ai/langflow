from langflow.core.celery_app import celery_app
from typing import Any, Dict, Optional, Tuple
from typing import TYPE_CHECKING
from celery.exceptions import SoftTimeLimitExceeded
from langflow.processing.process import (
    clear_caches_if_needed,
    generate_result,
    process_inputs,
)
from langflow.services.manager import initialize_session_manager
from langflow.services.utils import get_session_manager

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
) -> Tuple[Any, str]:
    initialize_session_manager()
    clear_caches_if_needed(clear_cache)
    session_manager = get_session_manager()
    # Load the graph using SessionManager
    langchain_object, artifacts = session_manager.load_session(session_id, data_graph)
    processed_inputs = process_inputs(inputs, artifacts)
    result = generate_result(langchain_object, processed_inputs)
    # langchain_object is now updated with the new memory
    # we need to update the cache with the updated langchain_object
    session_manager.update_session(
        session_id, data_graph, (langchain_object, artifacts)
    )

    return result, session_id
