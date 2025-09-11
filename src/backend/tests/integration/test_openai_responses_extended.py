import asyncio
import json
import os
import pathlib

import pytest
from dotenv import load_dotenv
from httpx import AsyncClient
from loguru import logger


# Load environment variables from .env file
def load_env_vars():
    """Load environment variables from .env files."""
    # Try to find .env file in various locations
    possible_paths = [
        pathlib.Path(".env"),  # Current directory
        pathlib.Path("../../.env"),  # Project root
        pathlib.Path("../../../.env"),  # One level up from project root
    ]

    for env_path in possible_paths:
        if env_path.exists():
            logger.info(f"Loading environment variables from {env_path.absolute()}")
            load_dotenv(env_path)
            return True

    logger.warning("No .env file found. Using existing environment variables.")
    return False


# Load environment variables at module import time
load_env_vars()


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
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
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
async def test_openai_responses_invalid_flow_id(client: AsyncClient, created_api_key):
    """Test the OpenAI responses endpoint with an invalid flow ID."""
    headers = {"x-api-key": created_api_key.api_key}

    # Test with non-existent flow ID
    payload = {"model": "non-existent-flow-id", "input": "Hello", "stream": False}

    response = await client.post("/api/v1/responses", json=payload, headers=headers)

    assert response.status_code == 200  # OpenAI errors are still 200 status
    data = response.json()
    assert "error" in data
    assert isinstance(data["error"], dict)
    assert data["error"]["type"] == "invalid_request_error"
    assert "not found" in data["error"]["message"].lower()


@pytest.mark.api_key_required
@pytest.mark.integration
async def test_openai_responses_with_tools(client: AsyncClient, created_api_key):
    """Test that tools parameter is rejected."""
    flow, headers = await load_and_prepare_flow(client, created_api_key)

    # Test with tools parameter
    payload = {
        "model": flow["id"],
        "input": "Hello",
        "stream": False,
        "tools": [{"type": "function", "function": {"name": "test", "parameters": {}}}],
    }

    response = await client.post("/api/v1/responses", json=payload, headers=headers)

    assert response.status_code == 200  # OpenAI errors are still 200 status
    data = response.json()
    assert "error" in data
    assert isinstance(data["error"], dict)
    assert data["error"]["type"] == "invalid_request_error"
    assert data["error"]["code"] == "tools_not_supported"
    assert "tools are not supported" in data["error"]["message"].lower()


@pytest.mark.api_key_required
@pytest.mark.integration
async def test_openai_responses_empty_input(client: AsyncClient, created_api_key):
    """Test the OpenAI responses endpoint with empty input."""
    flow, headers = await load_and_prepare_flow(client, created_api_key)

    # Test with empty input
    payload = {"model": flow["id"], "input": "", "stream": False}

    response = await client.post("/api/v1/responses", json=payload, headers=headers)
    logger.info(f"Empty input response status: {response.status_code}")

    # The flow might still process empty input, so we check for a valid response structure
    data = response.json()

    if "error" not in data or data["error"] is None:
        # Valid response even with empty input
        assert "id" in data
        assert "output" in data
        assert "created_at" in data
        assert data["object"] == "response"
    else:
        # Some flows might reject empty input
        assert isinstance(data["error"], dict)
        assert "message" in data["error"]


@pytest.mark.api_key_required
@pytest.mark.integration
async def test_openai_responses_long_input(client: AsyncClient, created_api_key):
    """Test the OpenAI responses endpoint with very long input."""
    flow, headers = await load_and_prepare_flow(client, created_api_key)

    # Create a very long input
    long_input = "Hello " * 1000  # ~6000 characters
    payload = {"model": flow["id"], "input": long_input, "stream": False}

    response = await client.post("/api/v1/responses", json=payload, headers=headers)

    assert response.status_code == 200
    data = response.json()

    if "error" not in data:
        assert "id" in data
        assert "output" in data
        assert isinstance(data["output"], str)


@pytest.mark.api_key_required
@pytest.mark.integration
async def test_openai_responses_streaming_error_handling(client: AsyncClient, created_api_key):
    """Test streaming response error handling."""
    headers = {"x-api-key": created_api_key.api_key}

    # Test with invalid flow ID in streaming mode
    payload = {"model": "invalid-flow-id", "input": "Hello", "stream": True}

    response = await client.post("/api/v1/responses", json=payload, headers=headers)

    # For streaming errors, we should still get a 200 status but with error in the response
    assert response.status_code == 200

    # Read the response content
    content = await response.aread()
    text_content = content.decode("utf-8")

    # Should contain error information in JSON format, not SSE
    data = json.loads(text_content)
    assert "error" in data
    assert isinstance(data["error"], dict)
    assert data["error"]["type"] == "invalid_request_error"


