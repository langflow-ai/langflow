from langflow.custom.custom_component.custom_component import CustomComponent
from langflow.schema.data import Data


class ListenComponent(CustomComponent):
    display_name = "Listen"
    description = "A component to listen for a notification."
    name = "Listen"
    beta: bool = True
    icon = "Radio"

    def build_config(self):
        return {
            "name": {
                "display_name": "Name",
                "info": "The name of the notification to listen for.",
            },
        }

    def build(self, name: str) -> Data:
        state = self.get_state(name)
        self._set_successors_ids()
        self.status = state
        return state

    def _set_successors_ids(self):
        self._vertex.is_state = True
        successors = self._vertex.graph.successor_map.get(self._vertex.id, [])
        return successors + self._vertex.graph.activated_vertices
