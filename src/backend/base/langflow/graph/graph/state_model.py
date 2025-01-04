import re

from langflow.graph.state.model import create_state_model
from langflow.helpers.base_model import BaseModel


def camel_to_snake(camel_str: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", camel_str).lower()


def create_state_model_from_graph(graph: BaseModel) -> type[BaseModel]:
    """Create a Pydantic state model from a graph representation.

    This function generates a Pydantic model that represents the state of an entire graph.
    It creates getter methods for each vertex in the graph, allowing access to the state
    of individual components within the graph structure.

    Args:
        graph (BaseModel): The graph object from which to create the state model.
            This should be a Pydantic model representing the graph structure,
            with a 'vertices' attribute containing all graph vertices.

    Returns:
        type[BaseModel]: A dynamically created Pydantic model class representing
            the state of the entire graph. This model will have properties
            corresponding to each vertex in the graph, with names converted from
            the vertex IDs to snake case.

    Raises:
        ValueError: If any vertex in the graph does not have a properly initialized
            component instance (i.e., if vertex.custom_component is None).

    Notes:
        - Each vertex in the graph must have a 'custom_component' attribute.
        - The 'custom_component' must have a 'get_state_model_instance_getter' method.
        - Vertex IDs are converted from camel case to snake case for the resulting model's field names.
        - The resulting model uses the 'create_state_model' function with validation disabled.

    Example:
        >>> class Vertex(BaseModel):
        ...     id: str
        ...     custom_component: Any
        >>> class Graph(BaseModel):
        ...     vertices: List[Vertex]
        >>> # Assume proper setup of vertices and components
        >>> graph = Graph(vertices=[...])
        >>> GraphStateModel = create_state_model_from_graph(graph)
        >>> graph_state = GraphStateModel()
        >>> # Access component states, e.g.:
        >>> print(graph_state.some_component_name)
    """
    for vertex in graph.vertices:
        if hasattr(vertex, "custom_component") and vertex.custom_component is None:
            msg = f"Vertex {vertex.id} does not have a component instance."
            raise ValueError(msg)

    state_model_getters = [
        vertex.custom_component.get_state_model_instance_getter()
        for vertex in graph.vertices
        if hasattr(vertex, "custom_component") and hasattr(vertex.custom_component, "get_state_model_instance_getter")
    ]
    fields = {
        camel_to_snake(vertex.id): state_model_getter
        for vertex, state_model_getter in zip(graph.vertices, state_model_getters, strict=False)
    }
    return create_state_model(model_name="GraphStateModel", validate=False, **fields)
