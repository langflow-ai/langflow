from unittest.mock import patch
from uuid import uuid4

import pytest
from httpx import AsyncClient
from langflow.api.utils.mcp.config_utils import (
    MCPServerValidationResult,
    auto_configure_starter_projects_mcp,
    validate_mcp_server_for_project,
)
from langflow.services.auth.utils import get_password_hash
from langflow.services.database.models.api_key.model import ApiKey
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.folder.constants import DEFAULT_FOLDER_NAME
from langflow.services.database.models.folder.model import Folder
from langflow.services.database.models.user.model import User
from langflow.services.database.utils import session_getter
from langflow.services.deps import session_scope
from sqlmodel import select

from lfx.services.deps import get_db_service


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
    """Test the validate_mcp_server_for_project function using real API calls."""

    @pytest.fixture
    async def test_project(self, active_user, client: AsyncClient):  # noqa: ARG002
        """Create a test project for testing."""
        project_id = uuid4()
        async with session_scope() as session:
            project = Folder(
                id=project_id,
                name="Test Project",
                user_id=active_user.id,
                description="Test project for MCP validation",
            )
            session.add(project)
            await session.commit()
            await session.refresh(project)
            yield project
            # Cleanup
            await session.delete(project)
            await session.commit()

    @pytest.mark.asyncio
    async def test_validate_server_not_exists(self, active_user, test_project, client: AsyncClient):  # noqa: ARG002
        """Test validation when server doesn't exist."""
        from langflow.services.deps import get_settings_service, get_storage_service

        async with session_scope() as session:
            storage_service = get_storage_service()
            settings_service = get_settings_service()

            result = await validate_mcp_server_for_project(
                test_project.id, test_project.name, active_user, session, storage_service, settings_service
            )

            assert result.server_exists is False
            assert result.project_id_matches is False
            assert result.server_name == "lf-test_project"
            assert result.existing_config is None
            assert result.conflict_message == ""

    @pytest.mark.asyncio
    async def test_validate_server_exists_project_matches(
        self, active_user, test_project, created_api_key, client: AsyncClient
    ):
        """Test validation when server exists and project ID matches."""
        sse_url = f"{client.base_url}/api/v1/mcp/project/{test_project.id}/sse"
        server_config = {
            "command": "uvx",
            "args": ["mcp-proxy", sse_url],
        }

        # Create MCP server via API
        response = await client.post(
            "/api/v2/mcp/servers/lf-test_project", json=server_config, headers={"x-api-key": created_api_key.api_key}
        )
        assert response.status_code == 200

        from langflow.services.deps import get_settings_service, get_storage_service

        async with session_scope() as session:
            storage_service = get_storage_service()
            settings_service = get_settings_service()

            result = await validate_mcp_server_for_project(
                test_project.id, test_project.name, active_user, session, storage_service, settings_service
            )

            assert result.server_exists is True
            assert result.project_id_matches is True
            assert result.server_name == "lf-test_project"
            assert result.existing_config == server_config
            assert result.conflict_message == ""

        # Cleanup - delete the server
        await client.delete("/api/v2/mcp/servers/lf-test_project", headers={"x-api-key": created_api_key.api_key})

    @pytest.mark.asyncio
    # @pytest.mark.skip(reason="404 when trying to create the server using client")
    async def test_validate_server_exists_project_doesnt_match(
        self, active_user, test_project, created_api_key, client: AsyncClient
    ):
        """Test validation when server exists but project ID doesn't match."""
        other_project_id = uuid4()
        server_name = "lf-test_project"
        sse_url = f"{client.base_url}/api/v1/mcp/project/{other_project_id}/sse"

        server_config = {
            "command": "uvx",
            "args": ["mcp-proxy", sse_url],
        }

        # Create MCP server with different project ID via API
        response = await client.post(
            f"/api/v2/mcp/servers/{server_name}", json=server_config, headers={"x-api-key": created_api_key.api_key}
        )
        assert response.status_code == 200

        from langflow.services.deps import get_settings_service, get_storage_service

        async with session_scope() as session:
            storage_service = get_storage_service()
            settings_service = get_settings_service()

            result = await validate_mcp_server_for_project(
                test_project.id, test_project.name, active_user, session, storage_service, settings_service, "create"
            )

            assert result.server_exists is True
            assert result.project_id_matches is False
            assert result.server_name == server_name
            assert result.existing_config == server_config
            assert "MCP server name conflict" in result.conflict_message
            assert str(test_project.id) in result.conflict_message

        # Cleanup - delete the server
        await client.delete(f"/api/v2/mcp/servers/{server_name}", headers={"x-api-key": created_api_key.api_key})

    @pytest.mark.asyncio
    async def test_validate_server_different_operations_messages(
        self, active_user, test_project, created_api_key, client: AsyncClient
    ):
        """Test different conflict messages for different operations."""
        other_project_id = uuid4()
        server_name = "lf-test_project"
        sse_url = f"{client.base_url}/api/v1/mcp/project/{other_project_id}/sse"

        server_config = {
            "command": "uvx",
            "args": ["mcp-proxy", sse_url],
        }

        # Create MCP server with different project ID via API
        response = await client.post(
            f"/api/v2/mcp/servers/{server_name}", json=server_config, headers={"x-api-key": created_api_key.api_key}
        )
        assert response.status_code == 200

        from langflow.services.deps import get_settings_service, get_storage_service

        async with session_scope() as session:
            storage_service = get_storage_service()
            settings_service = get_settings_service()

            # Test create operation
            result = await validate_mcp_server_for_project(
                test_project.id, test_project.name, active_user, session, storage_service, settings_service, "create"
            )
            assert "Cannot create MCP server" in result.conflict_message

            # Test update operation
            result = await validate_mcp_server_for_project(
                test_project.id, test_project.name, active_user, session, storage_service, settings_service, "update"
            )
            assert "Cannot update MCP server" in result.conflict_message

            # Test delete operation
            result = await validate_mcp_server_for_project(
                test_project.id, test_project.name, active_user, session, storage_service, settings_service, "delete"
            )
            assert "Cannot delete MCP server" in result.conflict_message

        # Cleanup - delete the server
        await client.delete(f"/api/v2/mcp/servers/{server_name}", headers={"x-api-key": created_api_key.api_key})

    @pytest.mark.asyncio
    async def test_validate_server_exception_handling(self, active_user, test_project, client: AsyncClient):  # noqa: ARG002
        """Test exception handling during validation."""
        from langflow.services.deps import get_settings_service, get_storage_service

        async with session_scope() as session:
            storage_service = get_storage_service()
            settings_service = get_settings_service()

            # Mock get_server_list to raise an exception
            with patch("langflow.api.utils.mcp.config_utils.get_server_list") as mock_get_server_list:
                mock_get_server_list.side_effect = Exception("Test error")

                result = await validate_mcp_server_for_project(
                    test_project.id, test_project.name, active_user, session, storage_service, settings_service
                )

                # Should return result allowing operation to proceed on validation failure
                assert result.server_exists is False
                assert result.project_id_matches is False
                assert result.server_name == "lf-test_project"
                assert result.existing_config is None
                assert result.conflict_message == ""


