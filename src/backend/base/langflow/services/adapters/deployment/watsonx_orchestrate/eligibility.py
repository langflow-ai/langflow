"""Flow-shape eligibility checks for Watsonx Orchestrate Langflow tools."""

from __future__ import annotations

from typing import Any

CHAT_INPUT_TYPE = "ChatInput"
CHAT_OUTPUT_TYPE = "ChatOutput"


def get_wxo_flow_eligibility_error(flow_data: Any) -> str | None:
    """Return an actionable error when a flow cannot become a wxO Langflow tool."""
    nodes = flow_data.get("nodes", []) if isinstance(flow_data, dict) else []
    nodes = nodes if isinstance(nodes, list) else []

    chat_input_count = sum(
        1
        for node in nodes
        if isinstance(node, dict) and isinstance(node.get("data"), dict) and node["data"].get("type") == CHAT_INPUT_TYPE
    )
    chat_output_count = sum(
        1
        for node in nodes
        if isinstance(node, dict)
        and isinstance(node.get("data"), dict)
        and node["data"].get("type") == CHAT_OUTPUT_TYPE
    )

    if chat_input_count == 0:
        return "Add one Chat Input ('ChatInput') node; Watsonx Orchestrate requires exactly one."
    if chat_input_count > 1:
        return "Remove extra Chat Input ('ChatInput') nodes; Watsonx Orchestrate requires exactly one."
    if chat_output_count == 0:
        return "Add at least one Chat Output ('ChatOutput') node for Watsonx Orchestrate."
    return None
