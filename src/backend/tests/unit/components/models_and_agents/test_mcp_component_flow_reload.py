"""Unit tests for MCP component flow reload behavior.

Validates that tool selection persists when navigating away and back to a flow:
- Cold cache (initial load) must NOT be treated as a server change
- Saved tool options and value must be preserved on initial load
- UUID override must only happen on genuine server changes
"""

from copy import deepcopy
from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest
from langchain_core.tools import StructuredTool
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
    def skipped_outputs(self):
        return {
            "component_as_tool": "needs a database user and starts the MCP server in default_kwargs",
            "response": "calls a tool on the MCP server in default_kwargs",
        }

    @pytest.fixture
    def default_kwargs(self):
        return {
            "mcp_server": {
                "name": "test_server",
                "config": {"command": "uvx", "args": ["test-mcp-server"]},
            },
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
        # The backend now attempts to fetch tools immediately; since "new_server"
        # doesn't exist in the database, it will fail with an error placeholder.
        assert updated_config["tool"]["options"] == []
        assert updated_config["tool"]["placeholder"] in (
            "Error on MCP Server",
            "Timeout on MCP server",
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize("is_refresh", [False, True])
    @pytest.mark.parametrize("last_selected_server", ["", "test_server"])
    async def test_same_server_refresh_preserves_selected_tool_inputs(
        self, component_class, default_kwargs, saved_flow_build_config, is_refresh, last_selected_server
    ):
        """Keep saved argument values and presentation when refreshing the same selected tool."""
        component = await self.component_setup(component_class, default_kwargs)
        safe_cache_set(component._shared_component_cache, "last_selected_server", last_selected_server)
        config = deepcopy(saved_flow_build_config)
        config["is_refresh"] = is_refresh
        config["name"] = {
            "name": "name",
            "type": "str",
            "value": "saved_name",
            "show": False,
            "advanced": True,
            "load_from_db": True,
        }
        config["times"] = {
            "name": "times",
            "type": "int",
            "value": 0,
            "show": True,
            "advanced": False,
            "load_from_db": False,
        }
        saved_fields = deepcopy({name: config[name] for name in ("name", "times")})

        async def saved_tool(name: str, times: int = 1) -> str:
            return name * times

        tool = StructuredTool.from_function(coroutine=saved_tool, description="Local schema fixture")
        with patch.object(component, "update_tool_list", new=AsyncMock(return_value=([tool], {"name": "test_server"}))):
            updated = await component.update_build_config(config, {"name": "test_server"}, "mcp_server")

        assert updated["tool"]["value"] == "saved_tool"
        for name, previous in saved_fields.items():
            for key in ("value", "show", "advanced", "load_from_db"):
                assert updated[name][key] == previous[key]

    @pytest.mark.asyncio
    @pytest.mark.parametrize("last_selected_server", ["", "test_server"])
    async def test_server_change_drops_previous_tool_inputs(
        self, component_class, default_kwargs, saved_flow_build_config, last_selected_server
    ):
        component = await self.component_setup(component_class, default_kwargs)
        safe_cache_set(component._shared_component_cache, "last_selected_server", last_selected_server)
        config = deepcopy(saved_flow_build_config)
        config["name"] = {"name": "name", "type": "str", "value": "previous server"}

        async def saved_tool(name: str) -> str:
            return name

        tool = StructuredTool.from_function(coroutine=saved_tool, description="Local schema fixture")
        with patch.object(component, "update_tool_list", new=AsyncMock(return_value=([tool], {"name": "new_server"}))):
            updated = await component.update_build_config(config, {"name": "new_server"}, "mcp_server")

        assert isinstance(updated["tool"]["value"], UUID)
        assert updated["tool"]["options"] == ["saved_tool"]
        assert "name" not in updated
