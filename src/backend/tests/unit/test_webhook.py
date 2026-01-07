import asyncio
from unittest.mock import patch

import aiofiles
import anyio
import pytest


@pytest.fixture(autouse=True)
def _check_openai_api_key_in_environment_variables():
    pass


# =============================================================================
# SUCCESS TESTS
# =============================================================================


async def test_webhook_endpoint_returns_202_accepted(client, added_webhook_test, created_api_key):
    """Test that webhook endpoint returns 202 Accepted on valid request."""
    endpoint_name = added_webhook_test["endpoint_name"]
    endpoint = f"api/v1/webhook/{endpoint_name}"

    payload = {"test_key": "test_value"}
    response = await client.post(endpoint, headers={"x-api-key": created_api_key.api_key}, json=payload)

    assert response.status_code == 202
    assert response.json()["message"] == "Task started in the background"
    assert response.json()["status"] == "in progress"


async def test_webhook_endpoint_by_flow_id(client, added_webhook_test, created_api_key):
    """Test that webhook can be accessed by flow ID."""
    flow_id = added_webhook_test["id"]
    endpoint = f"api/v1/webhook/{flow_id}"

    payload = {"data": "test"}
    response = await client.post(endpoint, headers={"x-api-key": created_api_key.api_key}, json=payload)

    assert response.status_code == 202


async def test_webhook_with_json_payload(client, added_webhook_test, created_api_key):
    """Test webhook with various JSON payload types."""
    endpoint_name = added_webhook_test["endpoint_name"]
    endpoint = f"api/v1/webhook/{endpoint_name}"

    # Test with nested JSON
    payload = {"nested": {"key": "value", "array": [1, 2, 3]}}
    response = await client.post(endpoint, headers={"x-api-key": created_api_key.api_key}, json=payload)
    assert response.status_code == 202

    # Test with array payload
    payload = [{"item": 1}, {"item": 2}]
    response = await client.post(endpoint, headers={"x-api-key": created_api_key.api_key}, json=payload)
    assert response.status_code == 202


async def test_webhook_endpoint_requires_api_key_when_auto_login_false(client, added_webhook_test):
    """Test that webhook endpoint requires API key when WEBHOOK_AUTH_ENABLE=true."""
    # Mock the settings service to enable webhook authentication
    from unittest.mock import patch

    with patch("langflow.services.auth.utils.get_settings_service") as mock_settings:
        mock_auth_settings = type("AuthSettings", (), {"WEBHOOK_AUTH_ENABLE": True})()
        mock_settings_service = type("SettingsService", (), {"auth_settings": mock_auth_settings})()
        mock_settings.return_value = mock_settings_service

        endpoint_name = added_webhook_test["endpoint_name"]
        endpoint = f"api/v1/webhook/{endpoint_name}"

        payload = {"path": "/tmp/test_file.txt"}  # noqa: S108

        # Should fail without API key when webhook auth is enabled
        response = await client.post(endpoint, json=payload)
        assert response.status_code == 403
        assert "API key required when webhook authentication is enabled" in response.json()["detail"]


async def test_webhook_endpoint_with_valid_api_key(client, added_webhook_test, created_api_key):
    """Test that webhook works when valid API key is provided."""
    endpoint_name = added_webhook_test["endpoint_name"]
    endpoint = f"api/v1/webhook/{endpoint_name}"

    # Create a temporary file
    async with aiofiles.tempfile.TemporaryDirectory() as tmp:
        file_path = anyio.Path(tmp) / "test_file.txt"
        payload = {"path": str(file_path)}

        # Should work with valid API key
        response = await client.post(endpoint, headers={"x-api-key": created_api_key.api_key}, json=payload)
        assert response.status_code == 202
        assert await file_path.exists(), f"File {file_path} does not exist"

    file_does_not_exist = not await file_path.exists()
    assert file_does_not_exist, f"File {file_path} still exists"


