"""Flow helper functions for lfx package."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic.v1 import BaseModel, Field, create_model

# Import run_flow from utils
from lfx.utils.util import run_flow

if TYPE_CHECKING:
    from lfx.graph.graph.base import Graph
    from lfx.graph.vertex.base import Vertex


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


__all__ = ["build_schema_from_inputs", "get_arg_names", "get_flow_inputs", "run_flow"]
