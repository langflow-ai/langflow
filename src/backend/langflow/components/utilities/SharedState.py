from typing import Union

from langflow import CustomComponent
from langflow.field_typing import Text
from langflow.schema import Record


class SharedState(CustomComponent):
    display_name = "Shared State"
    description = "A component to share state between components."

    def build_config(self):
        return {
            "name": {"display_name": "Name", "info": "The name of the state."},
            "record": {"display_name": "Record", "info": "The record to store."},
            "append": {
                "display_name": "Append",
                "info": "If True, the record will be appended to the state.",
            },
        }

    def build(
        self, name: str, record: Union[Text, Record], append: bool = False
    ) -> Record:
        if append:
            self.append_state(name, record)
        else:
            self.update_state(name, record)

        state = self.get_state(name)
        if not isinstance(state, Record):
            if isinstance(state, str):
                state = Record(text=state)
            elif isinstance(state, dict):
                state = Record(data=state)
            else:
                state = Record(text=str(state))
        return state