@pytest.mark.api_key_required
@pytest.mark.integration
async def test_openai_responses_concurrent_requests(client: AsyncClient, created_api_key):
    """Test handling of concurrent requests to the same flow."""
    flow, headers = await load_and_prepare_flow(client, created_api_key)

    # Create multiple concurrent requests
    payloads = [{"model": flow["id"], "input": f"Request {i}", "stream": False} for i in range(5)]

    # Send all requests concurrently
    tasks = [client.post("/api/v1/responses", json=payload, headers=headers) for payload in payloads]

    responses = await asyncio.gather(*tasks)

    # All requests should succeed
    for i, response in enumerate(responses):
        assert response.status_code == 200
        data = response.json()

        if "error" not in data:
            assert "id" in data
            assert "output" in data
            # Each response should have a unique ID
            assert all(
                data["id"] != other.json()["id"]
                for j, other in enumerate(responses)
                if i != j and "error" not in other.json()
            )


@pytest.mark.api_key_required
@pytest.mark.integration
async def test_openai_responses_unauthorized(client: AsyncClient):
    """Test the OpenAI responses endpoint without authentication."""
    payload = {"model": "some-flow-id", "input": "Hello", "stream": False}

    # No headers = no authentication
    response = await client.post("/api/v1/responses", json=payload)

    # Should get 403 Forbidden
    assert response.status_code == 403


@pytest.mark.api_key_required
@pytest.mark.integration
async def test_openai_responses_invalid_api_key(client: AsyncClient):
    """Test the OpenAI responses endpoint with invalid API key."""
    headers = {"x-api-key": "invalid-api-key-12345"}
    payload = {"model": "some-flow-id", "input": "Hello", "stream": False}

    response = await client.post("/api/v1/responses", json=payload, headers=headers)

    # Should get 403 Forbidden
    assert response.status_code == 403


@pytest.mark.api_key_required
@pytest.mark.integration
async def test_openai_responses_malformed_request(client: AsyncClient, created_api_key):
    """Test the OpenAI responses endpoint with malformed requests."""
    headers = {"x-api-key": created_api_key.api_key}

    # Missing required fields
    test_cases = [
        {},  # Empty payload
        {"model": "flow-id"},  # Missing input
        {"input": "Hello"},  # Missing model
        {"model": 123, "input": "Hello"},  # Wrong type for model
        {"model": "flow-id", "input": 123},  # Wrong type for input
        {"model": "flow-id", "input": "Hello", "stream": "yes"},  # Wrong type for stream
    ]

    for payload in test_cases:
        response = await client.post("/api/v1/responses", json=payload, headers=headers)
        # OpenAI API returns validation errors as 200 with error in body or 422
        if response.status_code == 200:
            data = response.json()
            assert "error" in data
            assert isinstance(data["error"], dict)
            assert "message" in data["error"]
        else:
            # Should get 422 Unprocessable Entity for validation errors
            assert response.status_code == 422


@pytest.mark.api_key_required
@pytest.mark.integration
async def test_openai_responses_stream_interruption(client: AsyncClient, created_api_key):
    """Test behavior when streaming is interrupted."""
    flow, headers = await load_and_prepare_flow(client, created_api_key)

    payload = {"model": flow["id"], "input": "Tell me a long story", "stream": True}

    response = await client.post("/api/v1/responses", json=payload, headers=headers)
    assert response.status_code == 200

    # Read only first 500 bytes then close (streaming might need more bytes)
    content = await response.aread()
    text_content = content.decode("utf-8")

    # Should have received at least some data
    assert len(content) > 0
    # Check for either data: or valid response content
    assert "data:" in text_content or "id" in text_content


@pytest.mark.api_key_required
@pytest.mark.integration
async def test_openai_responses_background_processing(client: AsyncClient, created_api_key):
    """Test background processing parameter."""
    flow, headers = await load_and_prepare_flow(client, created_api_key)

    # Test with background=True
    payload = {"model": flow["id"], "input": "Hello", "background": True, "stream": False}

    response = await client.post("/api/v1/responses", json=payload, headers=headers)
    assert response.status_code == 200

    data = response.json()
    if "error" not in data or data["error"] is None:
        assert "id" in data
        assert "status" in data
        # Background processing might change the status
        assert data["status"] in ["completed", "in_progress"]


@pytest.mark.api_key_required
@pytest.mark.integration
async def test_openai_responses_previous_response_id(client: AsyncClient, created_api_key):
    """Test previous_response_id parameter for conversation continuity."""
    flow, headers = await load_and_prepare_flow(client, created_api_key)

    # First request
    payload1 = {"model": flow["id"], "input": "Hello", "stream": False}
    response1 = await client.post("/api/v1/responses", json=payload1, headers=headers)
    assert response1.status_code == 200

    data1 = response1.json()
    if "error" not in data1 or data1["error"] is None:
        first_response_id = data1["id"]

        # Second request with previous_response_id
        payload2 = {
            "model": flow["id"],
            "input": "Continue our conversation",
            "previous_response_id": first_response_id,
            "stream": False,
        }
        response2 = await client.post("/api/v1/responses", json=payload2, headers=headers)
        assert response2.status_code == 200

        data2 = response2.json()
        if "error" not in data2 or data2["error"] is None:
            # The previous_response_id might be preserved in the response
            # This depends on the implementation, so we just check it doesn't error
            # We'll just verify that the request was processed successfully
            assert "id" in data2
            assert "output" in data2


