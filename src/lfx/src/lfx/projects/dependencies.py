"""Declared flow references and the transitive definitions behind a reviewed export."""

from dataclasses import dataclass

from lfx.projects.bindings import BINDING_ORIGIN, BoundFlowDependency, FlowSourceChangedError, flow_revision


@dataclass(frozen=True)
class FlowReference:
    flow_id: str | None
    name: str | None = None
    revision: str | None = None


def flow_references(data: dict) -> tuple[FlowReference, ...]:
    from lfx.projects.flow_slots import flow_runtime_bindings

    references = [
        FlowReference(binding.flow_id, revision=binding.revision) for _, binding in flow_runtime_bindings(data)
    ]
    for node in data.get("nodes", []):
        node_data = node.get("data", {})
        if node_data.get("type") not in {"RunFlow", "SubFlow"}:
            continue
        template = node_data.get("node", {}).get("template", {})
        flow_id = template.get("flow_id_selected", {}).get("value")
        name = template.get("flow_name_selected", template.get("flow_name", {})).get("value")
        origin = node_data.get(BINDING_ORIGIN) or {}
        pack_tool = (node_data.get("_harness_tool") or {}).get("tool_pack")
        if pack_tool:
            reviewed_tool = pack_tool["tool"]
            if str(reviewed_tool["flow_id"]) != flow_id:
                msg = "A nested Tool Pack adapter points to a different flow from its reviewed export."
                raise ValueError(msg)
            origin = reviewed_tool
        if flow_id or name:
            references.append(FlowReference(flow_id or None, name, origin.get("revision")))
    return tuple(references)


def dependency_ids(root_id: str, flows: list[dict]) -> tuple[str, ...]:
    """Resolve only supplied definitions; reject missing, stale, ambiguous, or cyclic edges."""
    by_id = {str(flow["id"]): flow for flow in flows}
    by_name: dict[str, list[str]] = {}
    for flow_id, flow in by_id.items():
        by_name.setdefault(flow["name"], []).append(flow_id)
    visited = set()

    def visit(flow_id, active):
        if flow_id in active:
            msg = "The exported tool contains a recursive flow reference."
            raise ValueError(msg)
        if flow_id in visited:
            return
        if flow_id not in by_id:
            msg = "An exported tool dependency is missing. Include its referenced flow."
            raise ValueError(msg)
        flow = by_id[flow_id]
        for reference in flow_references(flow["data"]):
            target_id = reference.flow_id
            if target_id is None:
                candidates = by_name.get(reference.name, [])
                if len(candidates) != 1:
                    msg = "An exported tool's named flow dependency is missing or ambiguous."
                    raise ValueError(msg)
                target_id = candidates[0]
            visit(target_id, active | {flow_id})
            if reference.revision and reference.revision != flow_revision(by_id[target_id]["data"]):
                msg = "A nested flow binding changed. Review and save it before exporting this tool."
                raise ValueError(msg)
        visited.add(flow_id)

    visit(root_id, set())
    return tuple(sorted(visited - {root_id}))


def binding_dependencies(root_id: str, flows: list[dict]) -> list[BoundFlowDependency]:
    """Describe the nested definitions included in a customization's review."""
    available = {str(flow["id"]): flow for flow in flows}
    return [
        BoundFlowDependency(
            flow_id=flow_id,
            name=available[flow_id]["name"],
            description=available[flow_id].get("description") or "",
            revision=flow_revision(available[flow_id]["data"]),
        )
        for flow_id in dependency_ids(root_id, flows)
    ]


def validate_binding_dependencies(binding, flows: list[dict]) -> None:
    expected = [item.definition() for item in binding_dependencies(binding.flow_id, flows)]
    actual = sorted((item.definition() for item in binding.dependencies), key=lambda item: item["flow_id"])
    if actual != expected:
        msg = "The flow dependencies changed. Review the customization and save its binding before running."
        raise FlowSourceChangedError(msg)
