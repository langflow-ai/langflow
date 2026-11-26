"""Reviewed definitions a Run Flow node runs in place of the stored flow.

A harness binds some Run Flow nodes to a reviewed revision. Those nodes run the reviewed
definition, so editing the stored flow after review never changes what runs. An ordinary Run
Flow node has no binding, every lookup here returns ``None`` for it, and it behaves exactly as
it always has.
"""

from copy import deepcopy

from lfx.helpers import get_tool_pack_flow
from lfx.template.field.base import UNDEFINED


def _origin(component, key: str) -> dict | None:
    vertex = getattr(component, "_vertex", None)
    origin = (getattr(vertex, "data", None) or {}).get(key)
    return origin if isinstance(origin, dict) else None


def tool_pack_binding(component):
    from lfx.projects.tool_packs import ToolPackToolBinding
    from lfx.projects.tools import TOOL_ORIGIN

    binding = (_origin(component, TOOL_ORIGIN) or {}).get("tool_pack")
    return ToolPackToolBinding.model_validate(binding) if binding is not None else None


def local_tool_binding(component):
    from lfx.projects.local_tools import LocalToolBinding
    from lfx.projects.tools import TOOL_ORIGIN

    binding = (_origin(component, TOOL_ORIGIN) or {}).get("local_tool")
    return LocalToolBinding.model_validate(binding) if binding is not None else None


def instruction_binding(component):
    """Read the typed contract on a generated Instructions reference node, if present."""
    from lfx.projects.bindings import BINDING_ORIGIN, FlowBinding

    origin = _origin(component, BINDING_ORIGIN)
    if origin is None or origin.get("field_name") != "system_prompt":
        return None
    return FlowBinding.model_validate({key: origin[key] for key in FlowBinding.model_fields if key in origin})


def frozen_flow(component, flow_id, flow_name) -> dict | None:
    """Return the dependency snapshot a reviewed parent graph froze for this flow."""
    graph = component.graph
    definitions = getattr(graph, "frozen_tool_flows", None) if graph is not None else None
    if definitions is None:
        return None
    source = definitions.get(str(flow_id)) if flow_id else None
    if not flow_id:
        matches = [item for item in definitions.values() if item["name"] == flow_name]
        source = matches[0] if len(matches) == 1 else None
    if source is None:
        msg = (
            "This flow was not included in the reviewed dependency snapshots. "
            "Review and save its containing flow or Tool Pack."
        )
        raise ValueError(msg)
    return source


async def reviewed_source(component, flow_id, flow_name) -> dict | None:
    """Return the reviewed definition this node runs, or ``None`` for an ordinary Run Flow.

    The result has ``data``, ``id``, ``name``, ``description`` and ``dependencies``. A bound
    definition is resolved once per run; every invocation still builds a fresh graph from it.
    """
    pack = tool_pack_binding(component)
    local = local_tool_binding(component)
    instruction = instruction_binding(component)
    if pack is not None and str(pack.tool.flow_id) != str(flow_id):
        msg = "The Tool Pack adapter points to a different flow. Restore its reviewed reference."
        raise ValueError(msg)
    if local is not None and local.flow_id != str(flow_id):
        msg = "The local tool adapter points to another flow. Restore its reviewed selection."
        raise ValueError(msg)
    if (frozen := frozen_flow(component, flow_id, flow_name)) is not None:
        return {**frozen, "dependencies": component.graph.frozen_tool_flows}
    binding = local or instruction or pack
    if binding is None:
        return None
    if binding is instruction and instruction.flow_id != str(flow_id):
        msg = "The bound Instructions flow was changed on the canvas. Update the harness binding."
        raise ValueError(msg)
    key = (getattr(component.graph, "_run_id", None), binding.model_dump_json())
    cached = getattr(component, "_reviewed_source", None)
    if cached is None or cached[0] != key:
        if binding is pack:
            resolved = await _resolve_tool_pack(component, pack)
        else:
            resolved = await _resolve_flow_binding(component, binding, local=binding is local)
        component._reviewed_source = (key, resolved)  # noqa: SLF001
    return component._reviewed_source[1]  # noqa: SLF001


