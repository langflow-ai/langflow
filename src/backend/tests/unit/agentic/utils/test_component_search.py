"""Tests for component search module.

Tests list_all_components, get_all_component_types, get_components_by_type,
get_component_by_name, and get_components_count functions.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langflow.agentic.utils.component_search import (
    get_all_component_types,
    get_component_by_name,
    get_components_by_type,
    get_components_count,
    list_all_components,
)

MODULE = "langflow.agentic.utils.component_search"

MOCK_TYPES_DICT = {
    "llms": {
        "OpenAIModel": {
            "display_name": "OpenAI",
            "description": "OpenAI language model",
            "icon": "openai-icon",
        },
        "AnthropicModel": {
            "display_name": "Anthropic",
            "description": "Anthropic language model",
            "icon": "anthropic-icon",
        },
    },
    "agents": {
        "Agent": {
            "display_name": "Agent",
            "description": "AI agent component",
            "icon": "agent-icon",
        },
    },
}


def _mock_logger():
    """Create a mock async logger."""
    mock = MagicMock()
    mock.aerror = AsyncMock()
    mock.ainfo = AsyncMock()
    mock.awarning = AsyncMock()
    return mock


@pytest.fixture
def _mock_deps():
    """Mock external dependencies for component search functions."""
    mock_settings = MagicMock()
    with (
        patch(f"{MODULE}.get_and_cache_all_types_dict", new_callable=AsyncMock, return_value=MOCK_TYPES_DICT),
        patch(f"{MODULE}.logger", _mock_logger()),
    ):
        yield mock_settings


class TestListAllComponents:
    """Tests for list_all_components."""

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("_mock_deps")
    async def test_should_return_all_components(self):
        """Should return all components from all types."""
        results = await list_all_components(settings_service=MagicMock())
        assert len(results) == 3
        names = {r["name"] for r in results}
        assert names == {"OpenAIModel", "AnthropicModel", "Agent"}

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("_mock_deps")
    async def test_should_filter_by_query(self):
        """Should filter components by name/display_name/description (case-insensitive)."""
        results = await list_all_components(query="openai", settings_service=MagicMock())
        assert len(results) == 1
        assert results[0]["name"] == "OpenAIModel"

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("_mock_deps")
    async def test_should_filter_by_type(self):
        """Should return only components of the specified type."""
        results = await list_all_components(component_type="agents", settings_service=MagicMock())
        assert len(results) == 1
        assert results[0]["name"] == "Agent"
        assert results[0]["type"] == "agents"

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("_mock_deps")
    async def test_should_select_specific_fields(self):
        """Should return only the requested fields."""
        results = await list_all_components(
            fields=["display_name"],
            settings_service=MagicMock(),
        )
        for r in results:
            assert "name" in r
            assert "type" in r
            assert "display_name" in r
            assert "icon" not in r

    @pytest.mark.asyncio
    async def test_should_return_empty_on_error(self):
        """Should return empty list when an exception occurs."""
        mock_cache = AsyncMock(side_effect=RuntimeError("fail"))
        with patch(f"{MODULE}.get_and_cache_all_types_dict", mock_cache), patch(f"{MODULE}.logger", _mock_logger()):
            results = await list_all_components(settings_service=MagicMock())
            assert results == []

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("_mock_deps")
    async def test_should_filter_by_description(self):
        """Should match query against description field."""
        results = await list_all_components(query="AI agent", settings_service=MagicMock())
        assert len(results) == 1
        assert results[0]["name"] == "Agent"


class TestGetAllComponentTypes:
    """Tests for get_all_component_types."""

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("_mock_deps")
    async def test_should_return_sorted_keys(self):
        """Should return sorted list of component type names."""
        result = await get_all_component_types(settings_service=MagicMock())
        assert result == ["agents", "llms"]

    @pytest.mark.asyncio
    async def test_should_return_empty_on_error(self):
        """Should return empty list on error."""
        mock_cache = AsyncMock(side_effect=RuntimeError("fail"))
        with patch(f"{MODULE}.get_and_cache_all_types_dict", mock_cache), patch(f"{MODULE}.logger", _mock_logger()):
            result = await get_all_component_types(settings_service=MagicMock())
            assert result == []


class TestGetComponentsByType:
    """Tests for get_components_by_type."""

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("_mock_deps")
    async def test_should_delegate_to_list_all(self):
        """Should return components of the specified type."""
        results = await get_components_by_type("llms", settings_service=MagicMock())
        assert len(results) == 2
        assert all(r["type"] == "llms" for r in results)


class TestGetComponentByName:
    """Tests for get_component_by_name."""

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("_mock_deps")
    async def test_should_find_component(self):
        """Should find a component by exact name."""
        result = await get_component_by_name("OpenAIModel", settings_service=MagicMock())
        assert result is not None
        assert result["name"] == "OpenAIModel"
        assert result["type"] == "llms"

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("_mock_deps")
    async def test_should_return_none_when_not_found(self):
        """Should return None for nonexistent component."""
        result = await get_component_by_name("NonExistent", settings_service=MagicMock())
        assert result is None

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("_mock_deps")
    async def test_should_search_specific_type(self):
        """Should search only the specified component type."""
        result = await get_component_by_name("Agent", component_type="agents", settings_service=MagicMock())
        assert result is not None
        assert result["name"] == "Agent"

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("_mock_deps")
    async def test_should_return_none_when_type_mismatch(self):
        """Should return None when component exists but not in specified type."""
        result = await get_component_by_name("Agent", component_type="llms", settings_service=MagicMock())
        assert result is None

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("_mock_deps")
    async def test_should_select_fields(self):
        """Should return only requested fields when fields parameter provided."""
        result = await get_component_by_name(
            "OpenAIModel",
            fields=["display_name"],
            settings_service=MagicMock(),
        )
        assert result is not None
        assert "display_name" in result
        assert "icon" not in result


class TestGetComponentsCount:
    """Tests for get_components_count."""

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("_mock_deps")
    async def test_should_count_all_components(self):
        """Should count total components across all types."""
        result = await get_components_count(settings_service=MagicMock())
        assert result == 3

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("_mock_deps")
    async def test_should_count_by_type(self):
        """Should count components of a specific type."""
        result = await get_components_count(component_type="llms", settings_service=MagicMock())
        assert result == 2

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("_mock_deps")
    async def test_should_return_zero_for_unknown_type(self):
        """Should return 0 for nonexistent type."""
        result = await get_components_count(component_type="nonexistent", settings_service=MagicMock())
        assert result == 0
