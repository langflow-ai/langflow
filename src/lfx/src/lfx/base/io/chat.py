from lfx.custom.custom_component.component import Component


def _extract_model_name(value) -> str | None:
    """Extract model name from various formats.

    Handles:
    - String model name (e.g., "gpt-4o-mini")
    - ModelInput format: list of dicts with 'name' key (e.g., [{'name': 'gpt-4o', ...}])
    - Single dict with 'name' key
    """
    if isinstance(value, str):
        return value
    if isinstance(value, list) and value:
        # ModelInput format: list of model option dicts
        first_item = value[0]
        if isinstance(first_item, dict) and "name" in first_item:
            return first_item["name"]
    if isinstance(value, dict) and "name" in value:
        return value["name"]
    return None


class ChatComponent(Component):
    display_name = "Chat Component"
    description = "Use as base for chat components."

    def get_properties_from_source_component(self):
        vertex = self.get_vertex()
        if vertex and hasattr(vertex, "incoming_edges") and vertex.incoming_edges:
            source_id = vertex.incoming_edges[0].source_id
            source_vertex = self.graph.get_vertex(source_id)
            component = source_vertex.custom_component
            source = component.display_name
            icon = component.icon
            possible_attributes = ["model_name", "model_id", "model"]
            for attribute in possible_attributes:
                if hasattr(component, attribute):
                    attr_value = getattr(component, attribute)
                    if attr_value:
                        model_name = _extract_model_name(attr_value)
                        if model_name:
                            return model_name, icon, source, component.get_id()
            return source, icon, component.display_name, component.get_id()
        return None, None, None, None
