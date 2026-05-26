"""Graph-aware per-vertex capability planning for the prototype.

This is intentionally small and conservative: it loads the real lfx graph,
walks real vertices, and derives only the variable-read scopes visible from
`load_from_db` fields. It does not try to solve production graph partitioning.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

VARIABLE_NAME_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")


@dataclass(frozen=True)
class VertexCapabilityPlan:
    vertex_id: str
    display_name: str
    component_type: str
    trust: str
    scopes: tuple[str, ...]
    reasons: tuple[str, ...]
    predecessors: tuple[str, ...]
    upstream: tuple[str, ...]
    successors: tuple[str, ...]

    @property
    def is_untrusted(self) -> bool:
        return self.trust == "untrusted"


def _is_variable_name(value: object) -> bool:
    return isinstance(value, str) and bool(VARIABLE_NAME_RE.match(value.strip()))


def _trust_for_vertex(vertex) -> str:
    node = vertex.full_data["data"]["node"]
    component_type = vertex.full_data["data"]["type"]
    if component_type == "CustomComponent" or node.get("edited") is True:
        return "untrusted"
    return "first_party"


def _variable_scopes_for_vertex(vertex) -> tuple[tuple[str, ...], tuple[str, ...]]:
    template = vertex.full_data["data"]["node"]["template"]
    scopes: list[str] = []
    reasons: list[str] = []

    for field_name, field in template.items():
        if not isinstance(field, dict) or not field.get("load_from_db"):
            continue
        value = field.get("value")
        if not _is_variable_name(value):
            continue
        variable_name = value.strip()
        scopes.append(f"variables:read:{variable_name}")
        reasons.append(f"{field_name} loads {variable_name}")

    return tuple(sorted(set(scopes))), tuple(reasons)


async def build_vertex_capability_plan(flow_path: Path) -> list[VertexCapabilityPlan]:
    from lfx.load import aload_flow_from_json

    graph = await aload_flow_from_json(flow_path, disable_logs=True)
    graph.prepare()

    plans: list[VertexCapabilityPlan] = []
    for vertex in graph.vertices:
        scopes, reasons = _variable_scopes_for_vertex(vertex)
        upstream = tuple(sorted(v.id for v in graph.get_all_predecessors(vertex, recursive=True)))
        plans.append(
            VertexCapabilityPlan(
                vertex_id=vertex.id,
                display_name=vertex.display_name,
                component_type=vertex.full_data["data"]["type"],
                trust=_trust_for_vertex(vertex),
                scopes=scopes,
                reasons=reasons,
                predecessors=tuple(sorted(v.id for v in vertex.predecessors)),
                upstream=upstream,
                successors=tuple(sorted(vertex.successors_ids)),
            )
        )

    return plans
