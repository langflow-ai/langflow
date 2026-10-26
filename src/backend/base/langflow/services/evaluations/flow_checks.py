"""Static checks on a flow before it is evaluated: what blocks a run and what only warns."""

from __future__ import annotations

from typing import Any

from langflow.api.v1.run_validation import flow_requires_hitl
from langflow.services.evaluations.schemas import FlowCheckIssue, FlowCheckReport

EVAL_INPUT_TYPES = frozenset({"ChatInput", "TextInput"})
EVAL_OUTPUT_TYPES = frozenset({"ChatOutput", "TextOutput"})
MEMORY_OUTPUT_TYPE = "Memory"
# Substrings of a component type or name that usually act on the outside world.
SIDE_EFFECT_MARKERS = (
    "email",
    "gmail",
    "slack",
    "discord",
    "telegram",
    "twilio",
    "webhook",
    "apirequest",
    "httprequest",
    "savetofile",
    "composio",
    "mcp",
    "sqlexecutor",
    "sqldatabase",
    "notion",
    "jira",
    "github",
)


def _node_data(node: dict[str, Any]) -> dict[str, Any]:
    return node.get("data") or {}


def _node_type(node: dict[str, Any]) -> str:
    return str(_node_data(node).get("type") or "")


def _node_id(node: dict[str, Any]) -> str:
    return str(_node_data(node).get("id") or node.get("id") or "")


def _display_name(node: dict[str, Any]) -> str:
    inner = _node_data(node).get("node") or {}
    return str(inner.get("display_name") or _node_type(node) or _node_id(node))


def _nodes(flow_data: dict[str, Any]) -> list[dict[str, Any]]:
    return [node for node in flow_data.get("nodes") or [] if isinstance(node, dict) and node.get("type") != "noteNode"]


def _is_type(node: dict[str, Any], types: frozenset[str]) -> bool:
    return _node_type(node) in types or _node_id(node).split("-")[0] in types


def output_vertices(flow_data: dict[str, Any]) -> list[dict[str, str]]:
    return [{"id": _node_id(n), "name": _display_name(n)} for n in _nodes(flow_data) if _is_type(n, EVAL_OUTPUT_TYPES)]


def _has_memory_output(node: dict[str, Any]) -> bool:
    outputs = (_node_data(node).get("node") or {}).get("outputs") or []
    return any(MEMORY_OUTPUT_TYPE in (output.get("types") or []) for output in outputs if isinstance(output, dict))


def _looks_side_effecting(node: dict[str, Any]) -> bool:
    haystack = f"{_node_type(node)} {_display_name(node)}".replace(" ", "").lower()
    return any(marker in haystack for marker in SIDE_EFFECT_MARKERS)


def _blocking(flow_data: dict[str, Any], output_vertex_id: str | None) -> list[FlowCheckIssue]:
    nodes = _nodes(flow_data)
    issues: list[FlowCheckIssue] = []
    if not nodes:
        return [FlowCheckIssue(code="empty_flow", message="The flow has no components.")]
    if flow_requires_hitl(flow_data):
        issues.append(
            FlowCheckIssue(
                code="human_in_the_loop",
                message="The flow pauses for human approval, which an evaluation cannot answer.",
            )
        )
    if not any(_is_type(node, EVAL_INPUT_TYPES) for node in nodes):
        issues.append(
            FlowCheckIssue(code="no_input", message="Add a Chat Input or Text Input so each row has somewhere to go.")
        )
    outputs = output_vertices(flow_data)
    if not outputs:
        issues.append(
            FlowCheckIssue(code="no_output", message="Add a Chat Output or Text Output so there is an answer to score.")
        )
    elif output_vertex_id is not None and output_vertex_id not in {output["id"] for output in outputs}:
        issues.append(
            FlowCheckIssue(code="output_not_found", message="The selected output component is no longer in the flow.")
        )
    elif output_vertex_id is None and len(outputs) > 1:
        issues.append(
            FlowCheckIssue(
                code="multiple_outputs",
                message="The flow has more than one output. Choose the one to score.",
                components=[output["name"] for output in outputs],
            )
        )
    return issues


def _warnings(flow_data: dict[str, Any]) -> list[FlowCheckIssue]:
    nodes = _nodes(flow_data)
    warnings: list[FlowCheckIssue] = []
    side_effects = [_display_name(node) for node in nodes if _looks_side_effecting(node)]
    if side_effects:
        warnings.append(
            FlowCheckIssue(
                code="external_actions",
                message="These components may act outside Langflow and will really run once per row.",
                components=side_effects,
            )
        )
    memories = [_display_name(node) for node in nodes if _has_memory_output(node)]
    if memories:
        warnings.append(
            FlowCheckIssue(
                code="external_memory",
                message="This flow uses external memory. Rows will read and write it; it cannot be isolated.",
                components=memories,
            )
        )
    frozen = [_display_name(node) for node in nodes if (_node_data(node).get("node") or {}).get("frozen")]
    if frozen:
        warnings.append(
            FlowCheckIssue(
                code="frozen_components",
                message="Frozen components return the same cached result for every row.",
                components=frozen,
            )
        )
    return warnings


def check_flow(flow_data: dict[str, Any] | None, output_vertex_id: str | None = None) -> FlowCheckReport:
    data = flow_data or {}
    return FlowCheckReport(
        blocking=_blocking(data, output_vertex_id),
        warnings=_warnings(data),
        output_vertices=output_vertices(data),
    )


def resolve_output_vertex(flow_data: dict[str, Any], output_vertex_id: str | None) -> str:
    """The output vertex a run scores; call only after ``check_flow`` reported no blocking issue."""
    if output_vertex_id is not None:
        return output_vertex_id
    return output_vertices(flow_data)[0]["id"]
