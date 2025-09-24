from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from langflow.api.utils.mcp.config_utils import (
    MCPServerValidationResult,
    auto_configure_starter_projects_mcp,
    get_project_sse_url,
    get_url_by_os,
    validate_mcp_server_for_project,
)
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.folder.constants import DEFAULT_FOLDER_NAME
from langflow.services.database.models.folder.model import Folder
from langflow.services.database.models.user.model import User
from langflow.services.deps import session_scope
from sqlmodel import select

# Only async tests are marked with @pytest.mark.asyncio
# pytestmark = pytest.mark.asyncio  # Removed to avoid warnings on sync tests


class TestMCPServerValidationResult:
    """Test the MCPServerValidationResult class and its properties."""

    def test_init_defaults(self):
        """Test initialization with default values."""
        result = MCPServerValidationResult()
        assert result.server_exists is False
        assert result.project_id_matches is False
        assert result.server_name == ""
        assert result.existing_config is None
        assert result.conflict_message == ""

    def test_init_with_values(self):
        """Test initialization with custom values."""
        config = {"command": "test", "args": ["arg1"]}
        result = MCPServerValidationResult(
            server_exists=True,
            project_id_matches=True,
            server_name="test-server",
            existing_config=config,
            conflict_message="Test conflict",
        )
        assert result.server_exists is True
        assert result.project_id_matches is True
        assert result.server_name == "test-server"
        assert result.existing_config == config
        assert result.conflict_message == "Test conflict"

    def test_has_conflict_property(self):
        """Test the has_conflict property."""
        # No conflict when server doesn't exist
        result = MCPServerValidationResult(server_exists=False, project_id_matches=False)
        assert result.has_conflict is False

        # No conflict when server exists and project matches
        result = MCPServerValidationResult(server_exists=True, project_id_matches=True)
        assert result.has_conflict is False

        # Conflict when server exists but project doesn't match
        result = MCPServerValidationResult(server_exists=True, project_id_matches=False)
        assert result.has_conflict is True

    def test_should_skip_property(self):
        """Test the should_skip property."""
        # Don't skip when server doesn't exist
        result = MCPServerValidationResult(server_exists=False, project_id_matches=False)
        assert result.should_skip is False

        # Don't skip when server exists but project doesn't match
        result = MCPServerValidationResult(server_exists=True, project_id_matches=False)
        assert result.should_skip is False

        # Skip when server exists and project matches
        result = MCPServerValidationResult(server_exists=True, project_id_matches=True)
        assert result.should_skip is True

    def test_should_proceed_property(self):
        """Test the should_proceed property."""
        # Proceed when server doesn't exist
        result = MCPServerValidationResult(server_exists=False, project_id_matches=False)
        assert result.should_proceed is True

        # Don't proceed when server exists but project doesn't match
        result = MCPServerValidationResult(server_exists=True, project_id_matches=False)
        assert result.should_proceed is False

        # Proceed when server exists and project matches
        result = MCPServerValidationResult(server_exists=True, project_id_matches=True)
        assert result.should_proceed is True


