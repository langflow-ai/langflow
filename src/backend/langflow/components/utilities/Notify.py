from typing import Optional

from langflow import CustomComponent
from langflow.schema import Record


class NotifyComponent(CustomComponent):
    display_name = "Notify"
    description = "A component to generate a notification to Get Notified component."

    def build_config(self):
        return {
            "name": {"display_name": "Name", "info": "The name of the notification."},
            "record": {"display_name": "Record", "info": "The record to store."},
            "append": {
                "display_name": "Append",
                "info": "If True, the record will be appended to the notification.",
            },
        }

    def build(
        self, name: str, record: Optional[Record] = None, append: bool = False
    ) -> Record:
        if state and not isinstance(state, Record):
            if isinstance(state, str):
                state = Record(text=state)
            elif isinstance(state, dict):
                state = Record(data=state)
            else:
                state = Record(text=str(state))
        elif not state:
            state = Record(text="")
        if record:
            if append:
                self.append_state(name, record)
            else:
                self.update_state(name, record)
        else:
            state = "No record provided."
        self.status = state
