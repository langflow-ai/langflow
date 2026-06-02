"""Tests for lfx.mcp.registry."""

from __future__ import annotations

from lfx.mcp.registry import describe_component, load_registry, search_registry


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


class TestDescribeComponentToolMode:
    """Tests for describe_component's component_as_tool detection.

    A component supports tool-mode whenever any INPUT field has
    ``tool_mode=True`` — this matches the canonical heuristic in
    ``Component._handle_tool_mode`` which serves as the runtime authority.
    Regression: previously the registry checked OUTPUTS for ``tool_mode``,
    which silently excluded most tool-capable components (FirecrawlScrapeApi,
    every component that follows the ``MessageTextInput(tool_mode=True)``
    pattern) from the flow builder's tool wiring.
    """

    def test_should_expose_component_as_tool_when_any_input_has_tool_mode(self) -> None:
        # Mirrors FirecrawlScrapeApi: tool_mode=True on an INPUT field, plain output.
        registry = {
            "FirecrawlScrapeApi": {
                "display_name": "Firecrawl Scrape API",
                "description": "Scrapes a URL.",
                "category": "firecrawl",
                "outputs": [{"name": "data", "types": ["Data"]}],
                "template": {
                    "url": {"type": "str", "tool_mode": True, "required": True, "show": True},
                    "api_key": {"type": "SecretStr", "required": True, "show": True},
                },
            }
        }

        result = describe_component(registry, "FirecrawlScrapeApi")

        output_names = [o["name"] for o in result["outputs"]]
        assert "component_as_tool" in output_names, (
            "FirecrawlScrapeApi has tool_mode=True on its url input, so the "
            "flow builder must advertise component_as_tool as a Tool output."
        )

    def test_should_not_expose_component_as_tool_when_no_input_has_tool_mode(self) -> None:
        registry = {
            "PlainComponent": {
                "outputs": [{"name": "data", "types": ["Data"]}],
                "template": {
                    "url": {"type": "str", "required": True, "show": True},
                },
            }
        }

        result = describe_component(registry, "PlainComponent")

        output_names = [o["name"] for o in result["outputs"]]
        assert "component_as_tool" not in output_names

    def test_should_expose_component_as_tool_for_message_text_input_pattern(self) -> None:
        """Recognize MessageTextInput(name=..., tool_mode=True) — the most common pattern.

        The registry must detect this pattern (used across the codebase) and
        advertise the component_as_tool output.
        """
        registry = {
            "WebSearchTool": {
                "outputs": [{"name": "result", "types": ["Message"]}],
                "template": {
                    "query": {
                        "type": "str",
                        "input_types": ["Message"],
                        "tool_mode": True,
                        "show": True,
                    },
                },
            }
        }

        result = describe_component(registry, "WebSearchTool")

        assert any(o["name"] == "component_as_tool" for o in result["outputs"])

    def test_should_still_expose_component_as_tool_when_output_carries_tool_mode_flag(self) -> None:
        """Backward compat: if some component sets tool_mode on an output, keep working."""
        registry = {
            "LegacyTool": {
                "outputs": [{"name": "result", "types": ["Tool"], "tool_mode": True}],
                "template": {},
            }
        }

        result = describe_component(registry, "LegacyTool")

        assert any(o["name"] == "component_as_tool" for o in result["outputs"])

    def test_should_include_input_names_in_component_as_tool_description(self) -> None:
        """Include tool-mode input names in the component_as_tool description.

        The agent uses this description to discover which parameters it can
        pass when invoking the tool.
        """
        registry = {
            "MyTool": {
                "outputs": [{"name": "result", "types": ["Data"]}],
                "template": {
                    "query": {"type": "str", "tool_mode": True, "show": True},
                    "limit": {"type": "int", "tool_mode": True, "show": True},
                    "api_key": {"type": "SecretStr", "show": True},
                },
            }
        }

        result = describe_component(registry, "MyTool")

        tool_output = next(o for o in result["outputs"] if o["name"] == "component_as_tool")
        assert "query" in tool_output["description"]
        assert "limit" in tool_output["description"]


class TestSearchRegistryLegacyFilter:
    """WS-5 / RC-5 — agent discovery must not surface LEGACY components.

    Screenshot 5: a Legacy Calculator was added to a built flow. Legacy stays
    describable by exact name so an explicit request still works.

    Requirement CHANGED (user, 2026-05-18): BETA components ARE allowed in
    search — only Legacy is hidden. The earlier "beta excluded" assertion is
    intentionally inverted below, not deleted, to record the spec change.
    """

    def test_search_excludes_legacy_components_by_default(self) -> None:
        registry = {
            "Calculator": {"template": {}, "legacy": True, "category": "tools"},
            "WebSearch": {"template": {}, "category": "tools"},
        }
        names = {r["type"] for r in search_registry(registry)}
        assert "Calculator" not in names, "Legacy components must not appear in default search results"
        assert "WebSearch" in names

    def test_search_includes_beta_components_by_default(self) -> None:
        # Spec change: beta is usable; the agent SHOULD see beta components.
        registry = {
            "BetaThing": {"template": {}, "beta": True, "category": "tools"},
            "StableThing": {"template": {}, "category": "tools"},
        }
        names = {r["type"] for r in search_registry(registry)}
        assert "BetaThing" in names, "Beta components must be visible in default search"
        assert "StableThing" in names

    def test_search_still_excludes_legacy_even_if_also_beta(self) -> None:
        # A component flagged both legacy AND beta is still hidden (legacy wins).
        registry = {
            "OldBeta": {"template": {}, "legacy": True, "beta": True, "category": "tools"},
        }
        names = {r["type"] for r in search_registry(registry)}
        assert "OldBeta" not in names

    def test_search_includes_legacy_when_explicitly_requested(self) -> None:
        registry = {"Calculator": {"template": {}, "legacy": True, "category": "tools"}}
        names = {r["type"] for r in search_registry(registry, include_legacy=True)}
        assert "Calculator" in names

    def test_search_still_returns_non_legacy_components(self) -> None:
        """Regression: the filter must not drop normal components."""
        registry = {
            "ChatInput": {"template": {}, "category": "inputs"},
            "Agent": {"template": {}, "category": "agents"},
        }
        names = {r["type"] for r in search_registry(registry)}
        assert names == {"ChatInput", "Agent"}

    def test_describe_still_works_for_legacy_and_flags_it(self) -> None:
        """A legacy component stays describable and the result flags it as legacy."""
        registry = {"Calculator": {"template": {}, "legacy": True, "category": "tools"}}
        result = describe_component(registry, "Calculator")
        assert result["type"] == "Calculator"
        assert result.get("legacy") is True