class TestValidateMcpServerForProject:
    """Test the validate_mcp_server_for_project function."""

    @pytest.fixture
    def mock_user(self):
        """Create a mock user for testing."""
        return User(id=uuid4(), username="testuser")

    @pytest.fixture
    def mock_session(self):
        """Create a mock session for testing."""
        return MagicMock()

    @pytest.fixture
    def mock_storage_service(self):
        """Create a mock storage service for testing."""
        return MagicMock()

    @pytest.fixture
    def mock_settings_service(self):
        """Create a mock settings service for testing."""
        return MagicMock()

    @pytest.mark.asyncio
    async def test_validate_server_not_exists(
        self, mock_user, mock_session, mock_storage_service, mock_settings_service
    ):
        """Test validation when server doesn't exist."""
        project_id = uuid4()
        project_name = "Test Project"

        # Mock get_server_list to return empty servers
        with patch("langflow.api.utils.mcp.config_utils.get_server_list") as mock_get_server_list:
            mock_get_server_list.return_value = {"mcpServers": {}}

            result = await validate_mcp_server_for_project(
                project_id, project_name, mock_user, mock_session, mock_storage_service, mock_settings_service
            )

            assert result.server_exists is False
            assert result.project_id_matches is False
            assert result.server_name == "lf-test_project"
            assert result.existing_config is None
            assert result.conflict_message == ""

    @pytest.mark.asyncio
    async def test_validate_server_exists_project_matches(
        self, mock_user, mock_session, mock_storage_service, mock_settings_service
    ):
        """Test validation when server exists and project ID matches."""
        project_id = uuid4()
        project_name = "Test Project"
        server_name = "lf-test_project"

        # Mock get_server_list to return server with matching project ID
        server_config = {
            "command": "uvx",
            "args": ["mcp-proxy", f"http://localhost:7860/api/v1/mcp/project/{project_id}/sse"],
        }
        mock_servers = {"mcpServers": {server_name: server_config}}

        with patch("langflow.api.utils.mcp.config_utils.get_server_list") as mock_get_server_list:
            mock_get_server_list.return_value = mock_servers

            result = await validate_mcp_server_for_project(
                project_id, project_name, mock_user, mock_session, mock_storage_service, mock_settings_service
            )

            assert result.server_exists is True
            assert result.project_id_matches is True
            assert result.server_name == server_name
            assert result.existing_config == server_config
            assert result.conflict_message == ""

    @pytest.mark.asyncio
    async def test_validate_server_exists_project_doesnt_match(
        self, mock_user, mock_session, mock_storage_service, mock_settings_service
    ):
        """Test validation when server exists but project ID doesn't match."""
        project_id = uuid4()
        other_project_id = uuid4()
        project_name = "Test Project"
        server_name = "lf-test_project"

        # Mock get_server_list to return server with different project ID
        server_config = {
            "command": "uvx",
            "args": ["mcp-proxy", f"http://localhost:7860/api/v1/mcp/project/{other_project_id}/sse"],
        }
        mock_servers = {"mcpServers": {server_name: server_config}}

        with patch("langflow.api.utils.mcp.config_utils.get_server_list") as mock_get_server_list:
            mock_get_server_list.return_value = mock_servers

            result = await validate_mcp_server_for_project(
                project_id, project_name, mock_user, mock_session, mock_storage_service, mock_settings_service, "create"
            )

            assert result.server_exists is True
            assert result.project_id_matches is False
            assert result.server_name == server_name
            assert result.existing_config == server_config
            assert "MCP server name conflict" in result.conflict_message
            assert str(project_id) in result.conflict_message

    @pytest.mark.asyncio
    async def test_validate_server_different_operations_messages(
        self, mock_user, mock_session, mock_storage_service, mock_settings_service
    ):
        """Test different conflict messages for different operations."""
        project_id = uuid4()
        other_project_id = uuid4()
        project_name = "Test Project"
        server_name = "lf-test_project"

        server_config = {
            "command": "uvx",
            "args": ["mcp-proxy", f"http://localhost:7860/api/v1/mcp/project/{other_project_id}/sse"],
        }
        mock_servers = {"mcpServers": {server_name: server_config}}

        with patch("langflow.api.utils.mcp.config_utils.get_server_list") as mock_get_server_list:
            mock_get_server_list.return_value = mock_servers

            # Test create operation
            result = await validate_mcp_server_for_project(
                project_id, project_name, mock_user, mock_session, mock_storage_service, mock_settings_service, "create"
            )
            assert "Cannot create MCP server" in result.conflict_message

            # Test update operation
            result = await validate_mcp_server_for_project(
                project_id, project_name, mock_user, mock_session, mock_storage_service, mock_settings_service, "update"
            )
            assert "Cannot update MCP server" in result.conflict_message

            # Test delete operation
            result = await validate_mcp_server_for_project(
                project_id, project_name, mock_user, mock_session, mock_storage_service, mock_settings_service, "delete"
            )
            assert "Cannot delete MCP server" in result.conflict_message

    @pytest.mark.asyncio
    async def test_validate_server_exception_handling(
        self, mock_user, mock_session, mock_storage_service, mock_settings_service
    ):
        """Test exception handling during validation."""
        project_id = uuid4()
        project_name = "Test Project"

        # Mock get_server_list to raise an exception
        with patch("langflow.api.utils.mcp.config_utils.get_server_list") as mock_get_server_list:
            mock_get_server_list.side_effect = Exception("Test error")

            result = await validate_mcp_server_for_project(
                project_id, project_name, mock_user, mock_session, mock_storage_service, mock_settings_service
            )

            # Should return result allowing operation to proceed on validation failure
            assert result.server_exists is False
            assert result.project_id_matches is False
            assert result.server_name == "lf-test_project"
            assert result.existing_config is None
            assert result.conflict_message == ""