async def test_webhook_endpoint_unauthorized_user_flow(client, added_webhook_test):
    """Test that webhook fails when user doesn't own the flow."""
    # Mock the settings service to enable webhook authentication
    from unittest.mock import patch

    with patch("langflow.services.auth.utils.get_settings_service") as mock_settings:
        mock_auth_settings = type("AuthSettings", (), {"WEBHOOK_AUTH_ENABLE": True})()
        mock_settings_service = type("SettingsService", (), {"auth_settings": mock_auth_settings})()
        mock_settings.return_value = mock_settings_service

        # This test would need a different user's API key to test authorization
        # For now, we'll use an invalid API key to simulate this
        endpoint_name = added_webhook_test["endpoint_name"]
        endpoint = f"api/v1/webhook/{endpoint_name}"

        payload = {"path": "/tmp/test_file.txt"}  # noqa: S108

        # Should fail with invalid API key
        response = await client.post(endpoint, headers={"x-api-key": "invalid_key"}, json=payload)
        assert response.status_code == 403
        assert "Invalid API key" in response.json()["detail"]


async def test_webhook_flow_on_run_endpoint(client, added_webhook_test, created_api_key):
    endpoint_name = added_webhook_test["endpoint_name"]
    endpoint = f"api/v1/run/{endpoint_name}?stream=false"
    # Just test that "Random Payload" returns 202
    # returns 202
    payload = {
        "output_type": "any",
    }
    response = await client.post(endpoint, headers={"x-api-key": created_api_key.api_key}, json=payload)
    assert response.status_code == 200, response.json()


async def test_webhook_with_auto_login_enabled(client, added_webhook_test):
    """Test webhook behavior when WEBHOOK_AUTH_ENABLE=false - should work without API key."""
    # Mock the settings service to disable webhook authentication (default behavior)
    from unittest.mock import patch

    with patch("langflow.services.auth.utils.get_settings_service") as mock_settings:
        mock_auth_settings = type("AuthSettings", (), {"WEBHOOK_AUTH_ENABLE": False})()
        mock_settings_service = type("SettingsService", (), {"auth_settings": mock_auth_settings})()
        mock_settings.return_value = mock_settings_service

        endpoint_name = added_webhook_test["endpoint_name"]
        endpoint = f"api/v1/webhook/{endpoint_name}"

        payload = {"path": "/tmp/test_auto_login.txt"}  # noqa: S108

        # Should work without API key when webhook auth is disabled
        response = await client.post(endpoint, json=payload)
        assert response.status_code == 202


async def test_webhook_with_random_payload_requires_auth(client, added_webhook_test, created_api_key):
    """Test that webhook with random payload still requires authentication."""
    # Mock the settings service to enable webhook authentication
    from unittest.mock import patch

    with patch("langflow.services.auth.utils.get_settings_service") as mock_settings:
        mock_auth_settings = type("AuthSettings", (), {"WEBHOOK_AUTH_ENABLE": True})()
        mock_settings_service = type("SettingsService", (), {"auth_settings": mock_auth_settings})()
        mock_settings.return_value = mock_settings_service

        endpoint_name = added_webhook_test["endpoint_name"]
        endpoint = f"api/v1/webhook/{endpoint_name}"

        # Should fail without API key
        response = await client.post(endpoint, json="Random Payload")
        assert response.status_code == 403

        # Should work with API key (even with random payload)
        response = await client.post(
            endpoint,
            headers={"x-api-key": created_api_key.api_key},
            json="Random Payload",
        )
        assert response.status_code == 202


# =============================================================================
# ERROR TESTS
# =============================================================================


async def test_webhook_not_found_invalid_endpoint(client, created_api_key):
    """Test that webhook returns 404 for non-existent endpoint."""
    endpoint = "api/v1/webhook/non-existent-endpoint-12345"
    payload = {"test": "data"}

    response = await client.post(endpoint, headers={"x-api-key": created_api_key.api_key}, json=payload)
    assert response.status_code == 404


async def test_webhook_not_found_invalid_flow_id(client, created_api_key):
    """Test that webhook returns 404 for invalid flow ID."""
    endpoint = "api/v1/webhook/00000000-0000-0000-0000-000000000000"
    payload = {"test": "data"}

    response = await client.post(endpoint, headers={"x-api-key": created_api_key.api_key}, json=payload)
    assert response.status_code == 404


