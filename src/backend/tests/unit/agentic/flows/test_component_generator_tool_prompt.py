"""Regression guard for the component-generator agent's system prompt.

The component generator (the inner ``LangflowAssistant.json`` Agent that
produces a single ``class MyComponent(Component): ...`` snippet) is the
ONLY place that teaches the LLM how to write tool-friendly components.
If the tool-compatibility section silently drops out, every component
generated for an agent regresses to the production failure observed
2026-05-27: the assistant generates a method like ``output()`` or
``process()``, the agent receives a tool with that uninformative name,
and the LLM never calls it.

These tests assert the SPECIFIC instructions are present so prompt
edits can't quietly undo the guidance. Behavior of the runtime fallback
(``_class_name_to_tool_name`` in ``component_tool.py``) is covered by
its own unit tests; this file only covers the prompt content.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

LANGFLOW_ASSISTANT_JSON = (
    Path(__file__).resolve().parent.parent.parent.parent.parent
    / "base"
    / "langflow"
    / "agentic"
    / "flows"
    / "LangflowAssistant.json"
)
# The COMPONENT GENERATOR agent (the inner one whose prompt embeds the
# Langflow Component API Reference). The PARENT agent has a different id
# and is covered by test_langflow_assistant_prompt.py.
COMPONENT_GENERATOR_AGENT_MARKER = "Langflow Component API Reference"


@pytest.fixture(scope="module")
def generator_prompt() -> str:
    flow = json.loads(LANGFLOW_ASSISTANT_JSON.read_text(encoding="utf-8"))
    for node in flow["data"]["nodes"]:
        node_data = node.get("data", {})
        if node_data.get("type") != "Agent":
            continue
        sp = node_data.get("node", {}).get("template", {}).get("system_prompt", {})
        if not isinstance(sp, dict):
            continue
        val = sp.get("value", "") or ""
        if COMPONENT_GENERATOR_AGENT_MARKER in val:
            return val
    msg = "Component generator agent (the one carrying the API Reference) not found in LangflowAssistant.json"
    raise AssertionError(msg)


class TestAgentToolCompatibilitySection:
    """Prompt covers the three traits that make a generated component agent-callable.

    Meaningful method name, descriptive ``description``, and explicit
    ``tool_mode=True`` on LLM-passed inputs.
    """

    def test_section_is_present(self, generator_prompt: str):
        assert "Agent Tool Compatibility" in generator_prompt, (
            "The 'Agent Tool Compatibility' section must remain in the generator prompt — "
            "removing it regresses the production failure where the agent could not call the "
            "generated tool (method name was 'output'/'process')."
        )

    def test_warns_against_generic_method_names(self, generator_prompt: str):
        # Every generic name we ALSO catch at runtime in
        # _GENERIC_OUTPUT_METHOD_NAMES must be called out in the prompt.
        # If the prompt drops one, the LLM regresses to using it.
        for bad_name in ("output", "process", "build_output", "run", "execute"):
            assert bad_name in generator_prompt, f"Prompt must explicitly call out generic method name {bad_name!r}"

    def test_shows_a_good_method_name_example(self, generator_prompt: str):
        # Concrete examples beat abstract advice for LLMs. The prompt must
        # show at least one action-verb-noun pattern so the LLM has a
        # template to copy.
        assert "get_random_menu_item" in generator_prompt or "fetch_weather" in generator_prompt, (
            "Prompt must include at least one action-verb-noun example tool name; without a "
            "concrete pattern, the LLM regresses to generic names."
        )

    def test_explains_description_is_the_tool_description(self, generator_prompt: str):
        # The component `description` doubles as the LLM-facing tool
        # description. The prompt must spell this out — otherwise the LLM
        # writes a one-liner like "Returns an item." and the agent never
        # knows when to call it.
        prompt_lower = generator_prompt.lower()
        assert "is the tool description" in prompt_lower or "tool description" in prompt_lower, (
            "Prompt must state that the component `description` IS the LLM-facing tool description."
        )

    def test_explains_tool_mode_input_marker(self, generator_prompt: str):
        # `tool_mode=True` on inputs is what restricts the LLM-facing tool
        # schema to the arguments the agent should provide. Without it,
        # ALL component inputs (including API keys) end up in the schema —
        # the LLM gets confused and hallucinates values.
        assert "tool_mode=True" in generator_prompt, "Prompt must mention `tool_mode=True` on inputs"

    def test_includes_a_quick_checklist(self, generator_prompt: str):
        # A bulleted pre-emission checklist is the single most effective
        # nudge for LLMs in our prompt evals — keep it.
        assert "checklist" in generator_prompt.lower(), (
            "Prompt must include a pre-emission checklist so the LLM self-verifies before emitting code."
        )

    def test_forbids_reserved_output_name(self, generator_prompt: str):
        # The production failure that motivated the runtime defensive fix:
        # the LLM declared `Output(name="component_as_tool", ...)`, which
        # collides with the synthetic sentinel and silently drops the
        # tool. The prompt MUST teach the LLM never to use this name.
        assert "component_as_tool" in generator_prompt, (
            "Prompt must explicitly forbid the reserved output name `component_as_tool`."
        )
        assert "reserved" in generator_prompt.lower(), (
            "Prompt must call the name `reserved` so the LLM understands the rule's force."
        )