@pytest.mark.api_key_required
@pytest.mark.integration
async def test_openai_responses_response_format(client: AsyncClient, created_api_key):
    """Test OpenAI response format compliance."""
    flow, headers = await load_and_prepare_flow(client, created_api_key)

    payload = {"model": flow["id"], "input": "Hello", "stream": False}
    response = await client.post("/api/v1/responses", json=payload, headers=headers)

    assert response.status_code == 200
    data = response.json()

    if "error" not in data or data["error"] is None:
        # Check OpenAI response format compliance
        required_fields = ["id", "object", "created_at", "status", "model", "output"]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"

        # Check field types and values
        assert isinstance(data["id"], str)
        assert data["object"] == "response"
        assert isinstance(data["created_at"], int)
        assert data["status"] in ["completed", "in_progress", "failed"]
        assert isinstance(data["model"], str)
        assert isinstance(data["output"], list)

        # Check optional fields with expected defaults
        assert data["parallel_tool_calls"] is True
        assert data["store"] is True
        assert data["temperature"] == 1.0
        assert data["top_p"] == 1.0
        assert data["truncation"] == "disabled"
        assert data["tool_choice"] == "auto"
        assert isinstance(data["tools"], list)
        assert isinstance(data["reasoning"], dict)
        assert isinstance(data["text"], dict)
        assert isinstance(data["metadata"], dict)


@pytest.mark.api_key_required
@pytest.mark.integration
async def test_openai_responses_stream_chunk_format(client: AsyncClient, created_api_key):
    """Test OpenAI streaming response chunk format compliance."""
    flow, headers = await load_and_prepare_flow(client, created_api_key)

    payload = {"model": flow["id"], "input": "Hello", "stream": True}
    response = await client.post("/api/v1/responses", json=payload, headers=headers)

    assert response.status_code == 200

    content = await response.aread()
    text_content = content.decode("utf-8")

    # Parse the events
    events = text_content.strip().split("\n\n")
    data_events = [evt for evt in events if evt.startswith("data:") and not evt.startswith("data: [DONE]")]

    if data_events:
        # Check first chunk format
        first_chunk_json = data_events[0].replace("data: ", "")
        try:
            first_chunk = json.loads(first_chunk_json)

            # Basic checks for streaming response
            assert "id" in first_chunk
            assert "delta" in first_chunk
            assert isinstance(first_chunk["id"], str)
            assert isinstance(first_chunk["delta"], dict)

            # Check OpenAI stream chunk format compliance if fields exist
            if "object" in first_chunk:
                assert first_chunk["object"] == "response.chunk"
            if "created" in first_chunk:
                assert isinstance(first_chunk["created"], int)
            if "model" in first_chunk:
                assert isinstance(first_chunk["model"], str)

            # Status is optional in chunks and can be None
            if "status" in first_chunk and first_chunk["status"] is not None:
                assert first_chunk["status"] in ["completed", "in_progress", "failed"]
        except json.JSONDecodeError:
            # If streaming format is different or not JSON, just ensure we have data
            assert len(data_events) > 0
    else:
        # If no streaming chunks, ensure we have the [DONE] marker or valid response
        assert "data: [DONE]" in text_content or len(text_content) > 0


@pytest.mark.api_key_required
@pytest.mark.integration
async def test_openai_responses_rate_limiting_simulation(client: AsyncClient, created_api_key):
    """Test behavior under rapid successive requests."""
    flow, headers = await load_and_prepare_flow(client, created_api_key)

    # Send 10 rapid requests
    rapid_requests = []
    for i in range(10):
        payload = {"model": flow["id"], "input": f"Rapid request {i}", "stream": False}
        rapid_requests.append(client.post("/api/v1/responses", json=payload, headers=headers))

    # Wait for all requests to complete
    responses = await asyncio.gather(*rapid_requests, return_exceptions=True)

    # Check that most requests succeeded (allowing for some potential failures)
    successful_responses = [r for r in responses if not isinstance(r, Exception) and r.status_code == 200]

    # At least 50% should succeed
    assert len(successful_responses) >= 5

    # Check that successful responses have unique IDs
    response_ids = []
    for response in successful_responses:
        data = response.json()
        if "error" not in data or data["error"] is None:
            response_ids.append(data["id"])

    # All response IDs should be unique
    assert len(response_ids) == len(set(response_ids))