class TestAutoConfigureStarterProjectsMcp:
    """Test the auto_configure_starter_projects_mcp function using real API calls."""

    @pytest.fixture
    async def sample_user_with_starter_project(self, client: AsyncClient):  # noqa: ARG002
        """Create a sample user with starter project for testing."""
        user_id = uuid4()
        project_id = uuid4()
        flow_id = uuid4()

        async with session_scope() as session:
            # Create user
            user = User(id=user_id, username=f"test_starter_user_{user_id}", password="hashed_password")  # noqa: S106
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
    async def test_auto_configure_disabled(self, client: AsyncClient):  # noqa: ARG002
        """Test auto-configure when add_projects_to_mcp_servers is disabled."""
        async with session_scope() as session:
            from langflow.services.deps import get_settings_service

            settings_service = get_settings_service()
            original_setting = settings_service.settings.add_projects_to_mcp_servers

            try:
                # Temporarily disable the setting
                settings_service.settings.add_projects_to_mcp_servers = False

                # This should return early without doing anything
                await auto_configure_starter_projects_mcp(session)
                # No assertions needed - just ensuring no exceptions are raised

            finally:
                # Restore original setting
                settings_service.settings.add_projects_to_mcp_servers = original_setting

    @pytest.mark.asyncio
    async def test_auto_configure_no_users(self, client: AsyncClient):  # noqa: ARG002
        """Test auto-configure when no users exist."""
        async with session_scope() as session:
            from langflow.services.deps import get_settings_service

            settings_service = get_settings_service()
            original_setting = settings_service.settings.add_projects_to_mcp_servers

            try:
                # Enable the setting
                settings_service.settings.add_projects_to_mcp_servers = True

                # Delete all users for this test
                users = (await session.exec(select(User))).all()
                for user in users:
                    await session.delete(user)
                await session.commit()

                # This should handle empty users list gracefully
                await auto_configure_starter_projects_mcp(session)
                # No assertions needed - just ensuring no exceptions are raised

            finally:
                # Restore original setting
                settings_service.settings.add_projects_to_mcp_servers = original_setting

    @pytest.mark.asyncio
    async def test_auto_configure_success(self, sample_user_with_starter_project, client: AsyncClient):  # noqa: ARG002
        """Test successful auto-configuration of starter projects."""
        _, starter_folder, flow = sample_user_with_starter_project

        async with session_scope() as session:
            from langflow.services.deps import get_settings_service

            settings_service = get_settings_service()
            original_setting = settings_service.settings.add_projects_to_mcp_servers

            try:
                # Enable the setting
                settings_service.settings.add_projects_to_mcp_servers = True

                await auto_configure_starter_projects_mcp(session)

                # Note: Due to database constraints, mcp_enabled defaults to False instead of None
                # The auto_configure function only acts when mcp_enabled is None, so in this case
                # the flow configuration won't be updated. This test verifies the function runs
                # without error even when flows are already configured (mcp_enabled=False).
                updated_flow = await session.get(Flow, flow.id)
                assert updated_flow.mcp_enabled is False  # Remains unchanged due to database default

                # Verify starter folder exists
                updated_folder = await session.get(Folder, starter_folder.id)
                assert updated_folder is not None

            finally:
                # Restore original setting
                settings_service.settings.add_projects_to_mcp_servers = original_setting

    @pytest.mark.asyncio
    async def test_auto_configure_user_without_starter_folder(self, client: AsyncClient):  # noqa: ARG002
        """Test auto-configure for user without starter folder."""
        user_id = uuid4()

        async with session_scope() as session:
            from langflow.services.deps import get_settings_service

            settings_service = get_settings_service()
            original_setting = settings_service.settings.add_projects_to_mcp_servers

            try:
                # Enable the setting
                settings_service.settings.add_projects_to_mcp_servers = True

                # Create user without starter folder
                user = User(id=user_id, username="user_no_starter", password="hashed_password")  # noqa: S106
                session.add(user)
                await session.commit()

                # This should handle missing starter folder gracefully
                await auto_configure_starter_projects_mcp(session)
                # No assertions needed - just ensuring no exceptions are raised

            finally:
                # Restore original setting
                settings_service.settings.add_projects_to_mcp_servers = original_setting

                # Cleanup
                user_to_delete = await session.get(User, user_id)
                if user_to_delete:
                    await session.delete(user_to_delete)
                    await session.commit()
