import asyncio
from unittest.mock import patch

import aiofiles
import anyio
import pytest
from langflow.services.event_manager import WebhookEventManager


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
    # Modify the auth_settings.WEBHOOK_AUTH_ENABLE on the real settings service
    from langflow.services.deps import get_settings_service

    settings_service = get_settings_service()
    original_webhook_auth_enable = settings_service.auth_settings.WEBHOOK_AUTH_ENABLE

    try:
        settings_service.auth_settings.WEBHOOK_AUTH_ENABLE = True

        endpoint_name = added_webhook_test["endpoint_name"]
        endpoint = f"api/v1/webhook/{endpoint_name}"

        payload = {"path": "/tmp/test_file.txt"}  # noqa: S108

        # Should fail without API key when webhook auth is enabled
        response = await client.post(endpoint, json=payload)
        assert response.status_code == 403
        assert "API key required when webhook authentication is enabled" in response.json()["detail"]
    finally:
        settings_service.auth_settings.WEBHOOK_AUTH_ENABLE = original_webhook_auth_enable


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

        # Wait for background task to complete (webhook returns 202 immediately)
        await asyncio.sleep(2)
        assert await file_path.exists(), f"File {file_path} does not exist"

    file_does_not_exist = not await file_path.exists()
    assert file_does_not_exist, f"File {file_path} still exists"


async def test_webhook_endpoint_unauthorized_user_flow(client, added_webhook_test):
    """Test that webhook fails when user doesn't own the flow."""
    # Modify the auth_settings.WEBHOOK_AUTH_ENABLE on the real settings service
    from langflow.services.deps import get_settings_service

    settings_service = get_settings_service()
    original_webhook_auth_enable = settings_service.auth_settings.WEBHOOK_AUTH_ENABLE

    try:
        settings_service.auth_settings.WEBHOOK_AUTH_ENABLE = True

        # This test would need a different user's API key to test authorization
        # For now, we'll use an invalid API key to simulate this
        endpoint_name = added_webhook_test["endpoint_name"]
        endpoint = f"api/v1/webhook/{endpoint_name}"

        payload = {"path": "/tmp/test_file.txt"}  # noqa: S108

        # Should fail with invalid API key
        response = await client.post(endpoint, headers={"x-api-key": "invalid_key"}, json=payload)
        assert response.status_code == 403
        # Error message may be "Invalid API key" or "API key authentication failed" depending on implementation
        assert "api key" in response.json()["detail"].lower()
    finally:
        settings_service.auth_settings.WEBHOOK_AUTH_ENABLE = original_webhook_auth_enable


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
    # Modify the auth_settings.WEBHOOK_AUTH_ENABLE on the real settings service
    from langflow.services.deps import get_settings_service

    settings_service = get_settings_service()
    original_webhook_auth_enable = settings_service.auth_settings.WEBHOOK_AUTH_ENABLE

    try:
        settings_service.auth_settings.WEBHOOK_AUTH_ENABLE = False

        endpoint_name = added_webhook_test["endpoint_name"]
        endpoint = f"api/v1/webhook/{endpoint_name}"

        payload = {"path": "/tmp/test_auto_login.txt"}  # noqa: S108

        # Should work without API key when webhook auth is disabled
        response = await client.post(endpoint, json=payload)
        assert response.status_code == 202
    finally:
        settings_service.auth_settings.WEBHOOK_AUTH_ENABLE = original_webhook_auth_enable


