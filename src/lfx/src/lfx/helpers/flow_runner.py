"""Flow runner functions for lfx package.

This module contains the run_flow function for executing flows.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from lfx.schema.schema import INPUT_FIELD_NAME

if TYPE_CHECKING:
    from lfx.graph.graph.base import Graph
    from lfx.graph.schema import RunOutputs


async def run_flow(
    inputs: dict | list[dict] | None = None,
    tweaks: dict | None = None,
    flow_id: str | None = None,
    flow_name: str | None = None,
    output_type: str | None = "chat",
    user_id: str | None = None,
    run_id: str | None = None,
    session_id: str | None = None,
    graph: Graph | None = None,
) -> list[RunOutputs]:
    """Run a flow with given inputs.

    This function supports two modes:
    1. Direct graph execution (lfx mode): When graph is provided, executes directly
    2. Database mode (langflow backend): When graph is not provided, delegates to backend

    Args:
        inputs: Input values for the flow.
        tweaks: Optional tweaks to apply.
        flow_id: The flow ID to run.
        flow_name: The flow name to run.
        output_type: The type of output to return.
        user_id: The user ID (required for database mode, optional for direct graph execution).
        run_id: Optional run ID.
        session_id: Optional session ID.
        graph: Optional pre-loaded graph (required for lfx mode).

    Returns:
        List of run outputs.
    """
    # If no graph is provided and we have langflow backend, delegate to it
    if graph is None:
        try:
            from langflow.helpers.flow import run_flow as backend_run_flow

            return await backend_run_flow(
                inputs=inputs,
                tweaks=tweaks,
                flow_id=flow_id,
                flow_name=flow_name,
                output_type=output_type,
                user_id=user_id,
                run_id=run_id,
                session_id=session_id,
                graph=graph,
            )
        except ImportError:
            pass

        msg = "run_flow requires a graph parameter in lfx standalone mode"
        raise ValueError(msg)

    # Direct graph execution mode (lfx) - user_id is optional

    # Enable environment variable fallback for subflow execution
    graph.fallback_to_env_vars = True

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

    # In lfx, we enable fallback to environment variables by default
    # This allows components to read API keys from environment variables
    fallback_to_env_vars = True

    return await graph.arun(
        inputs_list,
        outputs=outputs,
        inputs_components=inputs_components,
        types=types,
        fallback_to_env_vars=fallback_to_env_vars,
    )
