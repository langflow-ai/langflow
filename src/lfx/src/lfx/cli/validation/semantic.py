"""Semantic validation checks for Langflow flow JSON.

Includes component existence (Level 2), edge type compatibility (Level 3),
required inputs (Level 4), and credential checks.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from lfx.cli.validation.core import ValidationResult

# Validation level constants (local copies to avoid circular import)
_LEVEL_COMPONENTS = 2
_LEVEL_EDGE_TYPES = 3
_LEVEL_REQUIRED_INPUTS = 4


def _make_issue(
    level: int,
    severity: str,
    node_id: str | None,
    node_name: str | None,
    message: str,
) -> Any:
    from lfx.cli.validation.core import ValidationIssue

    return ValidationIssue(
        level=level,
        severity=severity,
        node_id=node_id,
        node_name=node_name,
        message=message,
    )


def _node_display_name(node: dict[str, Any]) -> str | None:
    from lfx.cli.validation.core import _node_display_name as _ndn

    return _ndn(node)


# ---------------------------------------------------------------------------
# Level 2 - component existence (loads lfx component registry)
# ---------------------------------------------------------------------------


def _check_component_existence(flow: dict[str, Any], result: ValidationResult) -> None:
    try:
        from lfx.interface.utils import initialize_components  # type: ignore[import-untyped]

        component_registry: set[str] = set(initialize_components().keys())
    except Exception as exc:  # noqa: BLE001
        result.issues.append(
            _make_issue(
                level=_LEVEL_COMPONENTS,
                severity="warning",
                node_id=None,
                node_name=None,
                message=f"Could not load component registry (skipping component checks): {exc}",
            )
        )
        return

    for node in flow.get("data", {}).get("nodes", []):
        if not isinstance(node, dict):
            continue
        node_data = node.get("data", {})
        component_type: str | None = node_data.get("type")
        if not component_type:
            continue
        if component_type not in component_registry:
            result.issues.append(
                _make_issue(
                    level=_LEVEL_COMPONENTS,
                    severity="error",
                    node_id=node.get("id"),
                    node_name=_node_display_name(node),
                    message=(f"Unknown component type '{component_type}'. This component may be missing or outdated."),
                )
            )


# ---------------------------------------------------------------------------
# Level 3 - edge type compatibility
# ---------------------------------------------------------------------------


def _check_edge_type_compatibility(flow: dict[str, Any], result: ValidationResult) -> None:
    """Check that source output types are compatible with target input types.

    This is a best-effort check: if type information is missing from the node
    template we emit a warning rather than an error.
    """
    data = flow.get("data", {})
    nodes_by_id: dict[str, dict[str, Any]] = {
        n["id"]: n for n in data.get("nodes", []) if isinstance(n, dict) and "id" in n
    }

    for edge in data.get("edges", []):
        if not isinstance(edge, dict):
            continue
        src_id: str | None = edge.get("source")
        tgt_id: str | None = edge.get("target")
        src_handle: dict[str, Any] = edge.get("data", {}).get("sourceHandle", {}) or {}
        tgt_handle: dict[str, Any] = edge.get("data", {}).get("targetHandle", {}) or {}

        if not src_id or not tgt_id:
            continue

        src_node = nodes_by_id.get(src_id)
        tgt_node = nodes_by_id.get(tgt_id)
        if not src_node or not tgt_node:
            result.issues.append(
                _make_issue(
                    level=_LEVEL_EDGE_TYPES,
                    severity="error",
                    node_id=None,
                    node_name=None,
                    message=(f"Edge references non-existent node(s): source={src_id!r}, target={tgt_id!r}"),
                )
            )
            continue

        output_types: list[str] = src_handle.get("output_types", [])
        src_type: str | None = output_types[0] if output_types else None
        tgt_type: str | None = tgt_handle.get("type")

        if src_type and tgt_type and tgt_type not in {src_type, "Any"}:
            result.issues.append(
                _make_issue(
                    level=_LEVEL_EDGE_TYPES,
                    severity="warning",
                    node_id=tgt_id,
                    node_name=_node_display_name(tgt_node),
                    message=(
                        f"Possible type mismatch on edge from "
                        f"'{_node_display_name(src_node)}' -> '{_node_display_name(tgt_node)}': "
                        f"source emits '{src_type}', target expects '{tgt_type}'"
                    ),
                )
            )


# ---------------------------------------------------------------------------
# Level 4 - required inputs connected
# ---------------------------------------------------------------------------


def _check_required_inputs(flow: dict[str, Any], result: ValidationResult) -> None:
    """Verify that all required input fields have a value or an incoming edge."""
    data = flow.get("data", {})
    nodes = data.get("nodes", [])
    edges = data.get("edges", [])

    # Build set of (node_id, field_name) pairs that receive an edge
    connected_inputs: set[tuple[str, str]] = set()
    for edge in edges:
        if not isinstance(edge, dict):
            continue
        tgt_id = edge.get("target")
        tgt_handle = edge.get("data", {}).get("targetHandle", {}) or {}
        field_name = tgt_handle.get("fieldName")
        if tgt_id and field_name:
            connected_inputs.add((tgt_id, field_name))

    for node in nodes:
        if not isinstance(node, dict):
            continue
        node_id = node.get("id")
        node_data = node.get("data", {})
        template: dict[str, Any] = node_data.get("node", {}).get("template", {})

        for field_name, field_def in template.items():
            if field_name.startswith("_") or not isinstance(field_def, dict):
                continue
            is_required = field_def.get("required", False)
            show = field_def.get("show", True)
            if not is_required or not show:
                continue

            has_value = field_def.get("value") not in (None, "", [], {})
            has_edge = (node_id, field_name) in connected_inputs

            if not has_value and not has_edge:
                result.issues.append(
                    _make_issue(
                        level=_LEVEL_REQUIRED_INPUTS,
                        severity="error",
                        node_id=node_id,
                        node_name=_node_display_name(node),
                        message=f"Required input '{field_name}' has no value and no incoming edge",
                    )
                )


# ---------------------------------------------------------------------------
# Missing credentials
# ---------------------------------------------------------------------------


def _check_missing_credentials(flow: dict[str, Any], result: ValidationResult) -> None:
    """Warn when password/secret fields have no value and no matching env var.

    A template field is considered a *credential field* when it has
    ``"password": true`` (or ``"display_password": true``).  If no value is
    stored in the flow JSON *and* no corresponding environment variable is set
    *and* the field has no incoming edge, a warning is emitted so the user
    knows to provide the secret before running the flow.

    The environment variable name is derived by uppercasing the field name and
    replacing hyphens with underscores (e.g. ``openai_api_key`` ->
    ``OPENAI_API_KEY``).
    """
    data = flow.get("data", {})
    edges = data.get("edges", [])

    # Build the set of (node_id, field_name) pairs that receive an edge
    connected_inputs: set[tuple[str, str]] = set()
    for edge in edges:
        if not isinstance(edge, dict):
            continue
        tgt_id = edge.get("target")
        tgt_handle = edge.get("data", {}).get("targetHandle", {}) or {}
        field_name = tgt_handle.get("fieldName")
        if tgt_id and field_name:
            connected_inputs.add((tgt_id, field_name))

    for node in data.get("nodes", []):
        if not isinstance(node, dict):
            continue
        node_id = node.get("id")
        node_data = node.get("data", {})
        template: dict[str, Any] = node_data.get("node", {}).get("template", {})

        for field_name, field_def in template.items():
            if field_name.startswith("_") or not isinstance(field_def, dict):
                continue

            is_credential = field_def.get("password", False) or field_def.get("display_password", False)
            if not is_credential:
                continue

            show = field_def.get("show", True)
            if not show:
                continue

            # Already satisfied? Check value, incoming edge, or env var.
            has_value = bool(field_def.get("value"))
            has_edge = (node_id, field_name) in connected_inputs
            if has_value or has_edge:
                continue

            env_key = field_name.upper().replace("-", "_")
            if os.environ.get(env_key):
                continue

            result.issues.append(
                _make_issue(
                    level=_LEVEL_REQUIRED_INPUTS,
                    severity="warning",
                    node_id=node_id,
                    node_name=_node_display_name(node),
                    message=(
                        f"Credential field '{field_name}' has no value "
                        f"(set ${env_key} or configure via global variables)"
                    ),
                )
            )