async def test_webhook_with_random_payload_requires_auth(client, added_webhook_test, created_api_key):
    """Test that webhook with random payload still requires authentication."""
    # Modify the auth_settings.WEBHOOK_AUTH_ENABLE on the real settings service
    from langflow.services.deps import get_settings_service

    settings_service = get_settings_service()

    # Ensure we're modifying the same settings service used by the application
    original_webhook_auth_enable = settings_service.auth_settings.WEBHOOK_AUTH_ENABLE

    try:
        settings_service.auth_settings.WEBHOOK_AUTH_ENABLE = True

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
        assert response.status_code == 202, f"Expected 202, got {response.status_code}: {response.json()}"
    finally:
        settings_service.auth_settings.WEBHOOK_AUTH_ENABLE = original_webhook_auth_enable


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
    from unittest.mock import AsyncMock, MagicMock

    from fastapi import HTTPException
    from langflow.services.auth.service import AuthService

    # Create a mock settings service with WEBHOOK_AUTH_ENABLE=True
    mock_auth_settings = MagicMock()
    mock_auth_settings.WEBHOOK_AUTH_ENABLE = True

    mock_settings_service = MagicMock()
    mock_settings_service.auth_settings = mock_auth_settings

    # Create a mock auth service
    mock_auth_service = MagicMock(spec=AuthService)
    mock_auth_service.settings_service = mock_settings_service
    mock_auth_service.get_webhook_user = AsyncMock(side_effect=HTTPException(status_code=403, detail="Invalid API key"))

    with patch("langflow.api.v1.endpoints.get_auth_service", return_value=mock_auth_service):
        endpoint_name = added_webhook_test["endpoint_name"]
        endpoint = f"api/v1/webhook/{endpoint_name}"
        payload = {"test": "data"}

        response = await client.post(endpoint, headers={"x-api-key": "invalid-api-key"}, json=payload)
        assert response.status_code == 403
        assert "api key" in response.json()["detail"].lower()


async def test_webhook_missing_api_key_when_required(client, added_webhook_test):
    """Test that webhook returns 403 when API key is missing and auth is enabled."""
    from unittest.mock import AsyncMock, MagicMock

    from fastapi import HTTPException
    from langflow.services.auth.service import AuthService

    # Create a mock settings service with WEBHOOK_AUTH_ENABLE=True
    mock_auth_settings = MagicMock()
    mock_auth_settings.WEBHOOK_AUTH_ENABLE = True

    mock_settings_service = MagicMock()
    mock_settings_service.auth_settings = mock_auth_settings

    # Create a mock auth service
    mock_auth_service = MagicMock(spec=AuthService)
    mock_auth_service.settings_service = mock_settings_service
    mock_auth_service.get_webhook_user = AsyncMock(
        side_effect=HTTPException(status_code=403, detail="API key required when webhook authentication is enabled")
    )

    with patch("langflow.api.v1.endpoints.get_auth_service", return_value=mock_auth_service):
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


# =============================================================================
# WEBHOOK EVENT MANAGER TESTS
# =============================================================================


async def test_webhook_event_manager_subscribe_unsubscribe():
    """Test subscribing and unsubscribing from webhook events."""
    manager = WebhookEventManager()
    flow_id = "test-flow-123"

    # Initially no listeners
    assert not manager.has_listeners(flow_id)

    # Subscribe
    queue = await manager.subscribe(flow_id)
    assert manager.has_listeners(flow_id)

    # Unsubscribe
    await manager.unsubscribe(flow_id, queue)
    assert not manager.has_listeners(flow_id)


async def test_webhook_event_manager_emit():
    """Test emitting events to subscribers."""
    manager = WebhookEventManager()
    flow_id = "test-flow-456"

    # Subscribe
    queue = await manager.subscribe(flow_id)

    # Emit event
    await manager.emit(flow_id, "test_event", {"key": "value"})

    # Check event was received
    event = await asyncio.wait_for(queue.get(), timeout=1.0)
    assert event["event"] == "test_event"
    assert event["data"] == {"key": "value"}
    assert "timestamp" in event

    # Cleanup
    await manager.unsubscribe(flow_id, queue)


async def test_webhook_event_manager_emit_no_listeners():
    """Test that emit with no listeners doesn't raise errors."""
    manager = WebhookEventManager()
    flow_id = "test-flow-789"

    # Should not raise any errors
    await manager.emit(flow_id, "test_event", {"key": "value"})


