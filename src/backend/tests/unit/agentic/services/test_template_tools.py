"""ListTemplates / UseTemplate MCP tools — the agent-facing starter-template surface.

They live in lfx.mcp.flow_builder_tools but are exercised here (backend tree)
because they lazily import langflow.agentic.utils.template_search, which the
isolated lfx suite cannot resolve.

The cost contract under test: the template's flow JSON goes through the
``set_flow`` proposal gate (server-side) and NEVER appears in the tool's
return value — the LLM only ever sees a compact summary.
"""

from __future__ import annotations

import json

import pytest
from langflow.agentic.utils.template_search import list_templates as lf_list_templates
from lfx.mcp.flow_builder_tools import (
    ListTemplates,
    UseTemplate,
    drain_flow_events,
    get_working_flow,
    reset_working_flow,
    set_tool_start_listener,
)
from lfx.mcp.tool_cache import reset_tool_cache


@pytest.fixture(autouse=True)
def _clean_tool_state():
    reset_working_flow()
    reset_tool_cache()
    yield
    set_tool_start_listener(None)
    reset_working_flow()
    reset_tool_cache()


def _any_real_template_name() -> str:
    names = sorted(t["name"] for t in lf_list_templates(fields=["name"]) if t.get("name"))
    assert names, "starter_projects must ship at least one template"
    return names[0]


def _capture_tool_starts() -> list[dict]:
    """Record each payload plus the flow_updates queued at emission time."""
    captured: list[dict] = []

    def listener(payload: dict) -> None:
        captured.append({"payload": payload, "pending_flow_updates": drain_flow_events()})

    set_tool_start_listener(listener)
    return captured


class TestListTemplates:
    def test_returns_name_and_one_line_description_only(self):
        result = ListTemplates().list_templates()

        data = result.data
        assert data["count"] > 0
        assert len(data["templates"]) == data["count"]
        for entry in data["templates"]:
            assert set(entry) == {"name", "description"}, f"unexpected fields in {entry}"
            assert entry["name"]
            assert "\n" not in entry["description"], "descriptions must be one line"

    def test_text_lists_every_template_name_for_the_llm(self):
        data = ListTemplates().list_templates().data

        for entry in data["templates"]:
            assert entry["name"] in data["text"]

    def test_is_a_pure_read_with_no_events(self):
        captured = _capture_tool_starts()

        ListTemplates().list_templates()

        assert captured == []
        assert drain_flow_events() == []

    def test_never_returns_template_flow_json(self):
        serialized = json.dumps(ListTemplates().list_templates().data)

        assert '"nodes"' not in serialized
        assert '"edges"' not in serialized


class TestUseTemplate:
    def test_instantiates_through_the_set_flow_proposal_gate(self):
        name = _any_real_template_name()
        comp = UseTemplate()
        comp.set(template_name=name)

        result = comp.use_template()

        assert "error" not in result.data, result.data
        set_flows = [e for e in drain_flow_events() if e["action"] == "set_flow"]
        assert len(set_flows) == 1, "instantiation must be proposed via exactly one set_flow event"
        flow = set_flows[0]["flow"]
        assert flow["name"] == name
        assert flow["data"]["nodes"], "proposed flow must carry the template's components"
        assert result.data["node_count"] == len(flow["data"]["nodes"])

    def test_updates_the_working_flow_in_place(self):
        name = _any_real_template_name()
        comp = UseTemplate()
        comp.set(template_name=name)

        comp.use_template()

        working = get_working_flow()
        assert working is not None
        assert working["name"] == name
        assert working["data"]["nodes"]

    def test_emits_tool_start_before_its_flow_update(self):
        name = _any_real_template_name()
        captured = _capture_tool_starts()
        comp = UseTemplate()
        comp.set(template_name=name)

        comp.use_template()

        assert len(captured) == 1
        assert captured[0]["payload"] == {"tool": "use_template", "template_name": name}
        assert captured[0]["pending_flow_updates"] == []

    def test_matches_template_name_case_insensitively(self):
        name = _any_real_template_name()
        comp = UseTemplate()
        comp.set(template_name=name.upper())

        result = comp.use_template()

        assert "error" not in result.data, result.data
        assert result.data["template"] == name

    def test_return_value_never_contains_the_template_json(self):
        name = _any_real_template_name()
        comp = UseTemplate()
        comp.set(template_name=name)

        result = comp.use_template()

        serialized = json.dumps(result.data)
        assert '"nodes"' not in serialized
        assert '"edges"' not in serialized
        assert '"viewport"' not in serialized
        working = get_working_flow()
        first_node = working["data"]["nodes"][0]
        first_id = (first_node.get("data") or {}).get("id") or first_node.get("id")
        assert first_id not in serialized, "component ids belong to the proposal, not the LLM summary"
        max_compact_summary_chars = 2000
        assert len(serialized) < max_compact_summary_chars, "summary must stay compact (token cost)"

    def test_summary_reports_node_types(self):
        name = _any_real_template_name()
        comp = UseTemplate()
        comp.set(template_name=name)

        result = comp.use_template()

        assert result.data["node_types"], "summary must name the component types"
        for node_type in result.data["node_types"]:
            assert node_type in result.data["text"]

    def test_unknown_template_name_returns_clear_error_and_no_proposal(self):
        comp = UseTemplate()
        comp.set(template_name="No Such Template Xyz")

        result = comp.use_template()

        assert "error" in result.data
        assert "No Such Template Xyz" in result.data["error"]
        assert _any_real_template_name() in result.data["error"], "error must list the available names"
        assert [e for e in drain_flow_events() if e["action"] == "set_flow"] == []
        assert get_working_flow() is None or not get_working_flow()["data"]["nodes"]

    def test_empty_template_name_returns_error(self):
        comp = UseTemplate()
        comp.set(template_name="   ")

        result = comp.use_template()

        assert "error" in result.data
        assert "list_templates" in result.data["error"]


