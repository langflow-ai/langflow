"""Tests for lfx.mcp.registry."""

from __future__ import annotations

from lfx.mcp.registry import load_registry, search_registry


class _StubClient:
    """Minimal async client that returns a preset payload from .get()."""

    def __init__(self, data: dict) -> None:
        self._data = data

    async def get(self, _path: str) -> dict:
        return self._data


class TestLoadRegistry:
    async def test_category_populated_from_response_keys(self) -> None:
        """/all groups components by category; the registry must preserve that category on each component."""
        data = {
            "models": {
                "OpenAIModel": {"template": {}, "display_name": "OpenAI"},
            },
            "inputs": {
                "ChatInput": {"template": {}, "display_name": "Chat Input"},
            },
        }

        registry = await load_registry(_StubClient(data))

        assert registry["OpenAIModel"]["category"] == "models"
        assert registry["ChatInput"]["category"] == "inputs"

    async def test_non_dict_category_groups_are_skipped(self) -> None:
        """Non-dict top-level values (e.g. metadata fields) should be ignored, not crash."""
        data = {
            "models": {"OpenAIModel": {"template": {}}},
            "version": "1.0.0",
        }

        registry = await load_registry(_StubClient(data))

        assert "OpenAIModel" in registry
        assert "version" not in registry


class TestSearchRegistryCategoryFilter:
    async def test_category_filter_returns_matching_components(self) -> None:
        """search_registry(category=...) must return only components from that category."""
        data = {
            "models": {
                "OpenAIModel": {"template": {}},
                "AnthropicModel": {"template": {}},
            },
            "inputs": {
                "ChatInput": {"template": {}},
            },
        }
        registry = await load_registry(_StubClient(data))

        results = search_registry(registry, category="models")

        types = {r["type"] for r in results}
        assert types == {"OpenAIModel", "AnthropicModel"}

    async def test_category_filter_case_insensitive(self) -> None:
        data = {"Models": {"OpenAIModel": {"template": {}}}}
        registry = await load_registry(_StubClient(data))

        results = search_registry(registry, category="models")

        assert {r["type"] for r in results} == {"OpenAIModel"}
