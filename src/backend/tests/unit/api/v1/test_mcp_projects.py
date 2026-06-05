import asyncio
import json
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException, status
from httpx import AsyncClient
from langflow.api.v1.mcp_projects import (
    ProjectMCPServer,
    _args_reference_urls,
    get_project_mcp_server,
    get_project_sse,
    get_project_streamable_http_url,
    init_mcp_servers,
    project_mcp_servers,
    project_sse_transports,
)
from langflow.api.v2.mcp import is_mcp_servers_locked
from langflow.services.auth.utils import create_user_longterm_token, get_password_hash
from langflow.services.database.models.flow import Flow
from langflow.services.database.models.folder import Folder
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_settings_service
from lfx.base.mcp.constants import MAX_MCP_SERVER_NAME_LENGTH
from lfx.base.mcp.util import sanitize_mcp_name
from lfx.services.deps import session_scope
from lfx.services.mcp_composer.service import COMPOSER_BACKEND_AUTH_HEADER
from lfx.services.settings.base import Settings
from mcp.server.sse import SseServerTransport
from sqlmodel import select

from tests.unit.utils.mcp import project_session_manager_lifespan

# Mark all tests in this module as asyncio
pytestmark = pytest.mark.asyncio


def _set_startup_mcp_settings(
    monkeypatch,
    *,
    auto_login: bool,
    mcp_composer_enabled: bool,
    add_projects_to_mcp_servers: bool,
) -> None:
    """Configure the runtime settings used by init_mcp_servers for a test."""
    settings_service = get_settings_service()
    monkeypatch.setattr(settings_service.auth_settings, "AUTO_LOGIN", auto_login)
    monkeypatch.setattr(settings_service.settings, "mcp_composer_enabled", mcp_composer_enabled)
    monkeypatch.setattr(
        settings_service.settings,
        "add_projects_to_mcp_servers",
        add_projects_to_mcp_servers,
    )


@pytest.mark.parametrize(
    ("args", "urls", "expected"),
    [
        (None, ["https://langflow.local/sse"], False),
        ([], ["https://langflow.local/sse"], False),
        ([123, {"url": "foo"}], ["https://langflow.local/sse"], False),
        (["https://langflow.local/sse", 42], ["https://langflow.local/sse"], True),
        (["alpha", "beta"], [], False),
    ],
)
def test_args_reference_urls_filters_strings_only(args, urls, expected):
    assert _args_reference_urls(args, urls) is expected


def test_args_reference_urls_matches_non_last_string_argument():
    args = ["match-me", "other"]
    urls = ["match-me"]
    assert _args_reference_urls(args, urls) is True


@pytest.fixture
def mock_project(active_user):
    """Fixture to provide a mock project linked to the active user."""
    return Folder(id=uuid4(), name="Test Project", user_id=active_user.id)


@pytest.fixture
def mock_flow(active_user, mock_project):
    """Fixture to provide a mock flow linked to the active user and project."""
    return Flow(
        id=uuid4(),
        name="Test Flow",
        description="Test Description",
        mcp_enabled=True,
        action_name="test_action",
        action_description="Test Action Description",
        folder_id=mock_project.id,
        user_id=active_user.id,
    )


@pytest.fixture
def mock_project_mcp_server():
    with patch("langflow.api.v1.mcp_projects.ProjectMCPServer") as mock:
        server_instance = MagicMock()
        server_instance.server = MagicMock()
        server_instance.server.name = "test-server"
        server_instance.server.run = AsyncMock()
        server_instance.server.create_initialization_options = MagicMock()
        mock.return_value = server_instance
        yield server_instance


class AsyncContextManagerMock:
    """Mock class that implements async context manager protocol."""

    async def __aenter__(self):
        return (MagicMock(), MagicMock())

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # No teardown required for this mock context manager in tests
        pass


@pytest.fixture
def mock_sse_transport():
    with patch("langflow.api.v1.mcp_projects.SseServerTransport") as mock:
        transport_instance = MagicMock()
        # Create an async context manager for connect_sse
        connect_sse_mock = AsyncContextManagerMock()
        transport_instance.connect_sse = MagicMock(return_value=connect_sse_mock)
        transport_instance.handle_post_message = AsyncMock()
        mock.return_value = transport_instance
        yield transport_instance


@pytest.fixture
def mock_streamable_http_manager():
    """Mock StreamableHTTPSessionManager used by ProjectMCPServer."""
    with patch("langflow.api.v1.mcp_projects.StreamableHTTPSessionManager") as mock_class:
        manager_instance = MagicMock()

        # Mock the run() method to return an async context manager
        async_cm = AsyncContextManagerMock()
        manager_instance.run = MagicMock(return_value=async_cm)

        async def _fake_handle_request(scope, receive, send):  # noqa: ARG001
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"", "more_body": False})

        manager_instance.handle_request = AsyncMock(side_effect=_fake_handle_request)

        # Make the class constructor return our mocked instance
        mock_class.return_value = manager_instance

        yield manager_instance


@pytest.fixture(autouse=True)
def mock_current_user_ctx(active_user):
    with patch("langflow.api.v1.mcp_projects.current_user_ctx") as mock:
        mock.get.return_value = active_user
        mock.set = MagicMock(return_value="dummy_token")
        mock.reset = MagicMock()
        yield mock


@pytest.fixture(autouse=True)
def mock_current_project_ctx(mock_project):
    with patch("langflow.api.v1.mcp_projects.current_project_ctx") as mock:
        mock.get.return_value = mock_project.id
        mock.set = MagicMock(return_value="dummy_token")
        mock.reset = MagicMock()
        yield mock


@pytest.fixture
async def other_test_user():
    """Fixture for creating another test user."""
    user_id = uuid4()
    async with session_scope() as session:
        user = User(
            id=user_id,
            username="other_test_user",
            password=get_password_hash("testpassword"),
            is_active=True,
            is_superuser=False,
        )
        session.add(user)
        await session.flush()
        await session.refresh(user)
    yield user
    # Clean up
    async with session_scope() as session:
        user = await session.get(User, user_id)
        if user:
            await session.delete(user)


@pytest.fixture
async def other_test_project(other_test_user):
    """Fixture for creating a project for another test user."""
    project_id = uuid4()
    async with session_scope() as session:
        project = Folder(id=project_id, name="Other Test Project", user_id=other_test_user.id)
        session.add(project)
        await session.flush()
        await session.refresh(project)
    yield project
    # Clean up
    async with session_scope() as session:
        project = await session.get(Folder, project_id)
        if project:
            await session.delete(project)


@pytest.fixture(autouse=True)
def disable_mcp_composer_by_default():
    """Auto-fixture to disable MCP Composer for all tests by default."""
    with patch("langflow.api.v1.mcp_projects.get_settings_service") as mock_get_settings:
        from langflow.services.deps import get_settings_service

        real_service = get_settings_service()

        # Create a mock that returns False for mcp_composer_enabled but delegates everything else
        mock_service = MagicMock()
        mock_service.settings = MagicMock()
        mock_service.settings.mcp_composer_enabled = False

        # Copy any other settings that might be needed
        mock_service.auth_settings = real_service.auth_settings

        mock_get_settings.return_value = mock_service
        yield


@pytest.fixture
def enable_mcp_composer():
    """Fixture to explicitly enable MCP Composer for specific tests."""
    with patch("langflow.api.v1.mcp_projects.get_settings_service") as mock_get_settings:
        from langflow.services.deps import get_settings_service

        real_service = get_settings_service()

        mock_service = MagicMock()
        mock_service.settings = MagicMock()
        mock_service.settings.mcp_composer_enabled = True

        # Copy any other settings that might be needed
        mock_service.auth_settings = real_service.auth_settings

        mock_get_settings.return_value = mock_service
        yield True


