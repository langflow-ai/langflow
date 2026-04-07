"""Unit tests for MCP component flow reload behavior.

Validates that tool selection persists when navigating away and back to a flow:
- Cold cache (initial load) must NOT be treated as a server change
- Saved tool options and value must be preserved on initial load
- UUID override must only happen on genuine server changes
"""

from typing import Any
from uuid import UUID, uuid4

import pytest
from lfx.base.agents.utils import safe_cache_get, safe_cache_set
from lfx.components.models_and_agents.mcp_component import MCPToolsComponent

from tests.base import ComponentTestBaseWithoutClient


class TestMCPComponentFlowReload(ComponentTestBaseWithoutClient):
    """Tests for tool selection persistence across flow navigation."""

    @pytest.fixture
    def component_class(self):
        return MCPToolsComponent

    @pytest.fixture
    def file_names_mapping(self):
        return []

    @pytest.fixture
    def default_kwargs(self):
        return {
            "mcp_server": {"name": "test_server", "config": {"command": "uvx test-mcp-server"}},
            "tool": "saved_tool",
            "use_cache": False,
        }

    @pytest.fixture
    def saved_flow_build_config(self):
        """Simulates build_config from a saved flow with tool already selected."""
        return {
            "mcp_server": {"value": {"name": "test_server"}},
            "tool": {
                "show": True,
                "options": ["saved_tool", "other_tool"],
                "value": "saved_tool",
                "placeholder": "Select a tool",
            },
            "tool_placeholder": {"tool_mode": False},
            "tools_metadata": {"show": False},
        }

    async def component_setup(self, component_class: type[Any], default_kwargs: dict[str, Any]) -> MCPToolsComponent:
        component_instance = await super().component_setup(component_class, default_kwargs)
        component_instance._user_id = str(uuid4())
        return component_instance

    @pytest.mark.asyncio
    async def test_should_preserve_tool_options_when_cache_is_cold(
        self, component_class, default_kwargs, saved_flow_build_config
    ):
        """Cold cache on initial flow load must not clear saved tool options.

        Bug: navigating away and back to a flow clears tool.options because the
        backend treats cold cache (_last_selected_server="") as a server change.
        """
        # Arrange — ensure cold cache (no previous server selection)
        component = await self.component_setup(component_class, default_kwargs)
        safe_cache_set(component._shared_component_cache, "last_selected_server", "")
        build_config = saved_flow_build_config.copy()
        server_value = {"name": "test_server"}

        # Act — simulate initial load (cold cache, no last_selected_server)
        updated_config = await component.update_build_config(build_config, server_value, "mcp_server")

        # Assert — saved options must be preserved
        assert updated_config["tool"]["options"] == ["saved_tool", "other_tool"]
        assert updated_config["tool"]["show"] is True

    @pytest.mark.asyncio
    async def test_should_preserve_tool_value_when_cache_is_cold(
        self, component_class, default_kwargs, saved_flow_build_config
    ):
        """Cold cache on initial flow load must not override saved tool value with UUID."""
        # Arrange — ensure cold cache
        component = await self.component_setup(component_class, default_kwargs)
        safe_cache_set(component._shared_component_cache, "last_selected_server", "")
        build_config = saved_flow_build_config.copy()
        server_value = {"name": "test_server"}

        # Act
        updated_config = await component.update_build_config(build_config, server_value, "mcp_server")

        # Assert — value must remain the saved tool name, not a UUID
        tool_value = updated_config["tool"]["value"]
        assert tool_value == "saved_tool"
        assert not isinstance(tool_value, UUID)

    @pytest.mark.asyncio
    async def test_should_override_tool_value_with_uuid_when_server_genuinely_changes(
        self, component_class, default_kwargs, saved_flow_build_config
    ):
        """When user switches to a different server, tool value must be reset."""
        # Arrange
        component = await self.component_setup(component_class, default_kwargs)
        build_config = saved_flow_build_config.copy()

        # Simulate previous server was set (warm cache)
        safe_cache_set(component._shared_component_cache, "last_selected_server", "old_server")

        new_server_value = {"name": "new_server"}

        # Act
        updated_config = await component.update_build_config(build_config, new_server_value, "mcp_server")

        # Assert — value must be a UUID (forced refresh)
        assert isinstance(updated_config["tool"]["value"], UUID)

    @pytest.mark.asyncio
    async def test_should_set_last_selected_server_in_cache_on_initial_load(
        self, component_class, default_kwargs, saved_flow_build_config
    ):
        """Initial load must populate the cache with the current server name."""
        # Arrange — ensure cold cache
        component = await self.component_setup(component_class, default_kwargs)
        safe_cache_set(component._shared_component_cache, "last_selected_server", "")
        build_config = saved_flow_build_config.copy()
        server_value = {"name": "test_server"}

        # Act
        await component.update_build_config(build_config, server_value, "mcp_server")

        # Assert
        cached_server = safe_cache_get(component._shared_component_cache, "last_selected_server", "")
        assert cached_server == "test_server"

    @pytest.mark.asyncio
    async def test_should_clear_tool_options_when_server_genuinely_changes(
        self, component_class, default_kwargs, saved_flow_build_config
    ):
        """When user switches server, old tool options must be cleared."""
        # Arrange
        component = await self.component_setup(component_class, default_kwargs)
        build_config = saved_flow_build_config.copy()

        # Simulate previous server was set (warm cache)
        safe_cache_set(component._shared_component_cache, "last_selected_server", "old_server")

        new_server_value = {"name": "new_server"}

        # Act
        updated_config = await component.update_build_config(build_config, new_server_value, "mcp_server")

        # Assert — options must be cleared (new server has different tools)
        assert updated_config["tool"]["options"] == []
        assert updated_config["tool"]["placeholder"] == "Loading tools..."
