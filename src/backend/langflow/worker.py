from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

from asgiref.sync import async_to_sync
from celery.exceptions import SoftTimeLimitExceeded  # type: ignore
from langflow.core.celery_app import celery_app
from langflow.processing.process import Result, generate_result, process_inputs
from langflow.services.deps import get_session_service
from langflow.services.manager import initialize_session_service
from loguru import logger
from rich import print

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
    try:
        initialize_session_service()
        session_service = get_session_service()

        if clear_cache:
            session_service.clear_session(session_id)

        if session_id is None:
            session_id = session_service.generate_key(session_id=session_id, data_graph=data_graph)

        # Use async_to_sync to handle the asynchronous part of the session service
        session_data = async_to_sync(session_service.load_session, force_new_loop=True)(session_id, data_graph)
        logger.warning(f"session_data: {session_data}")
        graph, artifacts = session_data if session_data else (None, None)

        if not graph:
            raise ValueError("Graph not found in the session")

        # Use async_to_sync for the asynchronous build method
        built_object = async_to_sync(graph.build, force_new_loop=True)()

        logger.debug(f"Built object: {built_object}")

        processed_inputs = process_inputs(inputs, artifacts or {})
        result = async_to_sync(generate_result, force_new_loop=True)(built_object, processed_inputs)

        # Update the session with the new data
        session_service.update_session(session_id, (graph, artifacts))
        result_object = Result(result=result, session_id=session_id).model_dump()
        print(f"Result object: {result_object}")
        return result_object
    except Exception as e:
        logger.error(f"Error in process_graph_cached_task: {e}")
        # Handle the exception as needed, maybe re-raise or return an error message
        raise
