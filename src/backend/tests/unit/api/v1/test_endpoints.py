import asyncio
import inspect
import time
from typing import Any
from unittest.mock import AsyncMock

import pytest
from anyio import Path
from fastapi import status
from httpx import AsyncClient
from langflow.api.v1.endpoints import consume_and_yield
from langflow.api.v1.schemas import UpdateCustomComponentRequest
from langflow.components.agents.agent import AgentComponent
from langflow.custom.utils import build_custom_component_template


async def test_get_version(client: AsyncClient):
    response = await client.get("api/v1/version")
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert isinstance(result, dict), "The result must be a dictionary"
    assert "version" in result, "The dictionary must contain a key called 'version'"
    assert "main_version" in result, "The dictionary must contain a key called 'main_version'"
    assert "package" in result, "The dictionary must contain a key called 'package'"


async def test_get_config(client: AsyncClient):
    response = await client.get("api/v1/config")
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert isinstance(result, dict), "The result must be a dictionary"
    assert "frontend_timeout" in result, "The dictionary must contain a key called 'frontend_timeout'"
    assert "auto_saving" in result, "The dictionary must contain a key called 'auto_saving'"
    assert "health_check_max_retries" in result, "The dictionary must contain a 'health_check_max_retries' key"
    assert "max_file_size_upload" in result, "The dictionary must contain a key called 'max_file_size_upload'"


async def test_update_component_outputs(client: AsyncClient, logged_in_headers: dict):
    path = Path(__file__).parent.parent.parent.parent / "data" / "dynamic_output_component.py"

    code = await path.read_text(encoding="utf-8")
    frontend_node: dict[str, Any] = {"outputs": []}
    request = UpdateCustomComponentRequest(
        code=code,
        frontend_node=frontend_node,
        field="show_output",
        field_value=True,
        template={},
    )
    response = await client.post("api/v1/custom_component/update", json=request.model_dump(), headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    output_names = [output["name"] for output in result["outputs"]]
    assert "tool_output" in output_names


async def test_update_component_model_name_options(client: AsyncClient, logged_in_headers: dict):
    """Test that model_name options are updated when selecting a provider."""
    component = AgentComponent()
    component_node, _ = build_custom_component_template(
        component,
    )

    # Initial template with OpenAI as the provider
    template = component_node["template"]
    current_model_names = template["model_name"]["options"]

    # load the code from the file at langflow.components.agents.agent.py asynchronously
    # we are at str/backend/tests/unit/api/v1/test_endpoints.py
    # find the file by using the class AgentComponent
    agent_component_file = await asyncio.to_thread(inspect.getsourcefile, AgentComponent)
    code = await Path(agent_component_file).read_text(encoding="utf-8")

    # Create the request to update the component
    request = UpdateCustomComponentRequest(
        code=code,
        frontend_node=component_node,
        field="agent_llm",
        field_value="Anthropic",
        template=template,
    )

    # Make the request to update the component
    response = await client.post("api/v1/custom_component/update", json=request.model_dump(), headers=logged_in_headers)
    result = response.json()

    # Verify the response
    assert response.status_code == status.HTTP_200_OK, f"Response: {response.json()}"
    assert "template" in result
    assert "model_name" in result["template"]
    assert isinstance(result["template"]["model_name"]["options"], list)
    assert len(result["template"]["model_name"]["options"]) > 0, (
        f"Model names: {result['template']['model_name']['options']}"
    )
    assert current_model_names != result["template"]["model_name"]["options"], (
        f"Current model names: {current_model_names}, New model names: {result['template']['model_name']['options']}"
    )
    # Now test with Custom provider
    template["agent_llm"]["value"] = "Custom"
    request.field_value = "Custom"
    request.template = template

    response = await client.post("api/v1/custom_component/update", json=request.model_dump(), headers=logged_in_headers)
    result = response.json()

    # Verify that model_name is not present for Custom provider
    assert response.status_code == status.HTTP_200_OK
    assert "template" in result
    assert "model_name" not in result["template"]


async def test_consume_and_yield_with_events():
    """Test consume_and_yield function handles events correctly."""
    # Create asyncio queues
    queue = asyncio.Queue()
    client_consumed_queue = asyncio.Queue()

    # Add test events to the queue
    test_events = [
        (1, b'{"event": "test1", "data": "value1"}', time.time()),
        (2, b'{"event": "test2", "data": "value2"}', time.time()),
        (None, None, time.time()),  # End of stream
    ]

    for event in test_events:
        await queue.put(event)

    # Collect yielded values
    yielded_values = [value async for value in consume_and_yield(queue, client_consumed_queue)]

    # Verify the correct values were yielded
    assert len(yielded_values) == 2
    assert yielded_values[0] == b'{"event": "test1", "data": "value1"}'
    assert yielded_values[1] == b'{"event": "test2", "data": "value2"}'

    # Verify client consumption tracking
    consumed_events = []
    while not client_consumed_queue.empty():
        consumed_events.append(client_consumed_queue.get_nowait())

    assert len(consumed_events) == 2
    assert consumed_events == [1, 2]


async def test_consume_and_yield_keepalive_timeout():
    """Test consume_and_yield sends Keep-Alive events on timeout."""
    import os

    # Set a short timeout for testing
    original_timeout = os.getenv("LANGFLOW_KEEP_ALIVE_TIMEOUT")
    os.environ["LANGFLOW_KEEP_ALIVE_TIMEOUT"] = "0.1"

    # Reload the module to pick up the new timeout value
    import importlib

    from langflow.api.v1 import endpoints

    importlib.reload(endpoints)

    try:
        # Create empty queues (no events will be available)
        queue = asyncio.Queue()
        client_consumed_queue = asyncio.Queue()

        # Start the generator
        generator = endpoints.consume_and_yield(queue, client_consumed_queue)

        # Wait for the first keepalive (should happen after 0.1 seconds)
        start_time = time.time()
        value = await generator.__anext__()
        elapsed = time.time() - start_time

        # Verify we got a keepalive event after the timeout
        assert elapsed >= 0.1
        assert value == b'{"event": "keepalive", "data": {}}\n\n'

        # Cancel the generator by adding None to queue
        await queue.put((None, None, time.time()))

        # The generator should break on the next iteration
        import contextlib

        with contextlib.suppress(StopAsyncIteration):
            await generator.__anext__()

    finally:
        # Restore original timeout
        if original_timeout is not None:
            os.environ["LANGFLOW_KEEP_ALIVE_TIMEOUT"] = original_timeout
        else:
            os.environ.pop("LANGFLOW_KEEP_ALIVE_TIMEOUT", None)

        # Reload to restore original state
        importlib.reload(endpoints)


async def test_consume_and_yield_exception_handling():
    """Test consume_and_yield propagates exceptions correctly."""
    queue = asyncio.Queue()
    client_consumed_queue = asyncio.Queue()

    # Create a mock queue that raises an exception
    queue.get = AsyncMock(side_effect=Exception("Test exception"))

    # The generator should propagate the exception to the caller
    with pytest.raises(Exception, match="Test exception"):
        [value async for value in consume_and_yield(queue, client_consumed_queue)]
