"""Flow helper functions for lfx package."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from loguru import logger
from pydantic import BaseModel, Field, create_model

from lfx.schema.schema import INPUT_FIELD_NAME

if TYPE_CHECKING:
    from lfx.graph.graph.base import Graph
    from lfx.graph.schema import RunOutputs
    from lfx.graph.vertex.base import Vertex
    from lfx.schema.data import Data


def get_flow_inputs(graph: Graph) -> list[Vertex]:
    """Retrieves the flow inputs from the given graph.

    Args:
        graph (Graph): The graph object representing the flow.

    Returns:
        List[Vertex]: A list of input vertices.
    """
    return [vertex for vertex in graph.vertices if vertex.is_input]


def build_schema_from_inputs(name: str, inputs: list[Vertex]) -> type[BaseModel]:
    """Builds a schema from the given inputs.

    Args:
        name (str): The name of the schema.
        inputs (List[Vertex]): A list of Vertex objects representing the inputs.

    Returns:
        BaseModel: The schema model.
    """
    fields = {}
    for input_ in inputs:
        field_name = input_.display_name.lower().replace(" ", "_")
        description = input_.description
        fields[field_name] = (str, Field(default="", description=description))
    return create_model(name, **fields)


def get_arg_names(inputs: list[Vertex]) -> list[dict[str, str]]:
    """Returns a list of dictionaries containing the component name and its corresponding argument name.

    Args:
        inputs (List[Vertex]): A list of Vertex objects representing the inputs.

    Returns:
        List[dict[str, str]]: A list of dictionaries, where each dictionary contains the component name and its
            argument name.
    """
    return [
        {"component_name": input_.display_name, "arg_name": input_.display_name.lower().replace(" ", "_")}
        for input_ in inputs
    ]


async def list_flows(*, user_id: str | None = None) -> list[Data]:
    """List flows for a user.

    In lfx, this is a stub that returns an empty list since we don't have
    a database backend by default.

    Args:
        user_id: The user ID to list flows for.

    Returns:
        List of flow data objects.
    """
    if not user_id:
        msg = "Session is invalid"
        raise ValueError(msg)

    # In lfx, we don't have a database backend by default
    # This is a stub implementation
    logger.warning("list_flows called but lfx doesn't have database backend by default")
    return []


async def load_flow(
    user_id: str,  # noqa: ARG001
    flow_id: str | None = None,
    flow_name: str | None = None,
    tweaks: dict | None = None,  # noqa: ARG001
) -> Graph:
    """Load a flow by ID or name.

    In lfx, this is a stub that raises an error since we don't have
    a database backend by default.

    Args:
        user_id: The user ID.
        flow_id: The flow ID to load.
        flow_name: The flow name to load.
        tweaks: Optional tweaks to apply to the flow.

    Returns:
        The loaded flow graph.
    """
    if not flow_id and not flow_name:
        msg = "Flow ID or Flow Name is required"
        raise ValueError(msg)

    # In lfx, we don't have a database backend by default
    # This is a stub implementation
    msg = f"load_flow not implemented in lfx - cannot load flow {flow_id or flow_name}"
    raise NotImplementedError(msg)


async def run_flow(
    inputs: dict | list[dict] | None = None,
    tweaks: dict | None = None,  # noqa: ARG001
    flow_id: str | None = None,  # noqa: ARG001
    flow_name: str | None = None,  # noqa: ARG001
    output_type: str | None = "chat",
    user_id: str | None = None,
    run_id: str | None = None,
    session_id: str | None = None,
    graph: Graph | None = None,
) -> list[RunOutputs]:
    """Run a flow with given inputs.

    Args:
        inputs: Input values for the flow.
        tweaks: Optional tweaks to apply.
        flow_id: The flow ID to run.
        flow_name: The flow name to run.
        output_type: The type of output to return.
        user_id: The user ID.
        run_id: Optional run ID.
        session_id: Optional session ID.
        graph: Optional pre-loaded graph.

    Returns:
        List of run outputs.
    """
    if user_id is None:
        msg = "Session is invalid"
        raise ValueError(msg)

    if graph is None:
        # In lfx, we can't load flows from database
        msg = "run_flow requires a graph parameter in lfx"
        raise ValueError(msg)

    if run_id:
        graph.set_run_id(UUID(run_id))
    if session_id:
        graph.session_id = session_id
    if user_id:
        graph.user_id = user_id

    if inputs is None:
        inputs = []
    if isinstance(inputs, dict):
        inputs = [inputs]

    inputs_list = []
    inputs_components = []
    types = []

    for input_dict in inputs:
        inputs_list.append({INPUT_FIELD_NAME: input_dict.get("input_value", "")})
        inputs_components.append(input_dict.get("components", []))
        types.append(input_dict.get("type", "chat"))

    outputs = [
        vertex.id
        for vertex in graph.vertices
        if output_type == "debug"
        or (vertex.is_output and (output_type == "any" or (output_type and output_type in str(vertex.id).lower())))
    ]

    # In lfx, we don't have settings service, so use False as default
    fallback_to_env_vars = False

    return await graph.arun(
        inputs_list,
        outputs=outputs,
        inputs_components=inputs_components,
        types=types,
        fallback_to_env_vars=fallback_to_env_vars,
    )


__all__ = ["build_schema_from_inputs", "get_arg_names", "get_flow_inputs", "list_flows", "load_flow", "run_flow"]
