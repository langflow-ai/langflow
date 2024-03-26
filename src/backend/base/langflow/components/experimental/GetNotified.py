from langflow.interface.custom.custom_component import CustomComponent
from langflow.schema import Record


class GetNotifiedComponent(CustomComponent):
    display_name = "Get Notified"
    description = "A component to get notified by Notify component."
    beta: bool = True

    def build_config(self):
        return {
            "name": {
                "display_name": "Name",
                "info": "The name of the notification to listen for.",
            },
        }

    def build(self, name: str) -> Record:
        state = self.get_state(name)
        self.status = state
        return state