async def test_webhook_invalid_api_key(client, added_webhook_test):
    """Test that webhook returns 403 for invalid API key when auth is enabled."""
    with patch("langflow.services.auth.utils.get_settings_service") as mock_settings:
        mock_auth_settings = type("AuthSettings", (), {"WEBHOOK_AUTH_ENABLE": True})()
        mock_settings_service = type("SettingsService", (), {"auth_settings": mock_auth_settings})()
        mock_settings.return_value = mock_settings_service

        endpoint_name = added_webhook_test["endpoint_name"]
        endpoint = f"api/v1/webhook/{endpoint_name}"
        payload = {"test": "data"}

        response = await client.post(endpoint, headers={"x-api-key": "invalid-api-key"}, json=payload)
        assert response.status_code == 403
        assert "Invalid API key" in response.json()["detail"]


async def test_webhook_missing_api_key_when_required(client, added_webhook_test):
    """Test that webhook returns 403 when API key is missing and auth is enabled."""
    with patch("langflow.services.auth.utils.get_settings_service") as mock_settings:
        mock_auth_settings = type("AuthSettings", (), {"WEBHOOK_AUTH_ENABLE": True})()
        mock_settings_service = type("SettingsService", (), {"auth_settings": mock_auth_settings})()
        mock_settings.return_value = mock_settings_service

        endpoint_name = added_webhook_test["endpoint_name"]
        endpoint = f"api/v1/webhook/{endpoint_name}"
        payload = {"test": "data"}

        response = await client.post(endpoint, json=payload)
        assert response.status_code == 403
        assert "API key required" in response.json()["detail"]


# =============================================================================
# EDGE CASE TESTS
# =============================================================================


async def test_webhook_with_empty_payload(client, added_webhook_test, created_api_key):
    """Test webhook with empty JSON payload."""
    endpoint_name = added_webhook_test["endpoint_name"]
    endpoint = f"api/v1/webhook/{endpoint_name}"

    response = await client.post(endpoint, headers={"x-api-key": created_api_key.api_key}, json={})
    assert response.status_code == 202


async def test_webhook_with_string_payload(client, added_webhook_test, created_api_key):
    """Test webhook with string payload instead of JSON object."""
    endpoint_name = added_webhook_test["endpoint_name"]
    endpoint = f"api/v1/webhook/{endpoint_name}"

    response = await client.post(endpoint, headers={"x-api-key": created_api_key.api_key}, json="plain string")
    assert response.status_code == 202


async def test_webhook_with_null_payload_returns_bad_request(client, added_webhook_test, created_api_key):
    """Test webhook with null payload returns 400 Bad Request."""
    endpoint_name = added_webhook_test["endpoint_name"]
    endpoint = f"api/v1/webhook/{endpoint_name}"

    response = await client.post(endpoint, headers={"x-api-key": created_api_key.api_key}, json=None)
    # Null payload is not valid JSON body, returns 400
    assert response.status_code == 400


async def test_webhook_with_large_payload(client, added_webhook_test, created_api_key):
    """Test webhook with large payload."""
    endpoint_name = added_webhook_test["endpoint_name"]
    endpoint = f"api/v1/webhook/{endpoint_name}"

    # Create a large payload
    large_payload = {"data": "x" * 10000, "items": list(range(1000))}
    response = await client.post(endpoint, headers={"x-api-key": created_api_key.api_key}, json=large_payload)
    assert response.status_code == 202


async def test_webhook_with_special_characters_in_payload(client, added_webhook_test, created_api_key):
    """Test webhook with special characters in payload."""
    endpoint_name = added_webhook_test["endpoint_name"]
    endpoint = f"api/v1/webhook/{endpoint_name}"

    payload = {
        "unicode": "こんにちは世界 🌍",
        "special": "<script>alert('xss')</script>",
        "quotes": 'He said "hello"',
        "newlines": "line1\nline2\rline3",
    }
    response = await client.post(endpoint, headers={"x-api-key": created_api_key.api_key}, json=payload)
    assert response.status_code == 202


# =============================================================================
# VERTEX BUILD TESTS
# =============================================================================


