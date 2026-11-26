"""Reviewed definitions a Run Flow node runs in place of the stored flow.

A harness binds some Run Flow nodes to a reviewed revision. Those nodes run the reviewed
definition, so editing the stored flow after review never changes what runs. An ordinary Run
Flow node has no binding, every lookup here returns ``None`` for it, and it behaves exactly as
it always has.
"""

from copy import deepcopy

from lfx.helpers import get_tool_pack_flow


def _origin(component, key: str) -> dict | None:
    vertex = getattr(component, "_vertex", None)
    origin = (getattr(vertex, "data", None) or {}).get(key)
    return origin if isinstance(origin, dict) else None


def tool_pack_binding(component):
    from lfx.projects.tool_packs import ToolPackToolBinding
    from lfx.projects.tools import TOOL_ORIGIN

    binding = (_origin(component, TOOL_ORIGIN) or {}).get("tool_pack")
    return ToolPackToolBinding.model_validate(binding) if binding is not None else None


def instruction_binding(component):
    """Read the typed contract on a generated Instructions reference node, if present."""
    from lfx.projects.bindings import BINDING_ORIGIN, FlowBinding

    origin = _origin(component, BINDING_ORIGIN)
    if origin is None or origin.get("field_name") != "system_prompt":
        return None
    return FlowBinding.model_validate({key: origin[key] for key in FlowBinding.model_fields if key in origin})


async def reviewed_source(component, flow_id, flow_name) -> dict | None:  # noqa: ARG001
    """Return the reviewed definition this node runs, or ``None`` for an ordinary Run Flow.

    The result has ``data``, ``id``, ``name``, ``description`` and ``dependencies``. A bound
    definition is resolved once per run; every invocation still builds a fresh graph from it.
    """
    pack = tool_pack_binding(component)
    if pack is not None and str(pack.tool.flow_id) != str(flow_id):
        msg = "The Tool Pack adapter points to a different flow. Restore its reviewed reference."
        raise ValueError(msg)
    if pack is None:
        return None
    key = (getattr(component.graph, "_run_id", None), pack)
    cached = getattr(component, "_reviewed_source", None)
    if cached is None or cached[0] != key:
        component._reviewed_source = (key, await _resolve_tool_pack(component, pack))  # noqa: SLF001
    return component._reviewed_source[1]  # noqa: SLF001


async def _resolve_tool_pack(component, binding) -> dict:
    snapshot = await get_tool_pack_flow(user_id=component.user_id, binding=binding)
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

    A bound Instructions child reports its selected output, read from the edge rather than the
    transport result. Any other Run Flow node keeps the transport result it always had.
    """
    if (binding := instruction_binding(component)) is None:
        return {}
    from lfx.projects.bindings import validate_instruction_result

    terminal = graph.get_vertex(binding.node_id)
    if not terminal.built or terminal.custom_component is None:
        msg = "The bound Instructions flow did not produce its selected output."
        raise ValueError(msg)
    # Display artifacts can stringify a list or object, which must never satisfy this
    # runtime text contract, so read the edge value.
    value = terminal.custom_component.get_output(binding.output_name).value
    return {(binding.node_id, binding.output_name): validate_instruction_result(value)}


def check_instruction_output(component, vertex_id: str, output_name: str) -> None:
    binding = instruction_binding(component)
    if binding is not None and (vertex_id, output_name) != (binding.node_id, binding.output_name):
        msg = "The Instructions output was changed on the canvas. Update the harness binding."
        raise ValueError(msg)
