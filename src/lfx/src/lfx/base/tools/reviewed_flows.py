"""Reviewed definitions a Run Flow node runs in place of the stored flow.

A harness binds some Run Flow nodes to a reviewed revision. Those nodes run the reviewed
definition, so editing the stored flow after review never changes what runs. An ordinary Run
Flow node has no binding, every lookup here returns ``None`` for it, and it behaves exactly as
it always has.
"""


def _origin(component, key: str) -> dict | None:
    vertex = getattr(component, "_vertex", None)
    origin = (getattr(vertex, "data", None) or {}).get(key)
    return origin if isinstance(origin, dict) else None


def instruction_binding(component):
    """Read the typed contract on a generated Instructions reference node, if present."""
    from lfx.projects.bindings import BINDING_ORIGIN, FlowBinding

    origin = _origin(component, BINDING_ORIGIN)
    if origin is None or origin.get("field_name") != "system_prompt":
        return None
    return FlowBinding.model_validate({key: origin[key] for key in FlowBinding.model_fields if key in origin})


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