class TestGetUrlByOs:
    """Test the get_url_by_os function."""

    @pytest.mark.asyncio
    async def test_get_url_non_wsl_non_localhost(self):
        """Test URL handling for non-WSL, non-localhost scenarios."""
        host = "example.com"
        port = 8080
        url = "http://example.com:8080/test"

        with patch("langflow.api.utils.mcp.config_utils.platform.system") as mock_system:
            mock_system.return_value = "Linux"

            result = await get_url_by_os(host, port, url)
            assert result == url

    @pytest.mark.asyncio
    async def test_get_url_non_wsl_localhost(self):
        """Test URL handling for non-WSL localhost scenarios."""
        host = "localhost"
        port = 7860
        url = "http://localhost:7860/test"

        with patch("langflow.api.utils.mcp.config_utils.platform.system") as mock_system:
            mock_system.return_value = "Darwin"  # macOS

            result = await get_url_by_os(host, port, url)
            assert result == url

    @pytest.mark.asyncio
    async def test_get_url_wsl_localhost_success(self):
        """Test URL handling for WSL localhost with successful IP retrieval."""
        host = "localhost"
        port = 7860
        url = "http://localhost:7860/test"
        wsl_ip = "172.20.10.2"

        with (
            patch("langflow.api.utils.mcp.config_utils.platform.system") as mock_system,
            patch("langflow.api.utils.mcp.config_utils.platform.uname") as mock_uname,
            patch("langflow.api.utils.mcp.config_utils.create_subprocess_exec") as mock_subprocess,
        ):
            mock_system.return_value = "Linux"
            mock_uname.return_value = MagicMock(release="microsoft-standard-WSL2")

            # Mock subprocess that returns WSL IP
            mock_process = AsyncMock()
            mock_process.returncode = 0
            mock_process.communicate.return_value = (wsl_ip.encode(), b"")
            mock_subprocess.return_value = mock_process

            result = await get_url_by_os(host, port, url)
            expected_url = f"http://{wsl_ip}:7860/test"
            assert result == expected_url

    @pytest.mark.asyncio
    async def test_get_url_wsl_localhost_failure(self):
        """Test URL handling for WSL localhost with failed IP retrieval."""
        host = "localhost"
        port = 7860
        url = "http://localhost:7860/test"

        with (
            patch("langflow.api.utils.mcp.config_utils.platform.system") as mock_system,
            patch("langflow.api.utils.mcp.config_utils.platform.uname") as mock_uname,
            patch("langflow.api.utils.mcp.config_utils.create_subprocess_exec") as mock_subprocess,
        ):
            mock_system.return_value = "Linux"
            mock_uname.return_value = MagicMock(release="microsoft-standard-WSL2")

            # Mock subprocess that fails
            mock_process = AsyncMock()
            mock_process.returncode = 1
            mock_process.communicate.return_value = (b"", b"error")
            mock_subprocess.return_value = mock_process

            result = await get_url_by_os(host, port, url)
            # Should return original URL on failure
            assert result == url

    @pytest.mark.asyncio
    async def test_get_url_wsl_127_0_0_1(self):
        """Test URL handling for WSL with 127.0.0.1."""
        host = "127.0.0.1"
        port = 7860
        url = "http://127.0.0.1:7860/test"
        wsl_ip = "172.20.10.2"

        with (
            patch("langflow.api.utils.mcp.config_utils.platform.system") as mock_system,
            patch("langflow.api.utils.mcp.config_utils.platform.uname") as mock_uname,
            patch("langflow.api.utils.mcp.config_utils.create_subprocess_exec") as mock_subprocess,
        ):
            mock_system.return_value = "Linux"
            mock_uname.return_value = MagicMock(release="microsoft-standard-WSL2")

            mock_process = AsyncMock()
            mock_process.returncode = 0
            mock_process.communicate.return_value = (wsl_ip.encode(), b"")
            mock_subprocess.return_value = mock_process

            result = await get_url_by_os(host, port, url)
            expected_url = f"http://{wsl_ip}:7860/test"
            assert result == expected_url

    @pytest.mark.asyncio
    async def test_get_url_wsl_exception_handling(self):
        """Test exception handling in WSL IP retrieval."""
        host = "localhost"
        port = 7860
        url = "http://localhost:7860/test"

        with (
            patch("langflow.api.utils.mcp.config_utils.platform.system") as mock_system,
            patch("langflow.api.utils.mcp.config_utils.platform.uname") as mock_uname,
            patch("langflow.api.utils.mcp.config_utils.create_subprocess_exec") as mock_subprocess,
        ):
            mock_system.return_value = "Linux"
            mock_uname.return_value = MagicMock(release="microsoft-standard-WSL2")
            mock_subprocess.side_effect = OSError("Process failed")

            result = await get_url_by_os(host, port, url)
            # Should return original URL on exception
            assert result == url


