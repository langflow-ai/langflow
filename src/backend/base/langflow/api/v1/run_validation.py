"""Guards for the v1 run endpoints — reject flows the synchronous run path cannot execute."""

from __future__ import annotations

from fastapi import HTTPException, status

_HUMAN_INPUT_TYPE = "HumanInput"

HITL_UNSUPPORTED_DETAIL = (
    "This flow uses Human-in-the-Loop (a Human Input node or a tool that requires approval), which the "
    "v1 run API cannot execute because it cannot pause and resume. Run it with the v2 workflows API instead: "
    "POST /api/v2/workflows with mode='background', then resume via POST /api/v2/workflows/{job_id}/resume."
)


def flow_requires_hitl(graph_data: dict) -> bool:
    """True if the flow pauses for a human decision.

    Two HITL shapes: a Human Input node wired to a downstream consumer (an isolated node is
    skipped at runtime, so it is not blocking), or an approval-gated agent tool (a
    ``tools_metadata`` row carrying a non-empty ``approval_actions``).
    """
    nodes = graph_data.get("nodes") or []
    edges = graph_data.get("edges") or []
    edge_sources = {edge.get("source") for edge in edges}
    for node in nodes:
        node_data = node.get("data") or {}
        node_id = node_data.get("id") or node.get("id")
        if node_data.get("type") == _HUMAN_INPUT_TYPE and node_id in edge_sources:
            return True
        template = (node_data.get("node") or {}).get("template") or {}
        rows = (template.get("tools_metadata") or {}).get("value")
        if isinstance(rows, list) and any(isinstance(row, dict) and row.get("approval_actions") for row in rows):
            return True
    return False


def raise_if_hitl_unsupported(graph_data: dict) -> None:
    """Reject a v1 run of a HITL flow with a clear pointer to the v2 workflows API."""
    if flow_requires_hitl(graph_data):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=HITL_UNSUPPORTED_DETAIL)
