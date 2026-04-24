"""Level 5 — agent architecture audit checks for Langflow flows."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from lfx.cli.validation.core import ValidationResult


def _make_issue(
    severity: str,
    node_id: str | None,
    node_name: str | None,
    message: str,
) -> Any:
    from lfx.cli.validation.core import LEVEL_AUDIT, ValidationIssue

    return ValidationIssue(
        level=LEVEL_AUDIT,
        severity=severity,
        node_id=node_id,
        node_name=node_name,
        message=message,
    )


def _node_display_name(node: dict[str, Any]) -> str | None:
    from lfx.cli.validation.core import _node_display_name as _display_name

    return _display_name(node)


_SECRET_PATTERNS = [
    (r"sk-[A-Za-z0-9]{20,}", "OpenAI API key"),
    (r"ghp_[A-Za-z0-9]{36}", "GitHub personal access token"),
    (r"glpat-[A-Za-z0-9\-]{20,}", "GitLab personal access token"),
    (r"AKIA[0-9A-Z]{16}", "AWS access key ID"),
]
_SECRET_FIELD_HINTS = ("api_key", "apikey", "token", "secret", "password", "credential")
_CODE_EXEC_TYPES = {"PythonFunction", "Code", "CustomComponent", "PythonCode", "Shell"}
_STATE_MUTATORS = {"FileWriter", "DatabaseWrite", "VectorStoreUpsert", "UpdateMemory"}
_SAFETY_SENSITIVE = {"Agent", "ToolCallingAgent", "ReActAgent", "Supervisor", "MultiAgent"}
_OBSERVABILITY = {"Tracing", "LangSmith", "LangFuse", "CallbackHandler", "Observable"}
_LIMIT_KEYWORDS = ("max_", "limit", "ttl", "expire", "top_", "threshold", "retention")
_EXACT_LIMIT_KEYS = {"k", "top_k", "ttl", "limit", "max_tokens", "max_results"}


def _iter_nodes(flow: dict[str, Any]) -> list[dict[str, Any]]:
    return [node for node in flow.get("data", {}).get("nodes", []) if isinstance(node, dict)]


def _build_graph(flow: dict[str, Any]) -> dict[str, set[str]]:
    graph: dict[str, set[str]] = {}
    for edge in flow.get("data", {}).get("edges", []):
        if not isinstance(edge, dict):
            continue
        source = edge.get("source")
        target = edge.get("target")
        if not source or not target:
            continue
        graph.setdefault(source, set()).add(target)
    return graph


def _reachable_from(starts: set[str], graph: dict[str, set[str]]) -> set[str]:
    visited: set[str] = set()
    stack = [node_id for node_id in starts if node_id]
    while stack:
        current = stack.pop()
        if current in visited:
            continue
        visited.add(current)
        stack.extend(neighbor for neighbor in graph.get(current, ()) if neighbor not in visited)
    return visited


def _check_hardcoded_secrets(flow: dict[str, Any], result: ValidationResult) -> None:
    for node in _iter_nodes(flow):
        template: dict[str, Any] = node.get("data", {}).get("node", {}).get("template", {})
        for field_name, field_def in template.items():
            if not isinstance(field_def, dict):
                continue
            metadata_parts = [
                str(field_name).strip().lower(),
                str(field_def.get("name", "")).strip().lower(),
                str(field_def.get("display_name", "")).strip().lower(),
                str(field_def.get("label", "")).strip().lower(),
            ]
            if not any(hint in part for part in metadata_parts for hint in _SECRET_FIELD_HINTS if part):
                continue

            value = str(field_def.get("value", "")).strip()
            if not value:
                continue

            for pattern, label in _SECRET_PATTERNS:
                if re.search(pattern, value):
                    result.issues.append(
                        _make_issue(
                            severity="error",
                            node_id=node.get("id"),
                            node_name=_node_display_name(node),
                            message=(
                                f"Hardcoded {label} detected in field '{field_name}'. "
                                "Use environment variables or Langflow global secrets instead."
                            ),
                        )
                    )
                    break


def _check_unrestricted_code_exec(flow: dict[str, Any], result: ValidationResult) -> None:
    has_sandbox = False
    code_nodes: list[dict[str, Any]] = []

    for node in _iter_nodes(flow):
        node_type = node.get("data", {}).get("type")
        if node_type in _CODE_EXEC_TYPES:
            code_nodes.append(node)
        if node_type and "sandbox" in node_type.lower():
            has_sandbox = True

    if code_nodes and not has_sandbox:
        names = ", ".join(_node_display_name(node) or node.get("id", "?") for node in code_nodes[:5])
        result.issues.append(
            _make_issue(
                severity="warning",
                node_id=None,
                node_name=None,
                message=(
                    f"Unrestricted code execution detected ({len(code_nodes)} node(s): {names}). "
                    "Consider wrapping in a sandbox component for production flows."
                ),
            )
        )


def _check_missing_error_handling(flow: dict[str, Any], result: ValidationResult) -> None:
    safety_nodes: list[dict[str, Any]] = []
    error_handlers: set[str] = set()

    for node in _iter_nodes(flow):
        node_type = node.get("data", {}).get("type")
        if node_type in _SAFETY_SENSITIVE:
            safety_nodes.append(node)
        if node_type and (
            "error" in node_type.lower()
            or "catch" in node_type.lower()
            or "fallback" in node_type.lower()
        ):
            node_id = node.get("id")
            if node_id:
                error_handlers.add(node_id)

    graph = _build_graph(flow)

    def has_error_handler_downstream(start_id: str | None) -> bool:
        if not start_id:
            return False
        visited: set[str] = set()
        stack: list[str] = [start_id]
        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)
            if current != start_id and current in error_handlers:
                return True
            stack.extend(neighbor for neighbor in graph.get(current, ()) if neighbor not in visited)
        return False

    for node in safety_nodes:
        node_id = node.get("id")
        if not has_error_handler_downstream(node_id):
            result.issues.append(
                _make_issue(
                    severity="warning",
                    node_id=node_id,
                    node_name=_node_display_name(node),
                    message=(
                        "Agent node has no error-handling or fallback path. "
                        "Add an error handler or retry component for production reliability."
                    ),
                )
            )


def _check_runaway_agent_loops(flow: dict[str, Any], result: ValidationResult) -> None:
    nodes = _iter_nodes(flow)
    nodes_by_id = {node.get("id"): node for node in nodes if node.get("id")}
    agent_ids = {
        node.get("id")
        for node in nodes
        if "agent" in str(node.get("data", {}).get("type", "")).lower()
        or "loop" in str(node.get("data", {}).get("type", "")).lower()
        or "react" in str(node.get("data", {}).get("type", "")).lower()
    }
    graph = _build_graph(flow)

    for agent_id in {node_id for node_id in agent_ids if node_id}:
        visited: set[str] = set()
        queue = list(graph.get(agent_id, set()))
        while queue:
            current = queue.pop(0)
            if current == agent_id:
                result.issues.append(
                    _make_issue(
                        severity="warning",
                        node_id=agent_id,
                        node_name=_node_display_name(nodes_by_id.get(agent_id, {})),
                        message=(
                            "Agent loop detected. Ensure a max-iterations or max-tokens guard is configured "
                            "to prevent runaway execution."
                        ),
                    )
                )
                break
            if current not in visited and current in agent_ids:
                visited.add(current)
                queue.extend(graph.get(current, set()))


def _check_unbounded_memory_growth(flow: dict[str, Any], result: ValidationResult) -> None:
    for node in _iter_nodes(flow):
        node_type = str(node.get("data", {}).get("type", ""))
        if "memory" not in node_type.lower() and "vector" not in node_type.lower():
            continue

        template: dict[str, Any] = node.get("data", {}).get("node", {}).get("template", {})
        has_limit = False
        for field_name, field_def in template.items():
            if not isinstance(field_def, dict):
                continue

            normalized_field_name = str(field_name).strip().lower()
            metadata_parts = [
                normalized_field_name,
                str(field_def.get("name", "")).strip().lower(),
                str(field_def.get("display_name", "")).strip().lower(),
                str(field_def.get("label", "")).strip().lower(),
            ]
            input_types = field_def.get("input_types")
            if isinstance(input_types, list):
                metadata_parts.extend(str(item).strip().lower() for item in input_types)

            matches_limit_field = (
                normalized_field_name in _EXACT_LIMIT_KEYS
                or any(part in _EXACT_LIMIT_KEYS for part in metadata_parts if part)
                or any(keyword in part for part in metadata_parts for keyword in _LIMIT_KEYWORDS if part)
            )
            if not matches_limit_field:
                continue

            value = field_def.get("value")
            if value is None:
                continue
            if isinstance(value, str) and not value.strip():
                continue

            has_limit = True
            break

        if not has_limit:
            result.issues.append(
                _make_issue(
                    severity="warning",
                    node_id=node.get("id"),
                    node_name=_node_display_name(node),
                    message=(
                        f"Memory/vector component '{_node_display_name(node) or node.get('id')}' has no "
                        "size limit, TTL, or retention policy configured. "
                        "This may cause unbounded context growth in long-running agents."
                    ),
                )
            )


def _check_missing_observability(flow: dict[str, Any], result: ValidationResult) -> None:
    node_types = {node.get("data", {}).get("type") for node in _iter_nodes(flow)}
    if not bool(node_types & _OBSERVABILITY):
        result.issues.append(
            _make_issue(
                severity="warning",
                node_id=None,
                node_name=None,
                message=(
                    "No observability or tracing component detected. "
                    "Add LangSmith, LangFuse, or a callback handler for production debugging."
                ),
            )
        )


def _check_state_mutator_safety(flow: dict[str, Any], result: ValidationResult) -> None:
    mutator_nodes: list[dict[str, Any]] = []
    upstream_validators: set[str] = set()

    for node in _iter_nodes(flow):
        node_type = str(node.get("data", {}).get("type", ""))
        if node_type in _STATE_MUTATORS:
            mutator_nodes.append(node)
        if "validate" in node_type.lower() or "guard" in node_type.lower() or "filter" in node_type.lower():
            node_id = node.get("id")
            if node_id:
                upstream_validators.add(node_id)

    validator_downstream = _reachable_from(upstream_validators, _build_graph(flow))
    for node in mutator_nodes:
        node_id = node.get("id")
        if node_id not in validator_downstream:
            result.issues.append(
                _make_issue(
                    severity="warning",
                    node_id=node_id,
                    node_name=_node_display_name(node),
                    message=(
                        f"State-mutating component '{_node_display_name(node) or node_id}' has no upstream "
                        "validation or guard. Add a validation node to prevent corrupt data writes."
                    ),
                )
            )


def _check_agent_audit(flow: dict[str, Any], result: ValidationResult) -> None:
    _check_hardcoded_secrets(flow, result)
    _check_unrestricted_code_exec(flow, result)
    _check_missing_error_handling(flow, result)
    _check_runaway_agent_loops(flow, result)
    _check_unbounded_memory_growth(flow, result)
    _check_missing_observability(flow, result)
    _check_state_mutator_safety(flow, result)