class TestUseTemplateLoadCost:
    def test_repeated_calls_load_the_starter_jsons_once_per_request(self, monkeypatch):
        # use_template re-walked every starter JSON on each call; the load is a
        # pure read, so it must memoize per request like list_templates.
        import lfx.mcp.flow_builder_tools.template_tools as module

        real_loader = module._load_starter_templates
        calls: list[list[str]] = []

        def counting_loader(fields: list[str]):
            calls.append(fields)
            return real_loader(fields)

        monkeypatch.setattr(module, "_load_starter_templates", counting_loader)
        name = _any_real_template_name()

        for _ in range(3):
            comp = UseTemplate()
            comp.set(template_name=name)
            assert "error" not in comp.use_template().data

        assert len(calls) == 1, f"expected one starter-projects walk per request, got {len(calls)}"

    def test_cached_template_data_is_not_aliased_into_the_working_flow(self):
        # The working flow is mutated in place by later tools; a cached
        # template must hand out a fresh copy on every instantiation.
        name = _any_real_template_name()
        comp = UseTemplate()
        comp.set(template_name=name)
        first = comp.use_template()
        assert "error" not in first.data

        working = get_working_flow()
        working["data"]["nodes"].clear()

        comp2 = UseTemplate()
        comp2.set(template_name=name)
        second = comp2.use_template()

        assert "error" not in second.data, second.data
        assert second.data["node_count"] == first.data["node_count"]


class TestUseTemplateToolStartLabel:
    def test_english_fallback_label_names_the_template(self):
        from langflow.agentic.helpers.sse import format_tool_start_event

        event = format_tool_start_event({"tool": "use_template", "template_name": "Memory Chatbot"})
        payload = json.loads(event.removeprefix("data: "))

        assert payload["label"] == "Applying template Memory Chatbot"

    def test_missing_template_name_gets_generic_label(self):
        from langflow.agentic.helpers.sse import format_tool_start_event

        event = format_tool_start_event({"tool": "use_template"})
        payload = json.loads(event.removeprefix("data: "))

        assert payload["label"] == "Applying a template"


class TestTemplateToolsInToolkit:
    async def test_toolkit_should_include_template_tools(self):
        from langflow.agentic.flows.flow_builder_assistant import build_toolkit

        tools = await build_toolkit()
        names = {getattr(t, "name", None) for t in tools}

        assert {"list_templates", "use_template"}.issubset(names), (
            f"template tools must be in the toolkit, got: {sorted(n for n in names if n)}"
        )

    def test_prompt_should_document_use_template_with_a_clear_match_guard(self):
        from langflow.agentic.flows.flow_builder_assistant import FLOW_BUILDER_PROMPT

        assert "use_template" in FLOW_BUILDER_PROMPT
        assert "list_templates" in FLOW_BUILDER_PROMPT
        lower = FLOW_BUILDER_PROMPT.lower()
        assert "clearly matches" in lower, "prompt must restrict use_template to clear template matches"