async def test_webhook_creates_vertex_builds(client, added_webhook_test, created_api_key):
    """Test that webhook execution creates vertex builds in the database."""
    flow_id = added_webhook_test["id"]
    endpoint_name = added_webhook_test["endpoint_name"]
    endpoint = f"api/v1/webhook/{endpoint_name}"

    # Execute the webhook
    payload = {"test": "vertex_build_test"}
    response = await client.post(endpoint, headers={"x-api-key": created_api_key.api_key}, json=payload)
    assert response.status_code == 202

    # Wait for background task to complete
    await asyncio.sleep(2)

    # Check vertex builds were created
    builds_endpoint = f"api/v1/monitor/builds?flow_id={flow_id}"
    builds_response = await client.get(builds_endpoint, headers={"x-api-key": created_api_key.api_key})

    assert builds_response.status_code == 200
    builds_data = builds_response.json()
    assert "vertex_builds" in builds_data
    # Should have at least one vertex build (Webhook component)
    assert len(builds_data["vertex_builds"]) > 0


async def test_webhook_vertex_builds_contain_expected_data(client, added_webhook_test, created_api_key):
    """Test that vertex builds contain expected structure and data."""
    flow_id = added_webhook_test["id"]
    endpoint_name = added_webhook_test["endpoint_name"]
    endpoint = f"api/v1/webhook/{endpoint_name}"

    # Execute the webhook
    payload = {"verify": "structure"}
    response = await client.post(endpoint, headers={"x-api-key": created_api_key.api_key}, json=payload)
    assert response.status_code == 202

    # Wait for background task to complete
    await asyncio.sleep(2)

    # Check vertex builds
    builds_endpoint = f"api/v1/monitor/builds?flow_id={flow_id}"
    builds_response = await client.get(builds_endpoint, headers={"x-api-key": created_api_key.api_key})

    assert builds_response.status_code == 200
    builds_data = builds_response.json()

    # Verify structure of vertex builds
    for builds in builds_data["vertex_builds"].values():
        assert isinstance(builds, list)
        for build in builds:
            assert "id" in build
            assert "valid" in build
            assert "timestamp" in build
            assert "flow_id" in build
            assert str(build["flow_id"]) == flow_id


async def test_webhook_multiple_executions_create_multiple_builds(client, added_webhook_test, created_api_key):
    """Test that multiple webhook executions create multiple vertex builds."""
    flow_id = added_webhook_test["id"]
    endpoint_name = added_webhook_test["endpoint_name"]
    endpoint = f"api/v1/webhook/{endpoint_name}"

    # Execute webhook multiple times
    for i in range(3):
        payload = {"execution": i}
        response = await client.post(endpoint, headers={"x-api-key": created_api_key.api_key}, json=payload)
        assert response.status_code == 202

    # Wait for all background tasks to complete
    await asyncio.sleep(5)

    # Check vertex builds
    builds_endpoint = f"api/v1/monitor/builds?flow_id={flow_id}"
    builds_response = await client.get(builds_endpoint, headers={"x-api-key": created_api_key.api_key})

    assert builds_response.status_code == 200
    builds_data = builds_response.json()

    # Should have vertex builds
    assert len(builds_data["vertex_builds"]) > 0


async def test_vertex_builds_endpoint_returns_empty_for_new_flow(client, logged_in_headers):
    """Test that vertex builds endpoint returns empty for a flow with no executions."""
    from langflow.services.database.models.flow.model import FlowCreate
    from lfx.components.input_output import ChatInput
    from lfx.graph import Graph

    # Create a new flow without executing it
    chat_input = ChatInput()
    graph = Graph(start=chat_input, end=chat_input)
    graph_dict = graph.dump(name="Empty Test Flow")
    flow = FlowCreate(**graph_dict)

    response = await client.post("api/v1/flows/", json=flow.model_dump(), headers=logged_in_headers)
    assert response.status_code == 201
    flow_id = response.json()["id"]

    try:
        # Check vertex builds - should be empty
        builds_endpoint = f"api/v1/monitor/builds?flow_id={flow_id}"
        builds_response = await client.get(builds_endpoint, headers=logged_in_headers)

        assert builds_response.status_code == 200
        builds_data = builds_response.json()
        assert builds_data["vertex_builds"] == {}
    finally:
        # Cleanup
        await client.delete(f"api/v1/flows/{flow_id}", headers=logged_in_headers)
