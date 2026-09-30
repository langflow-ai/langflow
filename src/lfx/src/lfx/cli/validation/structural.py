"""Level 1 structural validation checks for Langflow flow JSON.

Includes JSON shape validation, node/edge structure checks, orphaned and
unused node detection, and version mismatch warnings.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from lfx.cli.validation.core import ValidationResult

# These are imported lazily to avoid circular imports at module level.
# The functions receive a ValidationResult and create ValidationIssue instances.


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


# Validation level constants (local copies to avoid circular import)
_LEVEL_STRUCTURAL = 1

_REQUIRED_TOP_LEVEL = {"id", "name", "data"}
_REQUIRED_DATA_KEYS = {"nodes", "edges"}


# ---------------------------------------------------------------------------
# Level 1 - structural checks (pure JSON, no component loading)
# ---------------------------------------------------------------------------


def _check_structural(flow: dict[str, Any], result: ValidationResult) -> bool:
    """Return False if the flow is so broken that further checks cannot run."""
    ok = True
    missing_top = _REQUIRED_TOP_LEVEL - set(flow.keys())
    for key in sorted(missing_top):
        result.issues.append(
            _make_issue(
                level=_LEVEL_STRUCTURAL,
                severity="error",
                node_id=None,
                node_name=None,
                message=f"Missing required top-level field: '{key}'",
            )
        )
        ok = False

    data = flow.get("data")
    if not isinstance(data, dict):
        result.issues.append(
            _make_issue(
                level=_LEVEL_STRUCTURAL,
                severity="error",
                node_id=None,
                node_name=None,
                message="'data' must be a JSON object",
            )
        )
        return False

    missing_data = _REQUIRED_DATA_KEYS - set(data.keys())
    for key in sorted(missing_data):
        result.issues.append(
            _make_issue(
                level=_LEVEL_STRUCTURAL,
                severity="error",
                node_id=None,
                node_name=None,
                message=f"Missing required field: 'data.{key}'",
            )
        )
        ok = False

    nodes = data.get("nodes", [])
    if not isinstance(nodes, list):
        result.issues.append(
            _make_issue(
                level=_LEVEL_STRUCTURAL,
                severity="error",
                node_id=None,
                node_name=None,
                message="'data.nodes' must be a JSON array",
            )
        )
        return False

    for i, node in enumerate(nodes):
        if not isinstance(node, dict):
            result.issues.append(
                _make_issue(
                    level=_LEVEL_STRUCTURAL,
                    severity="error",
                    node_id=None,
                    node_name=None,
                    message=f"Node at index {i} is not a JSON object",
                )
            )
            ok = False
            continue
        for req in ("id", "data"):
            if req not in node:
                result.issues.append(
                    _make_issue(
                        level=_LEVEL_STRUCTURAL,
                        severity="error",
                        node_id=node.get("id"),
                        node_name=_node_display_name(node),
                        message=f"Node at index {i} is missing required field '{req}'",
                    )
                )
                ok = False

        node_data = node.get("data", {})
        if isinstance(node_data, dict) and "type" not in node_data:
            result.issues.append(
                _make_issue(
                    level=_LEVEL_STRUCTURAL,
                    severity="warning",
                    node_id=node.get("id"),
                    node_name=_node_display_name(node),
                    message="Node is missing 'data.type' -- component type cannot be determined",
                )
            )

    return ok


# ---------------------------------------------------------------------------
# Orphaned and unused node checks
# ---------------------------------------------------------------------------


def _check_orphaned_nodes(flow: dict[str, Any], result: ValidationResult) -> None:
    """Warn about nodes that have no edges connecting them to the rest of the graph.

    A node is *orphaned* when it appears in no edge (neither as source nor as
    target).  Single-node flows are exempt.
    """
    data = flow.get("data", {})
    nodes: list[dict[str, Any]] = [n for n in data.get("nodes", []) if isinstance(n, dict) and "id" in n]
    edges: list[dict[str, Any]] = [e for e in data.get("edges", []) if isinstance(e, dict)]

    if len(nodes) <= 1:
        return  # single-node flows are always "connected"

    connected_ids: set[str] = set()
    for edge in edges:
        if edge.get("source"):
            connected_ids.add(edge["source"])
        if edge.get("target"):
            connected_ids.add(edge["target"])

    for node in nodes:
        node_id = node["id"]
        if node_id not in connected_ids:
            result.issues.append(
                _make_issue(
                    level=_LEVEL_STRUCTURAL,
                    severity="warning",
                    node_id=node_id,
                    node_name=_node_display_name(node),
                    message="Orphaned node: not connected to any other node",
                )
            )


def _check_unused_nodes(flow: dict[str, Any], result: ValidationResult) -> None:
    """Warn about nodes whose outputs never reach an output node.

    Walks the graph backwards from every node whose ``data.type`` ends with
    ``"Output"`` (e.g. ``ChatOutput``, ``TextOutput``).  Any node that is not
    reachable from an output node is considered unused.

    Single-node flows and flows with no output nodes are skipped.
    """
    data = flow.get("data", {})
    nodes: list[dict[str, Any]] = [n for n in data.get("nodes", []) if isinstance(n, dict) and "id" in n]
    edges: list[dict[str, Any]] = [e for e in data.get("edges", []) if isinstance(e, dict)]

    if len(nodes) <= 1:
        return

    # Build reverse adjacency: for each node, which nodes feed INTO it
    # (i.e. target -> {sources})
    predecessors: dict[str, set[str]] = {n["id"]: set() for n in nodes}
    for edge in edges:
        src = edge.get("source")
        tgt = edge.get("target")
        if src and tgt and tgt in predecessors:
            predecessors[tgt].add(src)

    # Identify output nodes by type suffix
    output_node_ids: set[str] = set()
    for node in nodes:
        component_type: str = node.get("data", {}).get("type", "") or ""
        if component_type.endswith("Output"):
            output_node_ids.add(node["id"])

    if not output_node_ids:
        return  # can't determine "useful" without knowing output nodes

    # BFS backwards from all output nodes to find every contributing node
    reachable: set[str] = set()
    queue: list[str] = list(output_node_ids)
    while queue:
        current = queue.pop()
        if current in reachable:
            continue
        reachable.add(current)
        queue.extend(predecessors.get(current, set()) - reachable)

    nodes_by_id = {n["id"]: n for n in nodes}
    for node_id, node in nodes_by_id.items():
        if node_id not in reachable:
            result.issues.append(
                _make_issue(
                    level=_LEVEL_STRUCTURAL,
                    severity="warning",
                    node_id=node_id,
                    node_name=_node_display_name(node),
                    message="Unused node: does not contribute to any output",
                )
            )


# ---------------------------------------------------------------------------
# Version mismatch / outdated components
# ---------------------------------------------------------------------------


def _check_version_mismatch(flow: dict[str, Any], result: ValidationResult) -> None:
    """Warn when nodes were built with a different Langflow version.

    Each unique ``lf_version`` embedded in the node metadata that differs from
    the currently installed Langflow version triggers a single warning covering
    all affected nodes.  If Langflow is not installed the check is skipped
    silently (lfx can run standalone).
    """
    from lfx.cli.validation.core import _get_lf_version

    installed = _get_lf_version()
    if installed is None:
        return  # Langflow not installed; skip silently

    nodes: list[dict[str, Any]] = [n for n in flow.get("data", {}).get("nodes", []) if isinstance(n, dict)]

    # Collect node IDs grouped by the version they were built with
    version_to_nodes: dict[str, list[str]] = {}
    for node in nodes:
        lf_version: str | None = node.get("data", {}).get("node", {}).get("lf_version")
        if lf_version and lf_version != installed:
            version_to_nodes.setdefault(lf_version, []).append(_node_display_name(node) or node.get("id") or "?")

    _max_sample = 3
    for built_version, node_names in sorted(version_to_nodes.items()):
        count = len(node_names)
        sample = ", ".join(node_names[:_max_sample]) + (" ..." if count > _max_sample else "")
        result.issues.append(
            _make_issue(
                level=_LEVEL_STRUCTURAL,
                severity="warning",
                node_id=None,
                node_name=None,
                message=(
                    f"{count} component(s) built with Langflow {built_version} "
                    f"(installed: {installed}) -- re-export recommended. "
                    f"Affected: {sample}"
                ),
            )
        )
