from langflow.custom import CustomComponent
from langflow.schema import JSON


class NotifyComponent(CustomComponent):
    display_name = "Notify"
    description = "A component to generate a notification to Get Notified component."
    icon = "Notify"
    name = "Notify"
    beta: bool = True

    def build_config(self):
        return {
            "name": {"display_name": "Name", "info": "The name of the notification."},
            "data": {"display_name": "Data", "info": "The data to store."},
            "append": {
                "display_name": "Append",
                "info": "If True, the record will be appended to the notification.",
            },
        }

    def build(self, name: str, *, data: JSON | None = None, append: bool = False) -> JSON:
        if data and not isinstance(data, JSON):
            if isinstance(data, str):
                data = JSON(text=data)
            elif isinstance(data, dict):
                data = JSON(data=data)
            else:
                data = JSON(text=str(data))
        elif not data:
            data = JSON(text="")
        if data:
            if append:
                self.append_state(name, data)
            else:
                self.update_state(name, data)
        else:
            self.status = "No record provided."
        self.status = data
        self._set_successors_ids()
        return data

    def _set_successors_ids(self):
        self._vertex.is_state = True
        successors = self._vertex.graph.successor_map.get(self._vertex.id, [])
        return successors + self._vertex.graph.activated_vertices
