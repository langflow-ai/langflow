import re

from langflow.graph.state.model import create_state_model


def camel_to_snake(camel_str: str) -> str:
    snake_str = re.sub(r"(?<!^)(?=[A-Z])", "_", camel_str).lower()
    return snake_str


def create_state_model_from_graph(graph):
    for vertex in graph.vertices:
        if hasattr(vertex, "_custom_component") and vertex._custom_component is None:
            raise ValueError(f"Vertex {vertex.id} does not have a component instance.")

    state_model_getters = [
        vertex._custom_component.get_state_model_instance_getter()
        for vertex in graph.vertices
        if hasattr(vertex, "_custom_component") and hasattr(vertex._custom_component, "get_state_model_instance_getter")
    ]
    fields = {
        camel_to_snake(vertex.id): state_model_getter
        for vertex, state_model_getter in zip(graph.vertices, state_model_getters)
    }
    return create_state_model(model_name="GraphStateModel", **fields)