async def test_webhook_event_manager_duration_tracking():
    """Test build duration tracking."""
    manager = WebhookEventManager()
    flow_id = "test-flow-duration"
    vertex_id = "vertex-1"

    # Record start time
    manager.record_build_start(flow_id, vertex_id)

    # Wait a bit
    await asyncio.sleep(0.1)

    # Get duration
    duration = manager.get_build_duration(flow_id, vertex_id)
    assert duration is not None
    assert "ms" in duration  # Should be in milliseconds format

    # Duration should be cleared after getting it
    duration_again = manager.get_build_duration(flow_id, vertex_id)
    assert duration_again is None


async def test_webhook_event_manager_format_duration():
    """Test duration formatting."""
    # Test milliseconds
    assert WebhookEventManager._format_duration(0.5) == "500 ms"
    assert WebhookEventManager._format_duration(0.999) == "999 ms"

    # Test seconds
    assert WebhookEventManager._format_duration(1.0) == "1.0 s"
    assert WebhookEventManager._format_duration(30.5) == "30.5 s"

    # Test minutes
    assert WebhookEventManager._format_duration(60.0) == "1m 0.0s"
    assert WebhookEventManager._format_duration(90.5) == "1m 30.5s"


async def test_webhook_event_manager_multiple_subscribers():
    """Test multiple subscribers receive the same events."""
    manager = WebhookEventManager()
    flow_id = "test-flow-multi"

    # Subscribe multiple times
    queue1 = await manager.subscribe(flow_id)
    queue2 = await manager.subscribe(flow_id)

    # Emit event
    await manager.emit(flow_id, "broadcast", {"msg": "hello"})

    # Both should receive the event
    event1 = await asyncio.wait_for(queue1.get(), timeout=1.0)
    event2 = await asyncio.wait_for(queue2.get(), timeout=1.0)

    assert event1["data"] == {"msg": "hello"}
    assert event2["data"] == {"msg": "hello"}

    # Cleanup
    await manager.unsubscribe(flow_id, queue1)
    await manager.unsubscribe(flow_id, queue2)


# =============================================================================
# UNIT TESTS - PURE FUNCTIONS (NO DB, NO FIXTURES)
# =============================================================================


class TestGetVertexIdsFromFlow:
    """Unit tests for _get_vertex_ids_from_flow helper function."""

    def test_returns_empty_list_when_flow_data_is_none(self):
        """Should return empty list when flow.data is None."""
        from unittest.mock import Mock

        from langflow.api.v1.endpoints import _get_vertex_ids_from_flow

        flow = Mock()
        flow.data = None

        result = _get_vertex_ids_from_flow(flow)

        assert result == []

    def test_returns_empty_list_when_nodes_is_empty(self):
        """Should return empty list when nodes array is empty."""
        from unittest.mock import Mock

        from langflow.api.v1.endpoints import _get_vertex_ids_from_flow

        flow = Mock()
        flow.data = {"nodes": []}

        result = _get_vertex_ids_from_flow(flow)

        assert result == []

    def test_returns_empty_list_when_nodes_key_missing(self):
        """Should return empty list when nodes key is missing."""
        from unittest.mock import Mock

        from langflow.api.v1.endpoints import _get_vertex_ids_from_flow

        flow = Mock()
        flow.data = {"other_key": "value"}

        result = _get_vertex_ids_from_flow(flow)

        assert result == []

    def test_extracts_vertex_ids_from_nodes(self):
        """Should extract all vertex IDs from nodes."""
        from unittest.mock import Mock

        from langflow.api.v1.endpoints import _get_vertex_ids_from_flow

        flow = Mock()
        flow.data = {
            "nodes": [
                {"id": "vertex-1", "type": "ChatInput"},
                {"id": "vertex-2", "type": "ChatOutput"},
                {"id": "vertex-3", "type": "LLM"},
            ]
        }

        result = _get_vertex_ids_from_flow(flow)

        assert result == ["vertex-1", "vertex-2", "vertex-3"]

    def test_skips_nodes_without_id(self):
        """Should skip nodes that don't have an id field."""
        from unittest.mock import Mock

        from langflow.api.v1.endpoints import _get_vertex_ids_from_flow

        flow = Mock()
        flow.data = {
            "nodes": [
                {"id": "vertex-1", "type": "ChatInput"},
                {"type": "NoIdNode"},  # No id
                {"id": None, "type": "NullId"},  # None id
                {"id": "vertex-2", "type": "ChatOutput"},
            ]
        }

        result = _get_vertex_ids_from_flow(flow)

        assert result == ["vertex-1", "vertex-2"]