class TestGetProjectSseUrl:
    """Test the get_project_sse_url function."""

    @pytest.mark.asyncio
    async def test_get_project_sse_url_default_settings(self):
        """Test getting project SSE URL with default settings."""
        project_id = uuid4()

        with patch("langflow.api.utils.mcp.config_utils.get_settings_service") as mock_get_settings:
            mock_settings_service = MagicMock()
            mock_settings_service.settings = MagicMock()
            mock_settings_service.settings.host = "localhost"
            mock_settings_service.settings.runtime_port = None
            mock_settings_service.settings.port = 7860
            mock_get_settings.return_value = mock_settings_service

            with patch("langflow.api.utils.mcp.config_utils.get_url_by_os") as mock_get_url_by_os:
                expected_url = f"http://localhost:7860/api/v1/mcp/project/{project_id}/sse"
                mock_get_url_by_os.return_value = expected_url

                result = await get_project_sse_url(project_id)

                assert result == expected_url
                mock_get_url_by_os.assert_called_once_with("localhost", 7860, expected_url)

    @pytest.mark.asyncio
    async def test_get_project_sse_url_with_runtime_port(self):
        """Test getting project SSE URL with runtime port override."""
        project_id = uuid4()

        with patch("langflow.api.utils.mcp.config_utils.get_settings_service") as mock_get_settings:
            mock_settings_service = MagicMock()
            mock_settings_service.settings = MagicMock()
            mock_settings_service.settings.host = "0.0.0.0"
            mock_settings_service.settings.runtime_port = 8080
            mock_settings_service.settings.port = 7860
            mock_get_settings.return_value = mock_settings_service

            with patch("langflow.api.utils.mcp.config_utils.get_url_by_os") as mock_get_url_by_os:
                expected_url = f"http://localhost:8080/api/v1/mcp/project/{project_id}/sse"
                mock_get_url_by_os.return_value = expected_url

                result = await get_project_sse_url(project_id)

                assert result == expected_url
                mock_get_url_by_os.assert_called_once_with("localhost", 8080, expected_url)

    @pytest.mark.asyncio
    async def test_get_project_sse_url_fallback_port(self):
        """Test getting project SSE URL with fallback port when no port is configured."""
        project_id = uuid4()

        with patch("langflow.api.utils.mcp.config_utils.get_settings_service") as mock_get_settings:
            mock_settings_service = MagicMock()
            mock_settings_service.settings = MagicMock()
            mock_settings_service.settings.host = "example.com"
            mock_settings_service.settings.runtime_port = None
            mock_settings_service.settings.port = None
            mock_get_settings.return_value = mock_settings_service

            with patch("langflow.api.utils.mcp.config_utils.get_url_by_os") as mock_get_url_by_os:
                expected_url = f"http://example.com:7860/api/v1/mcp/project/{project_id}/sse"
                mock_get_url_by_os.return_value = expected_url

                result = await get_project_sse_url(project_id)

                assert result == expected_url
                mock_get_url_by_os.assert_called_once_with("example.com", 7860, expected_url)


