"""Inject a deterministic probe value into an input-needing flow.

A freshly built flow whose ChatInput is empty produces no output on a
verification run, so the loop can't tell whether it works. This applies
a fixed, harmless probe string to every empty ChatInput — never
overwriting a value the user or agent already set.
"""

from __future__ import annotations

from typing import Any

# Short, neutral, model-safe: enough for an Agent/chat flow to produce a
# response without steering the flow's behavior.
PROBE_INPUT_TEXT = "Hello"

_CHAT_INPUT_TYPE = "ChatInput"
_VALUE_FIELD = "input_value"


def apply_probe_input(flow: dict[str, Any]) -> bool:
    """Fill every empty ChatInput with the probe value.

    Args:
        flow: The working-flow dict (mutated in place).

    Returns:
        True if at least one empty ChatInput was filled, else False.
    """
    nodes = (flow or {}).get("data", {}).get("nodes", []) or []
    applied = False
    for node in nodes:
        if not isinstance(node, dict):
            continue
        node_data = node.get("data") or {}
        if node_data.get("type") != _CHAT_INPUT_TYPE:
            continue
        template = (node_data.get("node") or {}).get("template") or {}
        field = template.get(_VALUE_FIELD)
        if not isinstance(field, dict):
            continue
        if not field.get("value"):
            field["value"] = PROBE_INPUT_TEXT
            applied = True
    return applied
