from langflow.custom import CustomComponent
from langflow.schema import Record


class ListenComponent(CustomComponent):
    display_name = "Listen"
    description = "A component to listen for a notification."
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