async def _resolve_flow_binding(component, binding, *, local: bool) -> dict:
    from lfx.projects.bindings import validate_instruction_binding
    from lfx.projects.invocation import reviewed_flow_source
    from lfx.projects.local_tools import validate_local_tool_source

    field_name, validate = (
        ("tools", validate_local_tool_source) if local else ("system_prompt", validate_instruction_binding)
    )
    snapshot = await reviewed_flow_source(component, binding, field_name=field_name, validate=validate)
    return {
        "data": snapshot["data"],
        "id": binding.flow_id,
        "name": binding.name if local else snapshot.get("name"),
        "description": binding.description if local else None,
        "dependencies": snapshot.get("dependencies"),
    }


async def _resolve_tool_pack(component, binding) -> dict:
    graph = component.graph
    recorded = getattr(graph, "reviewed_tool_packs", {})
    value = binding.model_dump(mode="json")
    if recorded.get(str(binding.tool.flow_id)) == value:
        snapshot = await get_tool_pack_flow(user_id=component.user_id, binding=binding, require_current=False)
    else:
        snapshot = await get_tool_pack_flow(user_id=component.user_id, binding=binding)
    if binding.tool.dependencies and not snapshot.data.get("dependencies"):
        msg = "The reviewed tool dependency snapshots are unavailable. Review the Tool Pack again."
        raise ValueError(msg)
    if graph is not None:
        graph.reviewed_tool_packs[str(binding.tool.flow_id)] = value
    data = deepcopy(snapshot.data)
    return {
        "data": data["data"],
        "id": str(binding.tool.flow_id),
        "name": binding.tool.name,
        "description": binding.tool.description,
        "dependencies": data.get("dependencies"),
    }


def tool_metadata(component) -> dict:
    """Return the binding a harness tool carries so the Agent can audit which revision ran."""
    metadata = {}
    if (pack := tool_pack_binding(component)) is not None:
        metadata["harness_tool_pack"] = pack.model_dump(mode="json")
    if (local := local_tool_binding(component)) is not None:
        metadata["harness_local_tool"] = local.model_dump(mode="json")
    return metadata


def prepare_instruction_run(component, graph, *, tweaks) -> None:
    """Check a bound Instructions child against its reviewed contract before it runs."""
    binding = instruction_binding(component)
    if binding is None:
        return
    from lfx.projects.bindings import validate_instruction_binding

    if component.flow_id_selected != binding.flow_id:
        msg = "The bound Instructions flow was changed on the canvas. Update the harness binding."
        raise ValueError(msg)
    validate_instruction_binding(graph.raw_graph_data, binding)
    graph.get_vertex(binding.node_id).is_output = True
    component.status = {"flow_id": binding.flow_id, "revision": binding.revision, "version_id": binding.version_id}
    if tweaks:
        msg = "Configure inputs in the Instructions flow, then update the harness binding."
        raise ValueError(msg)


def declared_outputs(component, graph) -> dict:
    """Return the declared values a child run produced, keyed by ``(vertex id, output name)``.

    The transport result may replace values with display artifacts (for example
    ``{repr, raw, type}`` for text), while a flow edge needs the declared value, just like an
    edge within the child graph. A stored flow in Langflow keeps the transport result it always
    had, so existing downstream edges see the same values; this applies only to reviewed
    definitions and to flows served from a folder.
    """
    if (binding := instruction_binding(component)) is not None:
        from lfx.projects.bindings import validate_instruction_result

        terminal = graph.get_vertex(binding.node_id)
        if not terminal.built or terminal.custom_component is None:
            msg = "The bound Instructions flow did not produce its selected output."
            raise ValueError(msg)
        # Display artifacts can stringify a list or object, which must never satisfy this
        # runtime text contract, so read the edge value.
        value = terminal.custom_component.get_output(binding.output_name).value
        return {(binding.node_id, binding.output_name): validate_instruction_result(value)}
    parent = component.graph
    served = bool((getattr(parent, "context", None) or {}).get("project_dir"))
    reviewed = getattr(parent, "frozen_tool_flows", None) is not None or bool(tool_metadata(component))
    if not (served or reviewed):
        return {}
    return {
        (vertex.id, name): output.value
        for vertex in graph.vertices
        if vertex.built and vertex.custom_component is not None
        for name, output in vertex.custom_component.get_outputs_map().items()
        if output.value is not UNDEFINED
    }


def check_instruction_output(component, vertex_id: str, output_name: str) -> None:
    binding = instruction_binding(component)
    if binding is not None and (vertex_id, output_name) != (binding.node_id, binding.output_name):
        msg = "The Instructions output was changed on the canvas. Update the harness binding."
        raise ValueError(msg)