# =============================================================================
# UNIT TESTS - SIMPLE_RUN_FLOW_TASK (WITH MOCKS)
# =============================================================================


class TestSimpleRunFlowTask:
    """Unit tests for simple_run_flow_task function."""

    async def test_emits_vertices_sorted_event_when_emit_events_true(self):
        """Should emit vertices_sorted event when emit_events=True and has listeners."""
        from unittest.mock import AsyncMock, Mock, patch

        from langflow.api.v1.endpoints import simple_run_flow_task

        flow = Mock()
        flow.id = "test-flow-id"
        flow.data = {"nodes": [{"id": "v1"}, {"id": "v2"}]}

        input_request = Mock()

        with (
            patch("langflow.api.v1.endpoints.simple_run_flow", new_callable=AsyncMock) as mock_run,
            patch("langflow.api.v1.endpoints.webhook_event_manager") as mock_manager,
        ):
            mock_run.return_value = {"result": "success"}
            mock_manager.emit = AsyncMock()

            await simple_run_flow_task(
                flow=flow,
                input_request=input_request,
                emit_events=True,
                flow_id="test-flow-id",
                run_id="run-123",
            )

            # Should emit vertices_sorted
            mock_manager.emit.assert_any_call(
                "test-flow-id",
                "vertices_sorted",
                {"ids": ["v1", "v2"], "to_run": ["v1", "v2"], "run_id": "run-123"},
            )

            # Should emit end with success
            mock_manager.emit.assert_any_call(
                "test-flow-id",
                "end",
                {"run_id": "run-123", "success": True},
            )

    async def test_does_not_emit_events_when_emit_events_false(self):
        """Should not emit events when emit_events=False."""
        from unittest.mock import AsyncMock, Mock, patch

        from langflow.api.v1.endpoints import simple_run_flow_task

        flow = Mock()
        flow.id = "test-flow-id"
        flow.data = {"nodes": [{"id": "v1"}]}

        input_request = Mock()

        with (
            patch("langflow.api.v1.endpoints.simple_run_flow", new_callable=AsyncMock) as mock_run,
            patch("langflow.api.v1.endpoints.webhook_event_manager") as mock_manager,
        ):
            mock_run.return_value = {"result": "success"}
            mock_manager.emit = AsyncMock()

            await simple_run_flow_task(
                flow=flow,
                input_request=input_request,
                emit_events=False,
                flow_id="test-flow-id",
            )

            # Should NOT emit any events
            mock_manager.emit.assert_not_called()

    async def test_emits_error_event_on_exception(self):
        """Should emit end event with error when exception occurs."""
        from unittest.mock import AsyncMock, Mock, patch

        from langflow.api.v1.endpoints import simple_run_flow_task

        flow = Mock()
        flow.id = "test-flow-id"
        flow.data = {"nodes": [{"id": "v1"}]}

        input_request = Mock()

        with (
            patch("langflow.api.v1.endpoints.simple_run_flow", new_callable=AsyncMock) as mock_run,
            patch("langflow.api.v1.endpoints.webhook_event_manager") as mock_manager,
            patch("langflow.api.v1.endpoints.logger") as mock_logger,
        ):
            mock_run.side_effect = Exception("Test error")
            mock_manager.emit = AsyncMock()
            mock_logger.aexception = AsyncMock()

            result = await simple_run_flow_task(
                flow=flow,
                input_request=input_request,
                emit_events=True,
                flow_id="test-flow-id",
                run_id="run-456",
            )

            # Should return None on error
            assert result is None

            # Should emit end with error
            mock_manager.emit.assert_called_with(
                "test-flow-id",
                "end",
                {"run_id": "run-456", "success": False, "error": "Test error"},
            )

    async def test_logs_telemetry_on_success(self):
        """Should log telemetry on successful execution."""
        from unittest.mock import AsyncMock, Mock, patch

        from langflow.api.v1.endpoints import simple_run_flow_task

        flow = Mock()
        flow.id = "test-flow-id"
        flow.data = {"nodes": []}

        input_request = Mock()
        telemetry_service = Mock()
        telemetry_service.log_package_run = AsyncMock()

        with patch("langflow.api.v1.endpoints.simple_run_flow", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = {"result": "success"}

            await simple_run_flow_task(
                flow=flow,
                input_request=input_request,
                telemetry_service=telemetry_service,
                start_time=0.0,
                run_id="run-789",
            )

            # Should log telemetry
            telemetry_service.log_package_run.assert_called_once()
            call_args = telemetry_service.log_package_run.call_args[0][0]
            assert call_args.run_is_webhook is True
            assert call_args.run_success is True


# =============================================================================
# UNIT TESTS - WEBHOOK_EVENTS_STREAM AUTHENTICATION (WITH MOCKS)
# =============================================================================


class TestWebhookEventsStreamAuth:
    """Unit tests for webhook_events_stream authentication."""

    async def test_calls_get_current_user_for_sse_for_authentication(self):
        """Should call get_current_user_for_sse to validate authentication."""
        from unittest.mock import AsyncMock, Mock, patch

        from langflow.api.v1.endpoints import webhook_events_stream

        user_id = "user-123"
        flow = Mock()
        flow.id = "test-flow-id"
        flow.name = "Test Flow"
        flow.user_id = user_id

        request = Mock()
        request.is_disconnected = AsyncMock(return_value=True)  # Disconnect immediately

        mock_user = Mock()
        mock_user.id = user_id

        with (
            patch("langflow.api.v1.endpoints.get_current_user_for_sse", new_callable=AsyncMock) as mock_auth,
            patch("langflow.api.v1.endpoints.webhook_event_manager") as mock_manager,
        ):
            mock_auth.return_value = mock_user
            mock_manager.subscribe = AsyncMock(return_value=asyncio.Queue())
            mock_manager.unsubscribe = AsyncMock()

            await webhook_events_stream(
                flow_id_or_name="test-flow-id",
                flow=flow,
                request=request,
            )

            # Should call get_current_user_for_sse with request
            mock_auth.assert_called_once_with(request)

    async def test_raises_403_when_auth_fails(self):
        """Should propagate 403 error when authentication fails."""
        from unittest.mock import AsyncMock, Mock, patch

        from fastapi import HTTPException
        from langflow.api.v1.endpoints import webhook_events_stream

        flow = Mock()
        flow.id = "test-flow-id"

        request = Mock()

        with patch("langflow.api.v1.endpoints.get_current_user_for_sse", new_callable=AsyncMock) as mock_auth:
            mock_auth.side_effect = HTTPException(status_code=403, detail="Missing or invalid credentials")

            with pytest.raises(HTTPException) as exc_info:
                await webhook_events_stream(
                    flow_id_or_name="test-flow-id",
                    flow=flow,
                    request=request,
                )

            assert exc_info.value.status_code == 403
            assert "Missing or invalid credentials" in exc_info.value.detail

    async def test_raises_403_when_user_does_not_own_flow(self):
        """Should raise 403 when authenticated user doesn't own the flow."""
        from unittest.mock import AsyncMock, Mock, patch

        from fastapi import HTTPException
        from langflow.api.v1.endpoints import webhook_events_stream

        flow = Mock()
        flow.id = "test-flow-id"
        flow.user_id = "owner-user-id"

        mock_user = Mock()
        mock_user.id = "different-user-id"  # Different from flow owner

        request = Mock()

        with patch("langflow.api.v1.endpoints.get_current_user_for_sse", new_callable=AsyncMock) as mock_auth:
            mock_auth.return_value = mock_user

            with pytest.raises(HTTPException) as exc_info:
                await webhook_events_stream(
                    flow_id_or_name="test-flow-id",
                    flow=flow,
                    request=request,
                )

            assert exc_info.value.status_code == 403
            assert "Access denied" in exc_info.value.detail
