from langflow.custom import Component


class ChatComponent(Component):
    display_name = "Chat Component"
    description = "Use as base for chat components."

    def get_properties_from_source_component(self):
        if hasattr(self, "_vertex") and hasattr(self._vertex, "incoming_edges") and self._vertex.incoming_edges:
            source_id = self._vertex.incoming_edges[0].source_id
            source_vertex = self.graph.get_vertex(source_id)
            component = source_vertex.custom_component
            source = component.display_name
            icon = component.icon
            possible_attributes = ["model_name", "model_id", "model"]
            for attribute in possible_attributes:
                if hasattr(component, attribute) and getattr(component, attribute):
                    return getattr(component, attribute), icon, source, component._id
            return source, icon, component.display_name, component._id
        return None, None, None, None
