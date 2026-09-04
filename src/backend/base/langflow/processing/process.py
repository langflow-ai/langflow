from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lfx.log.logger import logger
from lfx.processing.process import apply_tweaks as _lfx_apply_tweaks
from lfx.processing.process import apply_tweaks_on_vertex as _lfx_apply_tweaks_on_vertex
from lfx.processing.process import process_tweaks as _lfx_process_tweaks
from lfx.processing.process import process_tweaks_on_graph as _lfx_process_tweaks_on_graph
from lfx.processing.process import run_graph_internal as _lfx_run_graph_internal
from pydantic import BaseModel

from langflow.schema.graph import InputValue, Tweaks
from langflow.schema.schema import INPUT_FIELD_NAME

if TYPE_CHECKING:
    from lfx.graph.graph.base import Graph
    from lfx.graph.schema import RunOutputs


class Result(BaseModel):
    result: Any
    session_id: str


async def run_graph(
    graph: Graph,
    input_value: str,
    input_type: str,
    output_type: str,
    *,
    session_id: str | None = None,
    fallback_to_env_vars: bool = False,
    output_component: str | None = None,
    stream: bool = False,
) -> list[RunOutputs]:
    """Runs the given Langflow Graph with the specified input and returns the outputs.

    Args:
        graph (Graph): The graph to be executed.
        input_value (str): The input value to be passed to the graph.
        input_type (str): The type of the input value.
        output_type (str): The type of the desired output.
        session_id (str | None, optional): The session ID to be used for the flow. Defaults to None.
        fallback_to_env_vars (bool, optional): Whether to fallback to environment variables.
            Defaults to False.
        output_component (Optional[str], optional): The specific output component to retrieve. Defaults to None.
        stream (bool, optional): Whether to stream the results or not. Defaults to False.

    Returns:
        List[RunOutputs]: A list of RunOutputs objects representing the outputs of the graph.

    """
    inputs = [InputValue(components=[], input_value=input_value, type=input_type)]
    if output_component:
        outputs = [output_component]
    else:
        outputs = [
            vertex.id
            for vertex in graph.vertices
            if output_type == "debug"
            or (vertex.is_output and (output_type == "any" or output_type in vertex.id.lower()))
        ]
    components = []
    inputs_list = []
    types = []
    for input_value_request in inputs:
        if input_value_request.input_value is None:
            await logger.awarning("InputValueRequest input_value cannot be None, defaulting to an empty string.")
            input_value_request.input_value = ""
        components.append(input_value_request.components or [])
        inputs_list.append({INPUT_FIELD_NAME: input_value_request.input_value})
        types.append(input_value_request.type)
    return await graph.arun(
        inputs_list,
        inputs_components=components,
        types=types,
        outputs=outputs or [],
        stream=stream,
        session_id=session_id,
        fallback_to_env_vars=fallback_to_env_vars,
    )


def validate_input(
    graph_data: dict[str, Any], tweaks: Tweaks | dict[str, str | dict[str, Any]]
) -> list[dict[str, Any]]:
    if not isinstance(graph_data, dict) or not isinstance(tweaks, dict):
        msg = "graph_data and tweaks should be dictionaries"
        raise TypeError(msg)

    nodes = graph_data.get("data", {}).get("nodes") or graph_data.get("nodes")

    if not isinstance(nodes, list):
        msg = "graph_data should contain a list of nodes under 'data' key or directly under 'nodes' key"
        raise TypeError(msg)

    return nodes


# The tweak application lives in lfx. This module re-exports it so the langflow
# API paths and the lfx paths enforce one implementation of the protected-field
# floor and the deployment tweak policy.
#
# The two copies had already drifted before this change: lfx was refactored onto
# `is_protected_tweak_field` while this copy kept the older inline checks and a
# separate "code field" warning. The guards were equivalent, so no request was
# unguarded, but the drift is why a second copy is not worth keeping.
run_graph_internal = _lfx_run_graph_internal
apply_tweaks = _lfx_apply_tweaks
apply_tweaks_on_vertex = _lfx_apply_tweaks_on_vertex
process_tweaks = _lfx_process_tweaks
process_tweaks_on_graph = _lfx_process_tweaks_on_graph
