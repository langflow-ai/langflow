from __future__ import annotations

import asyncio
from typing import Any

# Import the async simple_run_flow_task from the API endpoints
from langflow.api.v1.endpoints import simple_run_flow_task
from langflow.core.celery_app import celery_app


@celery_app.task(acks_late=True)
def simple_run_flow_task_celery(
    flow_data: dict,
    input_request: dict,
    *,
    stream: bool = False,
    api_key_user: Any = None,
    event_manager: Any = None,
) -> Any:
    """Celery task to execute the simple_run_flow_task from the API endpoints.

    Args:
        flow_data (dict): Data representing the flow to run.
        input_request (dict): Simplified API request data.
        stream (bool, optional): Whether the response should be streamed. Defaults to False.
        api_key_user (Any, optional): The API key user if available.
        event_manager (Any, optional): The event manager, if any.

    Returns:
        Any: The result of running the flow task.
    """
    run_response_object = asyncio.run(
        simple_run_flow_task(
            flow_data, input_request, stream=stream, api_key_user=api_key_user, event_manager=event_manager
        )
    )
    if run_response_object is not None:
        return run_response_object.model_dump()
    return None
