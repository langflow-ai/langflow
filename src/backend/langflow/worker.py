from langflow.core.celery_app import celery_app
from typing import Any, Dict, Optional
from typing import TYPE_CHECKING
from celery.exceptions import SoftTimeLimitExceeded

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
def process_graph_cached(
    data_graph: Dict[str, Any], inputs: Optional[dict] = None, clear_cache=False
):
    """
    Process graph by extracting input variables and replacing ZeroShotPrompt
    with PromptTemplate,then run the graph and return the result and thought.
    """
    from langflow.interface.run import build_sorted_vertices_with_caching
    from langflow.processing.process import get_result_and_thought
    from langchain.chains.base import Chain
    from langchain.vectorstores.base import VectorStore
    from langflow.utils.logger import logger

    # Load langchain object
    if clear_cache:
        build_sorted_vertices_with_caching.clear_cache()
        logger.debug("Cleared cache")
    langchain_object, artifacts = build_sorted_vertices_with_caching(data_graph)
    logger.debug("Loaded LangChain object")
    if inputs is None:
        inputs = {}

    # Add artifacts to inputs
    # artifacts can be documents loaded when building
    # the flow
    for (
        key,
        value,
    ) in artifacts.items():
        if key not in inputs or not inputs[key]:
            inputs[key] = value

    if langchain_object is None:
        # Raise user facing error
        raise ValueError(
            "There was an error loading the langchain_object. Please, check all the nodes and try again."
        )

    # Generate result and thought
    if isinstance(langchain_object, Chain):
        if inputs is None:
            raise ValueError("Inputs must be provided for a Chain")
        logger.debug("Generating result and thought")
        result = get_result_and_thought(langchain_object, inputs)
        logger.debug("Generated result and thought")
    elif isinstance(langchain_object, VectorStore):
        result = langchain_object.search(**inputs)
    else:
        raise ValueError(
            f"Unknown langchain_object type: {type(langchain_object).__name__}"
        )
    return result