async def test_handle_project_streamable_messages_success(
    client: AsyncClient, user_test_project, mock_streamable_http_manager, logged_in_headers
):
    """Test successful handling of project messages over Streamable HTTP."""
    response = await client.post(
        f"api/v1/mcp/project/{user_test_project.id}/streamable",
        headers=logged_in_headers,
        json={"type": "test", "content": "message"},
    )
    assert response.status_code == status.HTTP_200_OK
    # With StreamableHTTPSessionManager, it calls handle_request, not handle_post_message
    mock_streamable_http_manager.handle_request.assert_called_once()


async def _set_project_auth_type(project_id, auth_type: str) -> None:
    """Persist an auth_settings value for the given project."""
    from langflow.services.auth.mcp_encryption import encrypt_auth_settings

    async with session_scope() as session:
        project = await session.get(Folder, project_id)
        assert project is not None
        project.auth_settings = encrypt_auth_settings({"auth_type": auth_type})
        session.add(project)


async def test_streamable_rejects_unauthenticated_oauth_project(
    client: AsyncClient,
    user_test_project,
    mock_streamable_http_manager,
    enable_mcp_composer,
):
    """OAuth projects must reject any unauthenticated /streamable request.

    Network-level trust (loopback / same-host proxy) is intentionally NOT used here: a
    same-host reverse proxy or sidecar would make every external request appear to be
    loopback, which would reopen the original unauthenticated bypass. Requests must
    present a valid x-api-key regardless of source.
    """
    assert enable_mcp_composer
    await _set_project_auth_type(user_test_project.id, "oauth")

    response = await client.post(
        f"api/v1/mcp/project/{user_test_project.id}/streamable",
        json={"type": "test", "content": "message"},
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "OAuth" in response.json()["detail"]
    mock_streamable_http_manager.handle_request.assert_not_called()


async def test_streamable_rejects_unauthenticated_oauth_project_trailing_slash(
    client: AsyncClient,
    user_test_project,
    mock_streamable_http_manager,
    enable_mcp_composer,
):
    """Trailing-slash variant of /streamable must also enforce OAuth auth."""
    assert enable_mcp_composer
    await _set_project_auth_type(user_test_project.id, "oauth")

    response = await client.post(
        f"api/v1/mcp/project/{user_test_project.id}/streamable/",
        json={"type": "test", "content": "message"},
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    mock_streamable_http_manager.handle_request.assert_not_called()


async def test_sse_rejects_unauthenticated_oauth_project(
    client: AsyncClient,
    user_test_project,
    mock_sse_transport,
    enable_mcp_composer,
):
    """SSE endpoint must also reject unauthenticated OAuth-project requests."""
    assert enable_mcp_composer
    await _set_project_auth_type(user_test_project.id, "oauth")

    response = await client.get(f"api/v1/mcp/project/{user_test_project.id}/sse")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    mock_sse_transport.connect_sse.assert_not_called()


async def test_streamable_oauth_project_accepts_valid_api_key(
    client: AsyncClient,
    user_test_project,
    created_api_key,
    mock_streamable_http_manager,
    enable_mcp_composer,
):
    """Valid API keys must be accepted for OAuth-configured projects."""
    assert enable_mcp_composer
    await _set_project_auth_type(user_test_project.id, "oauth")

    response = await client.post(
        f"api/v1/mcp/project/{user_test_project.id}/streamable",
        headers={"x-api-key": created_api_key.api_key},
        json={"type": "test", "content": "message"},
    )

    assert response.status_code == status.HTTP_200_OK
    mock_streamable_http_manager.handle_request.assert_called_once()


async def test_streamable_oauth_project_accepts_valid_composer_backend_token(
    client: AsyncClient,
    user_test_project,
    mock_streamable_http_manager,
    enable_mcp_composer,
):
    """The in-process MCP Composer token must authenticate Composer's backend hop."""
    assert enable_mcp_composer
    await _set_project_auth_type(user_test_project.id, "oauth")

    composer_service = MagicMock()
    composer_service.validate_backend_auth_token.return_value = True

    with patch("langflow.api.v1.mcp_projects.get_service", return_value=composer_service):
        response = await client.post(
            f"api/v1/mcp/project/{user_test_project.id}/streamable",
            headers={COMPOSER_BACKEND_AUTH_HEADER: "valid-composer-token"},
            json={"type": "test", "content": "message"},
        )

    assert response.status_code == status.HTTP_200_OK
    composer_service.validate_backend_auth_token.assert_called_once_with(
        str(user_test_project.id),
        "valid-composer-token",
    )
    mock_streamable_http_manager.handle_request.assert_called_once()


async def test_streamable_oauth_project_rejects_invalid_api_key(
    client: AsyncClient,
    user_test_project,
    mock_streamable_http_manager,
    enable_mcp_composer,
):
    """Invalid API keys must be rejected for OAuth-configured projects."""
    assert enable_mcp_composer
    await _set_project_auth_type(user_test_project.id, "oauth")

    response = await client.post(
        f"api/v1/mcp/project/{user_test_project.id}/streamable",
        headers={"x-api-key": "not-a-real-api-key"},
        json={"type": "test", "content": "message"},
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["detail"] == "Invalid API key"
    mock_streamable_http_manager.handle_request.assert_not_called()


async def test_handle_project_messages_success(
    client: AsyncClient, user_test_project, mock_sse_transport, logged_in_headers
):
    """Test successful handling of project messages over SSE."""
    response = await client.post(
        f"api/v1/mcp/project/{user_test_project.id}",
        headers=logged_in_headers,
        json={"type": "test", "content": "message"},
    )
    assert response.status_code == status.HTTP_200_OK
    mock_sse_transport.handle_post_message.assert_called_once()


async def test_update_project_mcp_settings_invalid_json(client: AsyncClient, user_test_project, logged_in_headers):
    """Test updating MCP settings with invalid JSON."""
    response = await client.patch(
        f"api/v1/mcp/project/{user_test_project.id}", headers=logged_in_headers, json="invalid"
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


@pytest.fixture
async def test_flow_for_update(active_user, user_test_project):
    """Fixture to provide a real flow for testing MCP settings updates."""
    flow_id = uuid4()
    flow_data = {
        "id": flow_id,
        "name": "Test Flow For Update",
        "description": "Test flow that will be updated",
        "mcp_enabled": True,
        "action_name": "original_action",
        "action_description": "Original description",
        "folder_id": user_test_project.id,
        "user_id": active_user.id,
    }

    # Create the flow in the database
    async with session_scope() as session:
        flow = Flow(**flow_data)
        session.add(flow)
        await session.flush()
        await session.refresh(flow)

    yield flow

    # Clean up
    async with session_scope() as session:
        # Get the flow from the database
        flow = await session.get(Flow, flow_id)
        if flow:
            await session.delete(flow)


async def test_update_project_mcp_settings_success(
    client: AsyncClient, user_test_project, test_flow_for_update, logged_in_headers
):
    """Test successful update of MCP settings using real database."""
    # Create settings for updating the flow
    json_payload = {
        "settings": [
            {
                "id": str(test_flow_for_update.id),
                "action_name": "updated_action",
                "action_description": "Updated description",
                "mcp_enabled": False,
                "name": test_flow_for_update.name,
                "description": test_flow_for_update.description,
            }
        ],
        "auth_settings": {
            "auth_type": "none",
            "api_key": None,
            "iam_endpoint": None,
            "username": None,
            "password": None,
            "bearer_token": None,
        },
    }

    # Make the real PATCH request
    response = await client.patch(
        f"api/v1/mcp/project/{user_test_project.id}", headers=logged_in_headers, json=json_payload
    )

    # Assert response
    assert response.status_code == 200
    assert "Updated MCP settings for 1 flows" in response.json()["message"]

    # Verify the flow was actually updated in the database
    async with session_scope() as session:
        updated_flow = await session.get(Flow, test_flow_for_update.id)
        assert updated_flow is not None
        assert updated_flow.action_name == "updated_action"
        assert updated_flow.action_description == "Updated description"
        assert updated_flow.mcp_enabled is False


async def test_update_project_mcp_settings_invalid_project(client: AsyncClient, logged_in_headers):
    """Test accessing an invalid project ID."""
    # We're using the GET endpoint since it works correctly and tests the same security constraints
    # Generate a random UUID that doesn't exist in the database
    nonexistent_project_id = uuid4()

    # Try to access the project
    response = await client.get(f"api/v1/mcp/project/{nonexistent_project_id}/sse", headers=logged_in_headers)

    # Verify the response
    assert response.status_code == 404
    assert response.json()["detail"] == "Project not found"


async def test_update_project_mcp_settings_other_user_project(
    client: AsyncClient, other_test_project, logged_in_headers
):
    """Test accessing a project belonging to another user."""
    # We're using the GET endpoint since it works correctly and tests the same security constraints
    # This test disables MCP Composer to test JWT token-based access control

    # Try to access the other user's project using active_user's credentials
    response = await client.get(f"api/v1/mcp/project/{other_test_project.id}/sse", headers=logged_in_headers)

    # Verify the response
    assert response.status_code == 404
    assert response.json()["detail"] == "Project not found"


async def test_update_project_mcp_settings_other_user_project_with_composer(
    client: AsyncClient, other_test_project, logged_in_headers, enable_mcp_composer
):
    """Test accessing a project belonging to another user when MCP Composer is enabled."""
    # When MCP Composer is enabled, JWT tokens are not accepted for MCP endpoints
    assert enable_mcp_composer  # Fixture ensures MCP Composer is enabled

    # Try to access the other user's project using active_user's JWT credentials
    response = await client.get(f"api/v1/mcp/project/{other_test_project.id}/sse", headers=logged_in_headers)

    # Verify the response - should get 401 because JWT tokens aren't accepted
    assert response.status_code == 401
    assert "API key required" in response.json()["detail"]


async def test_update_project_mcp_settings_empty_settings(client: AsyncClient, user_test_project, logged_in_headers):
    """Test updating MCP settings with empty settings list."""
    # Use real database objects instead of mocks to avoid the coroutine issue

    # Empty settings list
    json_payload = {
        "settings": [],
        "auth_settings": {
            "auth_type": "none",
            "api_key": None,
            "iam_endpoint": None,
            "username": None,
            "password": None,
            "bearer_token": None,
        },
    }

    # Make the request to the actual endpoint
    response = await client.patch(
        f"api/v1/mcp/project/{user_test_project.id}", headers=logged_in_headers, json=json_payload
    )

    # Verify response - the real endpoint should handle empty settings correctly
    assert response.status_code == 200
    assert "Updated MCP settings for 0 flows" in response.json()["message"]


async def test_user_can_only_access_own_projects(client: AsyncClient, other_test_project, logged_in_headers):
    """Test that a user can only access their own projects."""
    # Try to access the other user's project using first user's credentials
    response = await client.get(f"api/v1/mcp/project/{other_test_project.id}/sse", headers=logged_in_headers)
    # Should fail with 404 as first user cannot see second user's project
    assert response.status_code == 404
    assert response.json()["detail"] == "Project not found"


async def test_user_data_isolation_with_real_db(
    client: AsyncClient, logged_in_headers, other_test_user, other_test_project
):
    """Test that users can only access their own MCP projects using a real database session."""
    # Create a flow for the other test user in their project
    second_flow_id = uuid4()

    # Use real database session just for flow creation and cleanup
    async with session_scope() as session:
        # Create a flow in the other user's project
        second_flow = Flow(
            id=second_flow_id,
            name="Second User Flow",
            description="This flow belongs to the second user",
            mcp_enabled=True,
            action_name="second_user_action",
            action_description="Second user action description",
            folder_id=other_test_project.id,
            user_id=other_test_user.id,
        )

        # Add flow to database
        session.add(second_flow)

    try:
        # Test that first user can't see the project
        response = await client.get(f"api/v1/mcp/project/{other_test_project.id}/sse", headers=logged_in_headers)

        # Should fail with 404
        assert response.status_code == 404
        assert response.json()["detail"] == "Project not found"

        # First user attempts to update second user's flow settings
        # Note: We're not testing the PATCH endpoint because it has the coroutine error
        # Instead, verify permissions via the GET endpoint

    finally:
        # Clean up flow
        async with session_scope() as session:
            second_flow = await session.get(Flow, second_flow_id)
            if second_flow:
                await session.delete(second_flow)


@pytest.fixture
async def user_test_project(active_user):
    """Fixture for creating a project for the active user."""
    project_id = uuid4()
    async with session_scope() as session:
        project = Folder(id=project_id, name="User Test Project", user_id=active_user.id)
        session.add(project)
        await session.flush()
        await session.refresh(project)
    yield project
    # Clean up
    async with session_scope() as session:
        project = await session.get(Folder, project_id)
        if project:
            await session.delete(project)


@pytest.fixture
async def user_test_flow(active_user, user_test_project):
    """Fixture for creating a flow for the active user."""
    flow_id = uuid4()
    async with session_scope() as session:
        flow = Flow(
            id=flow_id,
            name="User Test Flow",
            description="This flow belongs to the active user",
            mcp_enabled=True,
            action_name="user_action",
            action_description="User action description",
            folder_id=user_test_project.id,
            user_id=active_user.id,
        )
        session.add(flow)
        await session.flush()
        await session.refresh(flow)
    yield flow
    # Clean up
    async with session_scope() as session:
        flow = await session.get(Flow, flow_id)
        if flow:
            await session.delete(flow)


async def test_user_can_update_own_flow_mcp_settings(
    client: AsyncClient, logged_in_headers, user_test_project, user_test_flow
):
    """Test that a user can update MCP settings for their own flows using real database."""
    # User attempts to update their own flow settings
    json_payload = {
        "settings": [
            {
                "id": str(user_test_flow.id),
                "action_name": "updated_user_action",
                "action_description": "Updated user action description",
                "mcp_enabled": False,
                "name": "User Test Flow",
                "description": "This flow belongs to the active user",
            }
        ],
        "auth_settings": {
            "auth_type": "none",
            "api_key": None,
            "iam_endpoint": None,
            "username": None,
            "password": None,
            "bearer_token": None,
        },
    }

    # Make the PATCH request to update settings
    response = await client.patch(
        f"api/v1/mcp/project/{user_test_project.id}", headers=logged_in_headers, json=json_payload
    )

    # Should succeed as the user owns this project and flow
    assert response.status_code == 200
    assert "Updated MCP settings for 1 flows" in response.json()["message"]

    # Verify the flow was actually updated in the database
    async with session_scope() as session:
        updated_flow = await session.get(Flow, user_test_flow.id)
        assert updated_flow is not None
        assert updated_flow.action_name == "updated_user_action"
        assert updated_flow.action_description == "Updated user action description"
        assert updated_flow.mcp_enabled is False


async def test_update_project_auth_settings_encryption(
    client: AsyncClient, user_test_project, test_flow_for_update, logged_in_headers
):
    """Test that sensitive auth_settings fields are encrypted when stored."""
    # Create settings with sensitive data
    json_payload = {
        "settings": [
            {
                "id": str(test_flow_for_update.id),
                "action_name": "test_action",
                "action_description": "Test description",
                "mcp_enabled": True,
                "name": test_flow_for_update.name,
                "description": test_flow_for_update.description,
            }
        ],
        "auth_settings": {
            "auth_type": "oauth",
            "oauth_host": "localhost",
            "oauth_port": "3000",
            "oauth_server_url": "http://localhost:3000",
            "oauth_callback_path": "/callback",
            "oauth_client_id": "test-client-id",
            "oauth_client_secret": "test-oauth-secret-value-456",
            "oauth_auth_url": "https://oauth.example.com/auth",
            "oauth_token_url": "https://oauth.example.com/token",
            "oauth_mcp_scope": "read write",
            "oauth_provider_scope": "user:email",
        },
    }

    # Send the update request
    response = await client.patch(
        f"/api/v1/mcp/project/{user_test_project.id}",
        json=json_payload,
        headers=logged_in_headers,
    )
    assert response.status_code == 200

    # Verify the sensitive data is encrypted in the database
    async with session_scope() as session:
        updated_project = await session.get(Folder, user_test_project.id)
        assert updated_project is not None
        assert updated_project.auth_settings is not None

        # Check that sensitive field is encrypted (not plaintext)
        stored_value = updated_project.auth_settings.get("oauth_client_secret")
        assert stored_value is not None
        assert stored_value != "test-oauth-secret-value-456"  # Should be encrypted

        # The encrypted value should be a base64-like string (Fernet token)
        assert len(stored_value) > 50  # Encrypted values are longer

    # Now test that the GET endpoint returns the data (SecretStr will be masked)
    response = await client.get(
        f"/api/v1/mcp/project/{user_test_project.id}",
        headers=logged_in_headers,
    )
    assert response.status_code == 200
    data = response.json()

    # SecretStr fields are masked in the response for security
    assert data["auth_settings"]["oauth_client_secret"] == "**********"  # noqa: S105
    assert data["auth_settings"]["oauth_client_id"] == "test-client-id"
    assert data["auth_settings"]["auth_type"] == "oauth"

    # Verify that decryption is working by checking the actual decrypted value in the backend
    from langflow.services.auth.mcp_encryption import decrypt_auth_settings

    async with session_scope() as session:
        project = await session.get(Folder, user_test_project.id)
        decrypted_settings = decrypt_auth_settings(project.auth_settings)
        assert decrypted_settings["oauth_client_secret"] == "test-oauth-secret-value-456"  # noqa: S105


async def test_project_sse_creation(user_test_project):
    """Test that SSE transport and MCP server are correctly created for a project."""
    # Test getting an SSE transport for the first time
    project_id = user_test_project.id
    project_id_str = str(project_id)

    # Ensure there's no SSE transport for this project yet
    if project_id_str in project_sse_transports:
        del project_sse_transports[project_id_str]

    # Get an SSE transport
    sse_transport = get_project_sse(project_id)

    # Verify the transport was created correctly
    assert project_id_str in project_sse_transports
    assert sse_transport is project_sse_transports[project_id_str]
    assert isinstance(sse_transport, SseServerTransport)

    # Test getting an MCP server for the first time
    if project_id_str in project_mcp_servers:
        del project_mcp_servers[project_id_str]

    # Get an MCP server
    mcp_server = get_project_mcp_server(project_id)

    # Verify the server was created correctly
    assert project_id_str in project_mcp_servers
    assert mcp_server is project_mcp_servers[project_id_str]
    assert isinstance(mcp_server, ProjectMCPServer)
    assert mcp_server.project_id == project_id
    assert mcp_server.server.name == f"langflow-mcp-project-{project_id}"

    # Test that getting the same SSE transport and MCP server again returns the cached instances
    sse_transport2 = get_project_sse(project_id)
    mcp_server2 = get_project_mcp_server(project_id)

    assert sse_transport2 is sse_transport
    assert mcp_server2 is mcp_server
    # Yield control to the event loop to satisfy async usage in this test
    await asyncio.sleep(0)


async def test_project_session_manager_lifespan_handles_cleanup(user_test_project, monkeypatch):
    """Session manager contexts should be cleaned up automatically via shared lifespan stack."""
    project_mcp_servers.clear()
    lifecycle_events: list[str] = []

    @asynccontextmanager
    async def fake_run():
        lifecycle_events.append("enter")
        try:
            yield
        finally:
            lifecycle_events.append("exit")

    monkeypatch.setattr(
        "langflow.api.v1.mcp_projects.StreamableHTTPSessionManager.run",
        lambda self: fake_run(),  # noqa: ARG005
    )

    async with project_session_manager_lifespan():
        server = get_project_mcp_server(user_test_project.id)
        await server.ensure_session_manager_running()
        assert lifecycle_events == ["enter"]

    assert lifecycle_events == ["enter", "exit"]


def _prepare_install_test_env(monkeypatch, tmp_path, filename="cursor.json"):
    config_path = tmp_path / filename
    config_path.parent.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr("langflow.api.v1.mcp_projects.get_client_ip", lambda request: "127.0.0.1")  # noqa: ARG005

    async def fake_get_config_path(client_name):  # noqa: ARG001
        return config_path

    monkeypatch.setattr("langflow.api.v1.mcp_projects.get_config_path", fake_get_config_path)
    monkeypatch.setattr("langflow.api.v1.mcp_projects.platform.system", lambda: "Linux")
    monkeypatch.setattr("langflow.api.v1.mcp_projects.should_use_mcp_composer", lambda project: False)  # noqa: ARG005

    async def fake_streamable(project_id):
        return f"https://langflow.local/api/v1/mcp/project/{project_id}/streamable"

    async def fake_sse(project_id):
        return f"https://langflow.local/api/v1/mcp/project/{project_id}/sse"

    monkeypatch.setattr("langflow.api.v1.mcp_projects.get_project_streamable_http_url", fake_streamable)
    monkeypatch.setattr("langflow.api.v1.mcp_projects.get_project_sse_url", fake_sse)

    class DummyAuth:
        AUTO_LOGIN = True
        SUPERUSER = True

    dummy_settings = SimpleNamespace(host="localhost", port=9999, mcp_composer_enabled=False)
    dummy_service = SimpleNamespace(settings=dummy_settings, auth_settings=DummyAuth())
    monkeypatch.setattr("langflow.api.v1.mcp_projects.get_settings_service", lambda: dummy_service)

    return config_path


async def test_is_mcp_servers_locked_does_not_fire_for_magicmock_settings():
    settings = MagicMock()
    # Simulate test fixtures where unknown attrs return truthy MagicMock placeholders.
    assert is_mcp_servers_locked(settings) is False


async def test_is_mcp_servers_locked_respects_explicit_true_flag():
    settings = SimpleNamespace(mcp_servers_locked=True)
    assert is_mcp_servers_locked(settings) is True


async def test_settings_model_declares_mcp_servers_locked_field(monkeypatch):
    """Regression guard: mcp lock must be configurable via Settings/env vars."""
    assert "mcp_servers_locked" in Settings.model_fields
    monkeypatch.setenv("LANGFLOW_MCP_SERVERS_LOCKED", "true")
    assert Settings().mcp_servers_locked is True


async def test_v2_mcp_servers_locked_blocks_non_superuser_add_patch_delete(
    client: AsyncClient,
    logged_in_headers,
    monkeypatch,
):
    monkeypatch.setattr("langflow.api.v2.mcp.is_mcp_servers_locked", lambda _settings: True)

    server_name = f"lf-lock-test-{uuid4().hex[:8]}"
    server_config = {
        "command": "uvx",
        "args": ["mcp-proxy", "--transport", "sse", "https://langflow.local/sse"],
    }

    response = await client.post(f"/api/v2/mcp/servers/{server_name}", json=server_config, headers=logged_in_headers)
    assert response.status_code == status.HTTP_403_FORBIDDEN

    response = await client.patch(
        f"/api/v2/mcp/servers/{server_name}",
        json={"description": "updated"},
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN

    response = await client.delete(f"/api/v2/mcp/servers/{server_name}", headers=logged_in_headers)
    assert response.status_code == status.HTTP_403_FORBIDDEN


async def test_v2_mcp_servers_locked_allows_superuser_add_patch_delete(
    client: AsyncClient,
    monkeypatch,
):
    monkeypatch.setattr("langflow.api.v2.mcp.is_mcp_servers_locked", lambda _settings: True)

    username = f"super_lock_{uuid4().hex[:8]}"
    login_password = f"lfx-{uuid4().hex[:12]}"
    async with session_scope() as session:
        super_user = User(
            username=username,
            password=get_password_hash(login_password),
            is_active=True,
            is_superuser=True,
        )
        session.add(super_user)

    login_response = await client.post("api/v1/login", data={"username": username, "password": login_password})
    assert login_response.status_code == status.HTTP_200_OK
    access_token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    server_name = f"lf-lock-super-{uuid4().hex[:8]}"
    server_config = {
        "command": "uvx",
        "args": ["mcp-proxy", "--transport", "sse", "https://langflow.local/sse"],
    }

    response = await client.post(
        f"/api/v2/mcp/servers/{server_name}",
        json=server_config,
        headers=headers,
    )
    assert response.status_code == status.HTTP_200_OK

    response = await client.patch(
        f"/api/v2/mcp/servers/{server_name}",
        json={"description": "updated"},
        headers=headers,
    )
    assert response.status_code == status.HTTP_200_OK

    response = await client.delete(f"/api/v2/mcp/servers/{server_name}", headers=headers)
    assert response.status_code == status.HTTP_200_OK


async def test_install_mcp_config_defaults_to_sse_transport(
    client: AsyncClient,
    user_test_project,
    logged_in_headers,
    tmp_path,
    monkeypatch,
):
    config_path = _prepare_install_test_env(monkeypatch, tmp_path, "cursor_sse.json")

    response = await client.post(
        f"/api/v1/mcp/project/{user_test_project.id}/install",
        headers=logged_in_headers,
        json={"client": "cursor"},
    )

    assert response.status_code == status.HTTP_200_OK
    installed_config = json.loads(config_path.read_text())
    server_name = "lf-user_test_project"
    args = installed_config["mcpServers"][server_name]["args"]
    assert "--transport" not in args
    assert args[-1].endswith("/sse")


async def test_install_mcp_config_streamable_transport(
    client: AsyncClient,
    user_test_project,
    logged_in_headers,
    tmp_path,
    monkeypatch,
):
    config_path = _prepare_install_test_env(monkeypatch, tmp_path, "cursor_streamable.json")

    response = await client.post(
        f"/api/v1/mcp/project/{user_test_project.id}/install",
        headers=logged_in_headers,
        json={"client": "cursor", "transport": "streamablehttp"},
    )

    assert response.status_code == status.HTTP_200_OK
    installed_config = json.loads(config_path.read_text())
    server_name = "lf-user_test_project"
    args = installed_config["mcpServers"][server_name]["args"]
    assert "--transport" in args
    assert "streamablehttp" in args
    assert args[-1].endswith("/streamable")


async def test_init_mcp_servers(user_test_project, other_test_project):
    """Test the initialization of MCP servers for all projects."""
    # Clear existing caches
    project_sse_transports.clear()
    project_mcp_servers.clear()

    # Test the initialization function
    await init_mcp_servers()

    # Verify that both test projects have SSE transports and MCP servers initialized
    project1_id = str(user_test_project.id)
    project2_id = str(other_test_project.id)

    # Both projects should have SSE transports created
    assert project1_id in project_sse_transports
    assert project2_id in project_sse_transports

    # Both projects should have MCP servers created
    assert project1_id in project_mcp_servers
    assert project2_id in project_mcp_servers

    # Verify the correct configuration
    assert isinstance(project_sse_transports[project1_id], SseServerTransport)
    assert isinstance(project_sse_transports[project2_id], SseServerTransport)
    assert isinstance(project_mcp_servers[project1_id], ProjectMCPServer)
    assert isinstance(project_mcp_servers[project2_id], ProjectMCPServer)

    assert project_mcp_servers[project1_id].project_id == user_test_project.id
    assert project_mcp_servers[project2_id].project_id == other_test_project.id


async def test_init_mcp_servers_error_handling():
    """Test that init_mcp_servers handles SSE errors correctly and continues initialization."""
    # Clear existing caches
    project_sse_transports.clear()
    project_mcp_servers.clear()

    # Create a mock to simulate an error when initializing one project
    original_get_project_sse = get_project_sse

    def mock_get_project_sse(project_id):
        # Raise an exception for the first project only
        if not project_sse_transports:  # Only for the first project
            msg = "Test error for project SSE creation"
            raise ValueError(msg)
        return original_get_project_sse(project_id)

    # Apply the patch
    with patch("langflow.api.v1.mcp_projects.get_project_sse", side_effect=mock_get_project_sse):
        # This should not raise any exception, as the error should be caught
        await init_mcp_servers()


async def test_init_mcp_servers_error_handling_streamable():
    """Test that init_mcp_servers handles MCP server errors correctly and continues initialization."""
    # Clear existing caches
    project_mcp_servers.clear()

    # Create a mock to simulate an error when initializing one project
    original_get_project_mcp_server = get_project_mcp_server

    def mock_get_project_mcp_server(project_id):
        # Raise an exception for the first project only
        if not project_mcp_servers:  # Only for the first project
            msg = "Test error for project MCP server creation"
            raise ValueError(msg)
        return original_get_project_mcp_server(project_id)

    # Apply the patch
    with patch("langflow.api.v1.mcp_projects.get_project_mcp_server", side_effect=mock_get_project_mcp_server):
        # This should not raise any exception, as the error should be caught
        await init_mcp_servers()


async def test_init_mcp_servers_reconciles_project_server_auth_when_oauth_falls_back(
    user_test_project,
):
    """Startup should refresh MCP server config after OAuth falls back to API key auth."""
    project_sse_transports.clear()
    project_mcp_servers.clear()

    async with session_scope() as session:
        project = await session.get(Folder, user_test_project.id)
        assert project is not None
        project.auth_settings = {"auth_type": "oauth"}
        session.add(project)

    with (
        patch("langflow.api.v1.mcp_projects.get_project_sse"),
        patch("langflow.api.v1.mcp_projects.get_project_mcp_server"),
        patch("langflow.api.v1.mcp_projects.auto_configure_starter_projects_mcp", new=AsyncMock()),
        patch("langflow.api.v1.mcp_projects.get_settings_service") as mock_get_settings,
        patch(
            "langflow.api.v1.projects_mcp_helpers.register_mcp_servers_for_project",
            new=AsyncMock(return_value=True),
        ),
    ):
        mock_service = MagicMock()
        mock_service.settings = SimpleNamespace(mcp_composer_enabled=False, add_projects_to_mcp_servers=True)
        mock_service.auth_settings = SimpleNamespace(AUTO_LOGIN=False)
        mock_get_settings.return_value = mock_service
        await init_mcp_servers()

    async with session_scope() as session:
        project = await session.get(Folder, user_test_project.id)
        assert project is not None
        assert project.auth_settings is not None
        assert project.auth_settings["auth_type"] == "apikey"


async def test_init_mcp_servers_reconciles_existing_apikey_project_server_config(
    client: AsyncClient,
    user_test_project,
    created_api_key,
    monkeypatch,
):
    """Startup should repair stale MCP server config even when auth was already persisted earlier."""
    project_sse_transports.clear()
    project_mcp_servers.clear()
    _set_startup_mcp_settings(
        monkeypatch,
        auto_login=False,
        mcp_composer_enabled=False,
        add_projects_to_mcp_servers=True,
    )

    async with session_scope() as session:
        project = await session.get(Folder, user_test_project.id)
        assert project is not None
        project.auth_settings = {"auth_type": "apikey"}
        session.add(project)

    server_name = f"lf-{sanitize_mcp_name(user_test_project.name)[: (MAX_MCP_SERVER_NAME_LENGTH - 4)]}"
    streamable_http_url = await get_project_streamable_http_url(user_test_project.id)
    stale_server_config = {
        "command": "uvx",
        "args": ["mcp-proxy", "--transport", "streamablehttp", streamable_http_url],
    }
    headers = {"x-api-key": created_api_key.api_key}

    response = await client.post(f"/api/v2/mcp/servers/{server_name}", json=stale_server_config, headers=headers)
    assert response.status_code == 200

    try:
        with (
            patch("langflow.api.v1.mcp_projects.get_project_sse"),
            patch("langflow.api.v1.mcp_projects.get_project_mcp_server"),
            patch("langflow.api.v1.mcp_projects.auto_configure_starter_projects_mcp", new=AsyncMock()),
        ):
            await init_mcp_servers()

        response = await client.get(f"/api/v2/mcp/servers/{server_name}", headers=headers)
        assert response.status_code == 200
        server_config = response.json()
        server_args = server_config["args"]
        assert "mcp-proxy" in server_args
        assert "--transport" in server_args
        assert "streamablehttp" in server_args
        assert "--headers" in server_args
        assert "x-api-key" in server_args
        assert streamable_http_url in server_args
    finally:
        await client.delete(f"/api/v2/mcp/servers/{server_name}", headers=headers)


async def test_patch_project_mcp_settings_syncs_server_config_for_apikey(
    client: AsyncClient,
    user_test_project,
    created_api_key,
    logged_in_headers,
    monkeypatch,
):
    """PATCH /api/v1/mcp/project/{id} with auth_type=apikey must propagate x-api-key to MCP server args.

    Regression test for the PATCH-path gap where auth_settings was updated in the DB but the
    corresponding MCP server config was never reconciled, leaving args without --headers x-api-key
    and causing subsequent startup reconciliation to generate duplicate Langflow API keys.
    """
    project_sse_transports.clear()
    project_mcp_servers.clear()
    _set_startup_mcp_settings(
        monkeypatch,
        auto_login=False,
        mcp_composer_enabled=False,
        add_projects_to_mcp_servers=True,
    )

    server_name = f"lf-{sanitize_mcp_name(user_test_project.name)[: (MAX_MCP_SERVER_NAME_LENGTH - 4)]}"
    streamable_http_url = await get_project_streamable_http_url(user_test_project.id)
    # Seed the server registry with a config that does NOT yet include the apikey header.
    stale_server_config = {
        "command": "uvx",
        "args": ["mcp-proxy", "--transport", "streamablehttp", streamable_http_url],
    }
    api_headers = {"x-api-key": created_api_key.api_key}
    response = await client.post(f"/api/v2/mcp/servers/{server_name}", json=stale_server_config, headers=api_headers)
    assert response.status_code == 200

    try:
        patch_payload = {
            "settings": [],
            "auth_settings": {"auth_type": "apikey"},
        }
        response = await client.patch(
            f"/api/v1/mcp/project/{user_test_project.id}",
            headers=logged_in_headers,
            json=patch_payload,
        )
        assert response.status_code == 200

        # Server config should now reflect apikey auth (--headers x-api-key injected).
        response = await client.get(f"/api/v2/mcp/servers/{server_name}", headers=api_headers)
        assert response.status_code == 200
        server_args = response.json()["args"]
        assert "--headers" in server_args
        assert "x-api-key" in server_args
        assert streamable_http_url in server_args

        # PATCHing again with the same auth should be a no-op — no duplicate key creation.
        with patch("langflow.api.v1.projects_mcp_helpers.create_api_key") as mock_create_api_key:
            response = await client.patch(
                f"/api/v1/mcp/project/{user_test_project.id}",
                headers=logged_in_headers,
                json=patch_payload,
            )
            assert response.status_code == 200
            mock_create_api_key.assert_not_called()
    finally:
        await client.delete(f"/api/v2/mcp/servers/{server_name}", headers=api_headers)


async def test_init_mcp_servers_rolls_back_auth_update_when_reconciliation_fails(
    user_test_project,
    monkeypatch,
):
    """Startup should not persist auth changes if MCP server reconciliation fails."""
    project_sse_transports.clear()
    project_mcp_servers.clear()
    _set_startup_mcp_settings(
        monkeypatch,
        auto_login=False,
        mcp_composer_enabled=False,
        add_projects_to_mcp_servers=True,
    )

    async with session_scope() as session:
        project = await session.get(Folder, user_test_project.id)
        assert project is not None
        project.auth_settings = None
        session.add(project)

    with (
        patch("langflow.api.v1.mcp_projects.get_project_sse"),
        patch("langflow.api.v1.mcp_projects.get_project_mcp_server"),
        patch("langflow.api.v1.mcp_projects.auto_configure_starter_projects_mcp", new=AsyncMock()),
        patch(
            "langflow.api.v1.projects_mcp_helpers.create_api_key",
            new=AsyncMock(return_value=SimpleNamespace(api_key="generated-key")),
        ),
        patch(
            "langflow.api.v1.projects_mcp_helpers.update_server",
            new=AsyncMock(side_effect=RuntimeError("server sync failed")),
        ),
    ):
        await init_mcp_servers()

    async with session_scope() as session:
        project = await session.get(Folder, user_test_project.id)
        assert project is not None
        assert project.auth_settings is None


async def test_list_project_tools_with_mcp_enabled_filter(
    client: AsyncClient, user_test_project, active_user, logged_in_headers
):
    """Test that the list_project_tools endpoint correctly filters by mcp_enabled parameter."""
    # Create two flows: one with mcp_enabled=True and one with mcp_enabled=False
    enabled_flow_id = uuid4()
    disabled_flow_id = uuid4()

    async with session_scope() as session:
        # Create an MCP-enabled flow
        enabled_flow = Flow(
            id=enabled_flow_id,
            name="Enabled Flow",
            description="This flow is MCP enabled",
            mcp_enabled=True,
            action_name="enabled_action",
            action_description="Enabled action description",
            folder_id=user_test_project.id,
            user_id=active_user.id,
        )
        # Create an MCP-disabled flow
        disabled_flow = Flow(
            id=disabled_flow_id,
            name="Disabled Flow",
            description="This flow is MCP disabled",
            mcp_enabled=False,
            action_name="disabled_action",
            action_description="Disabled action description",
            folder_id=user_test_project.id,
            user_id=active_user.id,
        )
        session.add(enabled_flow)
        session.add(disabled_flow)
        await session.flush()

    try:
        # Test 1: With mcp_enabled=True (default), should only return enabled flows
        response = await client.get(
            f"/api/v1/mcp/project/{user_test_project.id}",
            headers=logged_in_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "tools" in data
        tools = data["tools"]
        # Should only include the enabled flow
        assert len(tools) == 1
        assert tools[0]["name"] == "Enabled Flow"
        assert tools[0]["action_name"] == "enabled_action"

        # Test 2: With mcp_enabled=True explicitly, should only return enabled flows
        response = await client.get(
            f"/api/v1/mcp/project/{user_test_project.id}?mcp_enabled=true",
            headers=logged_in_headers,
        )
        assert response.status_code == 200
        data = response.json()
        tools = data["tools"]
        assert len(tools) == 1
        assert tools[0]["name"] == "Enabled Flow"

        # Test 3: With mcp_enabled=False, should return all flows
        response = await client.get(
            f"/api/v1/mcp/project/{user_test_project.id}?mcp_enabled=false",
            headers=logged_in_headers,
        )
        assert response.status_code == 200
        data = response.json()
        tools = data["tools"]
        # Should include both flows
        assert len(tools) == 2
        flow_names = {tool["name"] for tool in tools}
        assert "Enabled Flow" in flow_names
        assert "Disabled Flow" in flow_names

    finally:
        # Clean up flows
        async with session_scope() as session:
            enabled_flow = await session.get(Flow, enabled_flow_id)
            if enabled_flow:
                await session.delete(enabled_flow)
            disabled_flow = await session.get(Flow, disabled_flow_id)
            if disabled_flow:
                await session.delete(disabled_flow)


async def test_list_project_tools_response_structure(client: AsyncClient, user_test_project, logged_in_headers):
    """Test that the list_project_tools endpoint returns the correct MCPProjectResponse structure."""
    response = await client.get(
        f"/api/v1/mcp/project/{user_test_project.id}",
        headers=logged_in_headers,
    )
    assert response.status_code == 200
    data = response.json()

    # Verify response structure matches MCPProjectResponse
    assert "tools" in data
    assert "auth_settings" in data
    assert isinstance(data["tools"], list)

    # Verify tool structure
    if len(data["tools"]) > 0:
        tool = data["tools"][0]
        assert "id" in tool
        assert "name" in tool
        assert "description" in tool
        assert "action_name" in tool
        assert "action_description" in tool
        assert "mcp_enabled" in tool


@pytest.mark.asyncio
async def test_mcp_longterm_token_fails_without_superuser():
    """When AUTO_LOGIN is false and no superuser exists, creating a long-term token should raise 400.

    This simulates a clean DB with AUTO_LOGIN disabled and without provisioning a superuser.
    """
    settings_service = get_settings_service()
    settings_service.auth_settings.AUTO_LOGIN = False

    # Ensure no superuser exists in DB
    async with session_scope() as session:
        result = await session.exec(select(User).where(User.is_superuser == True))  # noqa: E712
        users = result.all()
        for user in users:
            await session.delete(user)

    # Now attempt to create long-term token -> expect HTTPException 400
    async with session_scope() as session:
        with pytest.raises(HTTPException, match="Auto login required to create a long-term token"):
            await create_user_longterm_token(session)


def _prepare_installed_check_env(monkeypatch, tmp_path):
    """Set up environment for check_installed_mcp_servers tests.

    Creates per-client config directories under tmp_path so that
    ``get_config_path`` returns paths whose *parent* directories exist
    but whose config *files* may or may not exist.
    """
    client_paths = {
        "cursor": tmp_path / "cursor" / "mcp.json",
        "windsurf": tmp_path / "windsurf" / "mcp_config.json",
        "claude": tmp_path / "claude" / "claude_desktop_config.json",
    }
    # Create parent directories (simulating installed applications)
    for path in client_paths.values():
        path.parent.mkdir(parents=True, exist_ok=True)

    async def fake_get_config_path(client_name):
        return client_paths[client_name]

    monkeypatch.setattr("langflow.api.v1.mcp_projects.get_config_path", fake_get_config_path)
    monkeypatch.setattr("langflow.api.v1.mcp_projects.should_use_mcp_composer", lambda project: False)  # noqa: ARG005

    async def fake_streamable(project_id):
        return f"https://langflow.local/api/v1/mcp/project/{project_id}/streamable"

    async def fake_sse(project_id):
        return f"https://langflow.local/api/v1/mcp/project/{project_id}/sse"

    monkeypatch.setattr("langflow.api.v1.mcp_projects.get_project_streamable_http_url", fake_streamable)
    monkeypatch.setattr("langflow.api.v1.mcp_projects.get_project_sse_url", fake_sse)

    return client_paths


async def test_should_report_available_true_when_app_directory_exists_but_config_file_missing(
    client: AsyncClient,
    user_test_project,
    logged_in_headers,
    tmp_path,
    monkeypatch,
):
    """Bug: FileNotFoundError when config file is missing marks client as unavailable.

    GIVEN: App directories exist (e.g. ~/.cursor/) but config files don't exist yet
    WHEN:  GET /mcp/project/{id}/installed is called
    THEN:  Each client should have available=True (app is installed) and installed=False (not configured)
    """
    _prepare_installed_check_env(monkeypatch, tmp_path)

    response = await client.get(
        f"/api/v1/mcp/project/{user_test_project.id}/installed",
        headers=logged_in_headers,
    )

    assert response.status_code == 200
    results = response.json()

    # All three clients should be reported
    assert len(results) == 3

    for entry in results:
        assert entry["available"] is True, (
            f"{entry['name']} should be available (directory exists) even when config file is missing"
        )
        assert entry["installed"] is False, f"{entry['name']} should not be installed (config file doesn't exist)"


async def test_should_report_installed_true_when_config_file_contains_matching_url(
    client: AsyncClient,
    user_test_project,
    logged_in_headers,
    tmp_path,
    monkeypatch,
):
    """Config with matching URL marks client as installed.

    GIVEN: Config files exist with a matching project URL in mcpServers args
    WHEN:  GET /mcp/project/{id}/installed is called
    THEN:  Each client should have available=True AND installed=True
    """
    client_paths = _prepare_installed_check_env(monkeypatch, tmp_path)

    # Write config files with matching URLs for all clients
    project_id = user_test_project.id
    for path in client_paths.values():
        config = {"mcpServers": {"lf-test": {"args": [f"https://langflow.local/api/v1/mcp/project/{project_id}/sse"]}}}
        path.write_text(json.dumps(config))

    response = await client.get(
        f"/api/v1/mcp/project/{project_id}/installed",
        headers=logged_in_headers,
    )

    assert response.status_code == 200
    results = response.json()

    for entry in results:
        assert entry["available"] is True, f"{entry['name']} should be available"
        assert entry["installed"] is True, f"{entry['name']} should be installed (config has matching URL)"


async def test_should_report_installed_false_when_config_file_has_no_matching_url(
    client: AsyncClient,
    user_test_project,
    logged_in_headers,
    tmp_path,
    monkeypatch,
):
    """Config with non-matching URL reports installed=False.

    GIVEN: Config files exist but with a DIFFERENT project URL
    WHEN:  GET /mcp/project/{id}/installed is called
    THEN:  available=True (file exists) but installed=False (URL doesn't match)
    """
    client_paths = _prepare_installed_check_env(monkeypatch, tmp_path)

    for path in client_paths.values():
        config = {"mcpServers": {"other-server": {"args": ["https://other-server.example.com/sse"]}}}
        path.write_text(json.dumps(config))

    response = await client.get(
        f"/api/v1/mcp/project/{user_test_project.id}/installed",
        headers=logged_in_headers,
    )

    assert response.status_code == 200
    results = response.json()

    for entry in results:
        assert entry["available"] is True, f"{entry['name']} should be available"
        assert entry["installed"] is False, f"{entry['name']} should not be installed (URL doesn't match)"


async def test_should_report_available_false_when_app_directory_does_not_exist(
    client: AsyncClient,
    user_test_project,
    logged_in_headers,
    tmp_path,
    monkeypatch,
):
    """Missing app directory reports available=False.

    GIVEN: App directories do NOT exist (applications not installed)
    WHEN:  GET /mcp/project/{id}/installed is called
    THEN:  available=False and installed=False for all clients
    """
    # Point to paths whose parent directories do NOT exist
    nonexistent_paths = {
        "cursor": tmp_path / "nonexistent_cursor" / "mcp.json",
        "windsurf": tmp_path / "nonexistent_windsurf" / "mcp_config.json",
        "claude": tmp_path / "nonexistent_claude" / "claude_desktop_config.json",
    }

    async def fake_get_config_path(client_name):
        return nonexistent_paths[client_name]

    monkeypatch.setattr("langflow.api.v1.mcp_projects.get_config_path", fake_get_config_path)
    monkeypatch.setattr("langflow.api.v1.mcp_projects.should_use_mcp_composer", lambda project: False)  # noqa: ARG005

    async def fake_streamable(project_id):
        return f"https://langflow.local/api/v1/mcp/project/{project_id}/streamable"

    async def fake_sse(project_id):
        return f"https://langflow.local/api/v1/mcp/project/{project_id}/sse"

    monkeypatch.setattr("langflow.api.v1.mcp_projects.get_project_streamable_http_url", fake_streamable)
    monkeypatch.setattr("langflow.api.v1.mcp_projects.get_project_sse_url", fake_sse)

    response = await client.get(
        f"/api/v1/mcp/project/{user_test_project.id}/installed",
        headers=logged_in_headers,
    )

    assert response.status_code == 200
    results = response.json()

    for entry in results:
        assert entry["available"] is False, f"{entry['name']} should not be available (directory doesn't exist)"
        assert entry["installed"] is False


async def test_should_report_available_true_when_config_file_has_corrupt_json(
    client: AsyncClient,
    user_test_project,
    logged_in_headers,
    tmp_path,
    monkeypatch,
):
    """Corrupt JSON config reports available=True but installed=False.

    GIVEN: Config files exist but contain invalid/corrupt JSON
    WHEN:  GET /mcp/project/{id}/installed is called
    THEN:  available=True (directory exists) but installed=False (can't parse config)
    """
    client_paths = _prepare_installed_check_env(monkeypatch, tmp_path)

    for path in client_paths.values():
        path.write_text("{corrupt json content!!! not valid")

    response = await client.get(
        f"/api/v1/mcp/project/{user_test_project.id}/installed",
        headers=logged_in_headers,
    )

    assert response.status_code == 200
    results = response.json()

    for entry in results:
        assert entry["available"] is True, f"{entry['name']} should be available (directory exists)"
        assert entry["installed"] is False, f"{entry['name']} should not be installed (JSON is corrupt)"


async def test_handle_list_tools_filters_by_user_id_for_defense_in_depth(
    user_test_project,
    other_test_project,
    other_test_user,
    active_user,
):
    """Test that handle_list_tools filters by BOTH folder_id AND user_id for defense-in-depth.

    This test verifies the query-level ownership validation in handle_list_tools() when
    project_id is provided. While the endpoint-level authentication (verify_project_auth_conditional)
    already ensures the user owns the project, the database query should ALSO filter by user_id
    for consistency with other MCP handlers (handle_list_resources, handle_read_resource).

    GIVEN: Two projects owned by different users, each with flows
    WHEN:  handle_list_tools is called with a project_id and a specific user context
    THEN:  Only flows from that project AND owned by that user are returned
    """
    from langflow.api.v1.mcp_utils import current_user_ctx, handle_list_tools

    # Create flows for both users in their respective projects
    user_flow_id = uuid4()
    other_user_flow_id = uuid4()

    async with session_scope() as session:
        # Create flow for active_user in user_test_project
        # Include minimal valid data structure to pass json_schema_from_flow validation
        user_flow = Flow(
            id=user_flow_id,
            name="User Flow",
            description="Flow owned by active user",
            data={"nodes": [], "edges": []},  # Minimal valid flow structure
            mcp_enabled=True,
            action_name="user_action",
            action_description="User action",
            folder_id=user_test_project.id,
            user_id=active_user.id,
            is_component=False,
        )
        session.add(user_flow)

        # Create flow for other_test_user in other_test_project
        other_user_flow = Flow(
            id=other_user_flow_id,
            name="Other User Flow",
            description="Flow owned by other user",
            data={"nodes": [], "edges": []},  # Minimal valid flow structure
            mcp_enabled=True,
            action_name="other_action",
            action_description="Other action",
            folder_id=other_test_project.id,
            user_id=other_test_user.id,
            is_component=False,
        )
        session.add(other_user_flow)
        await session.commit()

    try:
        # Test 1: Active user queries their own project - should see their flow
        token = current_user_ctx.set(active_user)
        try:
            tools = await handle_list_tools(project_id=user_test_project.id, mcp_enabled_only=True)
            assert len(tools) == 1, "Active user should see exactly 1 tool in their project"
            assert tools[0].name == "user_action", "Should see the user's own flow"
        finally:
            current_user_ctx.reset(token)

        # Test 2: Other user queries their own project - should see their flow
        token = current_user_ctx.set(other_test_user)
        try:
            tools = await handle_list_tools(project_id=other_test_project.id, mcp_enabled_only=True)
            assert len(tools) == 1, "Other user should see exactly 1 tool in their project"
            assert tools[0].name == "other_action", "Should see the other user's flow"
        finally:
            current_user_ctx.reset(token)

        # Test 3: Defense-in-depth verification - Active user context with other user's project_id
        # This simulates a hypothetical scenario where endpoint auth is bypassed (shouldn't happen,
        # but the query-level filter should still protect against it)
        token = current_user_ctx.set(active_user)
        try:
            tools = await handle_list_tools(project_id=other_test_project.id, mcp_enabled_only=True)
            assert len(tools) == 0, (
                "Active user should see NO tools when querying other user's project_id. "
                "The query-level user_id filter provides defense-in-depth protection."
            )
        finally:
            current_user_ctx.reset(token)

        # Test 4: Verify the same defense-in-depth for the other user
        token = current_user_ctx.set(other_test_user)
        try:
            tools = await handle_list_tools(project_id=user_test_project.id, mcp_enabled_only=True)
            assert len(tools) == 0, (
                "Other user should see NO tools when querying active user's project_id. "
                "The query-level user_id filter provides defense-in-depth protection."
            )
        finally:
            current_user_ctx.reset(token)

    finally:
        # Cleanup
        async with session_scope() as session:
            user_flow = await session.get(Flow, user_flow_id)
            if user_flow:
                await session.delete(user_flow)
            other_user_flow = await session.get(Flow, other_user_flow_id)
            if other_user_flow:
                await session.delete(other_user_flow)
            await session.commit()


@pytest.mark.usefixtures("active_user")
async def test_v2_mcp_servers_unlocked_allows_non_superuser_add_patch_delete(
    client: AsyncClient,
    logged_in_headers,
    monkeypatch,
):
    """When is_mcp_servers_locked returns False the gate must not block normal users."""
    monkeypatch.setattr("langflow.api.v2.mcp.is_mcp_servers_locked", lambda _settings: False)

    server_name = f"lf-unlock-test-{uuid4().hex[:8]}"
    server_config = {
        "command": "uvx",
        "args": ["mcp-proxy", "--transport", "sse", "https://langflow.local/sse"],
    }

    response = await client.post(f"/api/v2/mcp/servers/{server_name}", json=server_config, headers=logged_in_headers)
    assert response.status_code == status.HTTP_200_OK

    response = await client.patch(
        f"/api/v2/mcp/servers/{server_name}",
        json={"description": "updated"},
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_200_OK

    response = await client.delete(f"/api/v2/mcp/servers/{server_name}", headers=logged_in_headers)
    assert response.status_code == status.HTTP_200_OK
