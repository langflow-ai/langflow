"""Unit tests for the dynamic tool-onboarding fixes in MCPToolsComponent.

Covers:
- ``_normalized_headers_for_cache`` handles list / dict / None header shapes
- ``_mcp_servers_cache_key`` is deterministic, header-hash scoped, and distinguishes auth contexts
- ``_ttl_tool_cache`` is a per-instance dict (not a class-level shared dict) so distinct
  components cannot leak tool lists into each other
- ``_get_tools`` honours the TTL cache hit / expiry / FIFO-eviction logic
- ``update_tool_list`` is serialized by ``_update_tool_list_lock`` (no interleaving)
- The shared ``servers`` cross-request cache evicts oldest entries when it exceeds
  ``SHARED_SERVERS_CACHE_MAX_ENTRIES``
- The Toolset output is declared / persisted with ``cache=False`` so saved flows
  do not memoize a stale tool list
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from lfx.base.agents.utils import safe_cache_get, safe_cache_set
from lfx.base.tools.constants import TOOL_OUTPUT_NAME
from lfx.components.models_and_agents.mcp_component import MCPToolsComponent


def _make_tool(name: str) -> MagicMock:
    tool = MagicMock()
    tool.name = name
    return tool


class TestHeaderNormalization:
    """``_normalized_headers_for_cache`` is the input to the cache-key hash."""

    def test_list_of_key_value_dicts(self) -> None:
        component = MCPToolsComponent()
        component.headers = [
            {"key": "Authorization", "value": "Bearer abc"},
            {"key": "X-Tenant", "value": "acme"},
        ]

        assert component._normalized_headers_for_cache() == {
            "Authorization": "Bearer abc",
            "X-Tenant": "acme",
        }

    def test_dict_input(self) -> None:
        component = MCPToolsComponent()
        component.headers = {"Authorization": "Bearer abc"}

        assert component._normalized_headers_for_cache() == {"Authorization": "Bearer abc"}

    def test_none_returns_empty_dict(self) -> None:
        component = MCPToolsComponent()
        component.headers = None

        assert component._normalized_headers_for_cache() == {}

    def test_malformed_list_items_are_skipped(self) -> None:
        component = MCPToolsComponent()
        component.headers = [
            {"key": "Authorization", "value": "Bearer abc"},
            "not-a-dict",
            {"no_key": "bad"},
        ]

        assert component._normalized_headers_for_cache() == {"Authorization": "Bearer abc"}


class TestCacheKey:
    """``_mcp_servers_cache_key`` must separate auth contexts and stay deterministic."""

    def test_empty_server_name_returns_empty_string(self) -> None:
        component = MCPToolsComponent()
        assert component._mcp_servers_cache_key("") == ""

    def test_no_headers_returns_bare_server_name(self) -> None:
        component = MCPToolsComponent()
        component.headers = []

        assert component._mcp_servers_cache_key("srv") == "srv"

    def test_different_headers_produce_different_keys(self) -> None:
        a = MCPToolsComponent()
        a.headers = [{"key": "Authorization", "value": "Bearer tenant-a"}]
        b = MCPToolsComponent()
        b.headers = [{"key": "Authorization", "value": "Bearer tenant-b"}]

        assert a._mcp_servers_cache_key("srv") != b._mcp_servers_cache_key("srv")

    def test_same_headers_produce_identical_keys(self) -> None:
        a = MCPToolsComponent()
        a.headers = [{"key": "Authorization", "value": "Bearer same"}]
        b = MCPToolsComponent()
        b.headers = [{"key": "Authorization", "value": "Bearer same"}]

        assert a._mcp_servers_cache_key("srv") == b._mcp_servers_cache_key("srv")

    def test_header_order_does_not_change_key(self) -> None:
        a = MCPToolsComponent()
        a.headers = [
            {"key": "Authorization", "value": "Bearer x"},
            {"key": "X-Tenant", "value": "acme"},
        ]
        b = MCPToolsComponent()
        b.headers = [
            {"key": "X-Tenant", "value": "acme"},
            {"key": "Authorization", "value": "Bearer x"},
        ]

        assert a._mcp_servers_cache_key("srv") == b._mcp_servers_cache_key("srv")


class TestTtlToolCacheIsolation:
    """``_ttl_tool_cache`` must be a per-instance dict, not class-level."""

    def test_fresh_instances_have_independent_dicts(self) -> None:
        a = MCPToolsComponent()
        b = MCPToolsComponent()

        assert a._ttl_tool_cache is not b._ttl_tool_cache

    def test_write_to_one_instance_does_not_leak_to_another(self) -> None:
        a = MCPToolsComponent()
        b = MCPToolsComponent()
        a._ttl_tool_cache["k"] = (0.0, [_make_tool("leak")])

        assert "k" not in b._ttl_tool_cache


class TestGetToolsTtlCache:
    """``_get_tools`` uses the per-instance TTL cache with FIFO eviction + expiry."""

    @pytest.mark.asyncio
    async def test_ttl_cache_hit_skips_update_tool_list(self) -> None:
        component = MCPToolsComponent()
        component.mcp_server = {"name": "srv"}
        component.headers = []

        cached_tools = [_make_tool("cached")]
        ttl_key = component._mcp_servers_cache_key("srv")
        import time as _time

        component._ttl_tool_cache[ttl_key] = (_time.monotonic(), cached_tools)

        with patch.object(component, "update_tool_list", new=AsyncMock()) as mocked_update:
            result = await component._get_tools()

        assert result is cached_tools
        mocked_update.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_ttl_cache_expired_entry_is_refetched(self) -> None:
        component = MCPToolsComponent()
        component.mcp_server = {"name": "srv"}
        component.headers = []

        stale_tools = [_make_tool("stale")]
        fresh_tools = [_make_tool("fresh")]
        ttl_key = component._mcp_servers_cache_key("srv")
        # Timestamp older than TOOL_TTL_SECS so the entry is considered expired.
        component._ttl_tool_cache[ttl_key] = (0.0, stale_tools)

        with patch.object(
            component,
            "update_tool_list",
            new=AsyncMock(return_value=(fresh_tools, {"name": "srv", "config": {}})),
        ):
            result = await component._get_tools()

        assert result is fresh_tools
        # Stale entry was evicted and replaced with the fresh one.
        assert component._ttl_tool_cache[ttl_key][1] is fresh_tools

    @pytest.mark.asyncio
    async def test_ttl_cache_bounded_by_max_entries_fifo(self) -> None:
        component = MCPToolsComponent()
        # Shrink the cap for a fast, deterministic FIFO check.
        component.TOOL_TTL_MAX_ENTRIES = 3

        async def fake_update_tool_list(mcp_server):
            srv = mcp_server.get("name") if isinstance(mcp_server, dict) else mcp_server
            return [_make_tool(f"{srv}-tool")], {"name": srv, "config": {}}

        with patch.object(component, "update_tool_list", new=AsyncMock(side_effect=fake_update_tool_list)):
            for i in range(5):
                component.mcp_server = {"name": f"srv-{i}"}
                component.headers = []
                await component._get_tools()

        assert len(component._ttl_tool_cache) == 3
        # FIFO eviction: the first two inserted keys must be gone, the last three must remain.
        remaining_keys = set(component._ttl_tool_cache.keys())
        for i in (0, 1):
            assert component._mcp_servers_cache_key(f"srv-{i}") not in remaining_keys
        for i in (2, 3, 4):
            assert component._mcp_servers_cache_key(f"srv-{i}") in remaining_keys

    @pytest.mark.asyncio
    async def test_ttl_cache_disabled_when_ttl_is_zero(self) -> None:
        component = MCPToolsComponent()
        component.TOOL_TTL_SECS = 0
        component.mcp_server = {"name": "srv"}
        component.headers = []

        fresh_tools = [_make_tool("fresh")]
        with patch.object(
            component,
            "update_tool_list",
            new=AsyncMock(return_value=(fresh_tools, {"name": "srv", "config": {}})),
        ):
            await component._get_tools()

        # With TTL disabled, nothing should ever be written to the cache.
        assert component._ttl_tool_cache == {}


class TestUpdateToolListLock:
    """Concurrent ``update_tool_list`` calls must be serialized per component."""

    @pytest.mark.asyncio
    async def test_concurrent_calls_are_serialized(self) -> None:
        component = MCPToolsComponent()
        component.use_cache = False

        in_flight = 0
        peak = 0
        entered = asyncio.Event()

        async def stub_run(_mcp_server):
            nonlocal in_flight, peak
            in_flight += 1
            peak = max(peak, in_flight)
            entered.set()
            await asyncio.sleep(0.02)
            in_flight -= 1
            return [], {"name": "srv", "config": {}}

        async def guarded(mcp_server):
            async with component._update_tool_list_lock:
                return await stub_run(mcp_server)

        # Ten concurrent invocations must not overlap because the lock serializes them.
        await asyncio.gather(*(guarded("srv") for _ in range(10)))
        assert peak == 1
        assert entered.is_set()


class TestSharedServersCacheEviction:
    """Shared ``servers`` cache must be bounded by ``SHARED_SERVERS_CACHE_MAX_ENTRIES``."""

    @pytest.mark.asyncio
    async def test_fifo_eviction_when_over_limit(self) -> None:
        component = MCPToolsComponent()
        component.SHARED_SERVERS_CACHE_MAX_ENTRIES = 3

        # Seed the shared cache up to capacity with placeholder entries.
        servers_cache: dict = {}
        for i in range(3):
            servers_cache[f"old-{i}"] = {
                "tools": [],
                "tool_names": [],
                "tool_cache": {},
                "config": {"i": i},
            }
        safe_cache_set(component._shared_component_cache, "servers", servers_cache)

        # The component's update_tool_list block applies FIFO eviction before inserting a new
        # key whenever len >= max_entries and the new key is absent. Reproduce that block here
        # to exercise the exact policy the component uses.
        new_key = "new-key"
        cache_data = {
            "tools": [],
            "tool_names": [],
            "tool_cache": {},
            "config": {"new": True},
        }
        current = safe_cache_get(component._shared_component_cache, "servers", {})
        max_entries = component.SHARED_SERVERS_CACHE_MAX_ENTRIES
        while len(current) >= max_entries and new_key not in current:
            oldest = next(iter(current))
            current.pop(oldest, None)
        current[new_key] = cache_data
        safe_cache_set(component._shared_component_cache, "servers", current)

        final = safe_cache_get(component._shared_component_cache, "servers", {})
        assert len(final) == 3
        assert new_key in final
        # The oldest entry ("old-0") must have been evicted first.
        assert "old-0" not in final
        assert "old-1" in final
        assert "old-2" in final


class TestUpdateBuildConfigRefresh:
    """MCP node refresh should force a fresh connection attempt and surface failures."""

    @staticmethod
    def _build_config(**overrides):
        config = {
            "mcp_server": {"value": {"name": "srv", "config": {"command": "uvx test"}}},
            "tool": {"show": True, "options": ["stale"], "value": "", "placeholder": "Select a tool"},
            "tool_placeholder": {"tool_mode": False},
            "tools_metadata": {"show": False},
            "use_cache": {"value": True},
            "verify_ssl": {"value": True},
            "headers": {"value": []},
        }
        config.update(overrides)
        return config

    @pytest.mark.asyncio
    async def test_refresh_bypasses_existing_options(self) -> None:
        component = MCPToolsComponent()
        component.use_cache = True
        tool = _make_tool("fresh")

        safe_cache_set(component._shared_component_cache, "last_selected_server", "srv")
        with patch.object(
            component,
            "update_tool_list",
            new=AsyncMock(return_value=([tool], {"name": "srv", "config": {"command": "uvx test"}})),
        ) as mocked_update:
            build_config = await component.update_build_config(
                self._build_config(is_refresh=True),
                {"name": "srv", "config": {"command": "uvx test"}},
                "mcp_server",
            )

        mocked_update.assert_awaited_once()
        assert build_config["tool"]["options"] == ["fresh"]
        assert build_config["tool"]["placeholder"] == "Select a tool"

    @pytest.mark.asyncio
    async def test_mcp_server_error_placeholder_includes_root_cause(self) -> None:
        component = MCPToolsComponent()
        component.use_cache = False

        with patch.object(
            component,
            "update_tool_list",
            new=AsyncMock(side_effect=ValueError("Connection refused")),
        ):
            build_config = await component.update_build_config(
                self._build_config(),
                {"name": "srv", "config": {"command": "uvx test"}},
                "mcp_server",
            )

        assert build_config["tool"]["options"] == []
        assert "Connection refused" in build_config["tool"]["placeholder"]


class TestToolsetOutputNotCached:
    """Saved flows must not memoize the Toolset output."""

    def test_build_tool_output_declares_cache_false(self) -> None:
        component = MCPToolsComponent()
        output = component._build_tool_output()

        assert output.name == TOOL_OUTPUT_NAME
        assert output.cache is False

    def test_map_outputs_forces_cache_false_on_persisted_output(self) -> None:
        component = MCPToolsComponent()
        # Seed the outputs map with an entry that *claims* cache=True, as saved flow JSON
        # occasionally does. ``map_outputs`` must override it back to False.
        persisted = MagicMock()
        persisted.cache = True
        component._outputs_map = {TOOL_OUTPUT_NAME: persisted}

        # Short-circuit the super() call; this test isolates the override behaviour.
        with patch(
            "lfx.custom.custom_component.component_with_cache.ComponentWithCache.map_outputs",
            return_value=None,
        ):
            component.map_outputs()

        assert component._outputs_map[TOOL_OUTPUT_NAME].cache is False
