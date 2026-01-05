import asyncio
import json
import pathlib

import pytest
from dotenv import find_dotenv, load_dotenv
from httpx import AsyncClient
from lfx.log.logger import logger

load_dotenv(find_dotenv())


async def create_global_variable(client: AsyncClient, headers, name, value, variable_type="credential"):
    """Create a global variable in Langflow."""
    payload = {"name": name, "value": value, "type": variable_type, "default_fields": []}

    response = await client.post("/api/v1/variables/", json=payload, headers=headers)
    if response.status_code != 201:
        logger.error(f"Failed to create global variable: {response.content}")
        return False

    logger.info(f"Successfully created global variable: {name}")
    return True


async def load_and_prepare_flow(client: AsyncClient, created_api_key):
    """Load a flow template, create it, and wait for it to be ready."""
    # Set up headers
    headers = {"x-api-key": created_api_key.api_key}

    # Create OPENAI_API_KEY global variable
    from tests.api_keys import get_openai_api_key

    try:
        openai_api_key = get_openai_api_key()
    except ValueError:
        pytest.skip("OPENAI_API_KEY environment variable not set")

    await create_global_variable(client, headers, "OPENAI_API_KEY", openai_api_key)

    # Load the Basic Prompting template
    template_path = (
        pathlib.Path(__file__).resolve().parent.parent.parent
        / "base"
        / "langflow"
        / "initial_setup"
        / "starter_projects"
        / "Basic Prompting.json"
    )

    flow_data = await asyncio.to_thread(lambda: json.loads(pathlib.Path(template_path).read_text()))

    # Add the flow
    response = await client.post("/api/v1/flows/", json=flow_data, headers=headers)
    logger.info(f"Flow creation response: {response.status_code}")

    assert response.status_code == 201
    flow = response.json()

    # Poll for flow builds to complete
    max_attempts = 10
    for attempt in range(max_attempts):
        # Get the flow builds
        builds_response = await client.get(f"/api/v1/monitor/builds?flow_id={flow['id']}", headers=headers)

        if builds_response.status_code == 200:
            builds = builds_response.json().get("vertex_builds", {})
            # Check if builds are complete
            all_valid = True
            for build_list in builds.values():
                if not build_list or build_list[0].get("valid") is not True:
                    all_valid = False
                    break

            if all_valid and builds:
                logger.info(f"Flow builds completed successfully after {attempt + 1} attempts")
                break

        # Wait before polling again
        if attempt < max_attempts - 1:
            logger.info(f"Waiting for flow builds to complete (attempt {attempt + 1}/{max_attempts})...")
            await asyncio.sleep(1)
    else:
        logger.warning("Flow builds polling timed out, proceeding anyway")

    return flow, headers


@pytest.mark.api_key_required
@pytest.mark.integration
async def test_openai_responses_non_streaming(client: AsyncClient, created_api_key):
    """Test the OpenAI-compatible non-streaming responses endpoint directly."""
    flow, headers = await load_and_prepare_flow(client, created_api_key)

    # Now test the OpenAI-compatible endpoint
    payload = {"model": flow["id"], "input": "Hello, Langflow!", "stream": False}

    # Make the request
    response = await client.post("/api/v1/responses", json=payload, headers=headers)
    logger.info(f"Response status: {response.status_code}")
    logger.debug(f"Response content: {response.content}")

    # Handle potential errors
    if response.status_code != 200:
        logger.error(f"Error response: {response.content}")
        pytest.fail(f"Request failed with status {response.status_code}")

    try:
        data = response.json()
        if "error" in data and data["error"] is not None:
            logger.error(f"Error in response: {data['error']}")
            # Don't fail immediately, log more details for debugging
            logger.error(f"Full error details: {data}")
            error_msg = "Unknown error"
            if isinstance(data.get("error"), dict):
                error_msg = data["error"].get("message", "Unknown error")
            elif data.get("error"):
                error_msg = str(data["error"])
            pytest.fail(f"Error in response: {error_msg}")

        # Validate the response
        assert "id" in data
        assert "output" in data
    except Exception as exc:
        logger.exception("Exception parsing response")
        pytest.fail(f"Failed to parse response: {exc}")


@pytest.mark.api_key_required
@pytest.mark.integration
async def test_openai_responses_streaming(client: AsyncClient, created_api_key):
    """Test the OpenAI-compatible streaming responses endpoint directly."""
    flow, headers = await load_and_prepare_flow(client, created_api_key)

    # Now test the OpenAI-compatible streaming endpoint
    payload = {"model": flow["id"], "input": "Hello, stream!", "stream": True}

    # Make the request
    response = await client.post("/api/v1/responses", json=payload, headers=headers)
    logger.info(f"Response status: {response.status_code}")

    # Handle potential errors
    if response.status_code != 200:
        logger.error(f"Error response: {response.content}")
        pytest.fail(f"Request failed with status {response.status_code}")

    # For streaming, we should get a stream of server-sent events
    content = await response.aread()
    text_content = content.decode("utf-8")
    logger.debug(f"Response content (first 200 chars): {text_content[:200]}")

    # Check that we got some SSE data events
    assert "data:" in text_content

    # Parse the events to validate structure and final [DONE] marker
    events = text_content.strip().split("\n\n")
    # The stream must end with the OpenAI '[DONE]' sentinel
    assert events, "No events in stream"
    assert events[-1].strip() == "data: [DONE]", "Stream did not end with [DONE] marker"

    # Filter out the [DONE] marker to inspect JSON data events
    data_events = [evt for evt in events if evt.startswith("data:") and not evt.startswith("data: [DONE]")]
    assert data_events, "No streaming events were received"

    # Parse the first and last JSON events to check their structure
    first_event = json.loads(data_events[0].replace("data: ", ""))
    last_event = json.loads(data_events[-1].replace("data: ", ""))
    assert "delta" in first_event
    assert "delta" in last_event