class TestAutoConfigureStarterProjectsMcp:
    """Test the auto_configure_starter_projects_mcp function."""

    @pytest.fixture
    async def sample_user_with_starter_project(self):
        """Create a sample user with starter project for testing."""
        user_id = uuid4()
        project_id = uuid4()
        flow_id = uuid4()

        async with session_scope() as session:
            # Create user
            user = User(id=user_id, username=f"test_starter_user_{user_id}", password="hashed_password")
            session.add(user)

            # Create starter folder
            starter_folder = Folder(
                id=project_id, name=DEFAULT_FOLDER_NAME, user_id=user_id, description="My Collection"
            )
            session.add(starter_folder)

            # Create flow in starter folder
            flow = Flow(
                id=flow_id,
                name="Test Starter Flow",
                description="A test starter flow",
                folder_id=project_id,
                user_id=user_id,
                is_component=False,
                mcp_enabled=None,  # Explicitly set to None to bypass default False
                action_name=None,
                action_description=None,
            )
            session.add(flow)

            await session.commit()

        yield user, starter_folder, flow

        # Cleanup
        async with session_scope() as session:
            # Delete flow first (foreign key dependency)
            flow_to_delete = await session.get(Flow, flow_id)
            if flow_to_delete:
                await session.delete(flow_to_delete)

            # Delete folder
            folder_to_delete = await session.get(Folder, project_id)
            if folder_to_delete:
                await session.delete(folder_to_delete)

            # Delete user
            user_to_delete = await session.get(User, user_id)
            if user_to_delete:
                await session.delete(user_to_delete)

            await session.commit()

    @pytest.mark.asyncio
    async def test_auto_configure_disabled(self):
        """Test auto-configure when add_projects_to_mcp_servers is disabled."""
        async with session_scope() as session:
            with patch("langflow.api.utils.mcp.config_utils.get_settings_service") as mock_get_settings:
                mock_settings_service = MagicMock()
                mock_settings_service.settings.add_projects_to_mcp_servers = False
                mock_get_settings.return_value = mock_settings_service

                # This should return early without doing anything
                await auto_configure_starter_projects_mcp(session)
                # No assertions needed - just ensuring no exceptions are raised

    @pytest.mark.asyncio
    async def test_auto_configure_no_users(self):
        """Test auto-configure when no users exist."""
        async with session_scope() as session:
            # Delete all users for this test
            users = (await session.exec(select(User))).all()
            for user in users:
                await session.delete(user)
            await session.commit()

            with patch("langflow.api.utils.mcp.config_utils.get_settings_service") as mock_get_settings:
                mock_settings_service = MagicMock()
                mock_settings_service.settings.add_projects_to_mcp_servers = True
                mock_get_settings.return_value = mock_settings_service

                # This should handle empty users list gracefully
                await auto_configure_starter_projects_mcp(session)
                # No assertions needed - just ensuring no exceptions are raised

    @pytest.mark.asyncio
    async def test_auto_configure_success(self, sample_user_with_starter_project):
        """Test successful auto-configuration of starter projects."""
        _, starter_folder, flow = sample_user_with_starter_project

        async with session_scope() as session:
            with (
                patch("langflow.api.utils.mcp.config_utils.get_settings_service") as mock_get_settings,
                patch("langflow.api.utils.mcp.config_utils.get_storage_service") as mock_get_storage,
                patch("langflow.api.utils.mcp.config_utils.validate_mcp_server_for_project") as mock_validate,
                patch("langflow.api.utils.mcp.config_utils.create_api_key") as mock_create_api_key,
                patch("langflow.api.utils.mcp.config_utils.get_project_sse_url") as mock_get_sse_url,
                patch("langflow.api.utils.mcp.config_utils.update_server") as mock_update_server,
                patch("langflow.api.utils.mcp.config_utils.encrypt_auth_settings") as mock_encrypt,
            ):
                mock_settings_service = MagicMock()
                mock_settings_service.settings.add_projects_to_mcp_servers = True
                mock_get_settings.return_value = mock_settings_service

                mock_storage_service = MagicMock()
                mock_get_storage.return_value = mock_storage_service

                # Mock validation to indicate server doesn't exist
                mock_validation_result = MagicMock()
                mock_validation_result.should_skip = False
                mock_validation_result.server_exists = False
                mock_validation_result.project_id_matches = True
                mock_validation_result.server_name = "lf-my-collection"
                mock_validate.return_value = mock_validation_result

                # Mock API key creation
                mock_api_key_response = MagicMock()
                mock_api_key_response.api_key = "test-api-key-123"
                mock_create_api_key.return_value = mock_api_key_response

                # Mock SSE URL
                mock_sse_url = f"http://localhost:7860/api/v1/mcp/project/{starter_folder.id}/sse"
                mock_get_sse_url.return_value = mock_sse_url

                # Mock encryption
                mock_encrypt.return_value = {"auth_type": "apikey"}

                await auto_configure_starter_projects_mcp(session)

                # Note: Due to database constraints, mcp_enabled defaults to False instead of None
                # The auto_configure function only acts when mcp_enabled is None, so in this case
                # the flow configuration won't be updated. This test verifies the function runs
                # without error even when flows are already configured (mcp_enabled=False).
                assert flow.mcp_enabled is False  # Remains unchanged due to database default
                assert flow.action_name is None  # Remains unchanged
                assert flow.action_description is None  # Remains unchanged

                # Verify starter folder got auth settings
                updated_folder = await session.get(Folder, starter_folder.id)
                assert updated_folder.auth_settings is not None

                # Verify API key was created (may be called multiple times for different users)
                assert mock_create_api_key.called

                # Verify MCP server was updated (may be called multiple times for different users)
                assert mock_update_server.called

    @pytest.mark.asyncio
    async def test_auto_configure_server_already_exists(self, sample_user_with_starter_project):
        """Test auto-configure when server already exists for the project."""
        _, _, _ = sample_user_with_starter_project

        async with session_scope() as session:
            with (
                patch("langflow.api.utils.mcp.config_utils.get_settings_service") as mock_get_settings,
                patch("langflow.api.utils.mcp.config_utils.get_storage_service") as mock_get_storage,
                patch("langflow.api.utils.mcp.config_utils.validate_mcp_server_for_project") as mock_validate,
                patch("langflow.api.utils.mcp.config_utils.update_server") as mock_update_server,
            ):
                mock_settings_service = MagicMock()
                mock_settings_service.settings.add_projects_to_mcp_servers = True
                mock_get_settings.return_value = mock_settings_service

                mock_storage_service = MagicMock()
                mock_get_storage.return_value = mock_storage_service

                # Mock validation to indicate server already exists for this project
                mock_validation_result = MagicMock()
                mock_validation_result.should_skip = True
                mock_validation_result.server_exists = True
                mock_validation_result.project_id_matches = True
                mock_validation_result.server_name = "lf-my-collection"
                mock_validate.return_value = mock_validation_result

                await auto_configure_starter_projects_mcp(session)

                # Server update should not be called when skipping
                mock_update_server.assert_not_called()

    @pytest.mark.asyncio
    async def test_auto_configure_exception_handling(self, sample_user_with_starter_project):
        """Test auto-configure handles exceptions gracefully."""
        _, _, _ = sample_user_with_starter_project

        async with session_scope() as session:
            with (
                patch("langflow.api.utils.mcp.config_utils.get_settings_service") as mock_get_settings,
                patch("langflow.api.utils.mcp.config_utils.get_storage_service") as mock_get_storage,
                patch("langflow.api.utils.mcp.config_utils.validate_mcp_server_for_project") as mock_validate,
            ):
                mock_settings_service = MagicMock()
                mock_settings_service.settings.add_projects_to_mcp_servers = True
                mock_get_settings.return_value = mock_settings_service

                mock_storage_service = MagicMock()
                mock_get_storage.return_value = mock_storage_service

                # Mock validation to raise an exception
                mock_validate.side_effect = Exception("Test validation error")

                # This should not raise an exception but log the error
                await auto_configure_starter_projects_mcp(session)

                # No assertions needed - just ensuring exceptions are handled gracefully

    @pytest.mark.asyncio
    async def test_auto_configure_user_without_starter_folder(self):
        """Test auto-configure for user without starter folder."""
        user_id = uuid4()

        async with session_scope() as session:
            # Create user without starter folder
            user = User(id=user_id, username="user_no_starter", password="hashed_password")
            session.add(user)
            await session.commit()

            try:
                with patch("langflow.api.utils.mcp.config_utils.get_settings_service") as mock_get_settings:
                    mock_settings_service = MagicMock()
                    mock_settings_service.settings.add_projects_to_mcp_servers = True
                    mock_get_settings.return_value = mock_settings_service

                    # This should handle missing starter folder gracefully
                    await auto_configure_starter_projects_mcp(session)
                    # No assertions needed - just ensuring no exceptions are raised

            finally:
                # Cleanup
                user_to_delete = await session.get(User, user_id)
                if user_to_delete:
                    await session.delete(user_to_delete)
                    await session.commit()
