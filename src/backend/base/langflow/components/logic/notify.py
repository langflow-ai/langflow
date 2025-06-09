from langflow.custom import Component
from langflow.io import BoolInput, HandleInput, Output, StrInput
from langflow.schema.data import Data


class NotifyComponent(Component):
    display_name = "Notify"
    description = "A component to generate a notification to Get Notified component."
    icon = "Notify"
    name = "Notify"
    beta: bool = True

    inputs = [
        StrInput(
            name="context_key",
            display_name="Context Key",
            info="The key of the context to store the notification.",
            required=True,
        ),
        HandleInput(
            name="input_value",
            display_name="Input Data",
            info="The data to store.",
            required=False,
            input_types=["Data", "Message", "DataFrame"],
        ),
        BoolInput(
            name="append",
            display_name="Append",
            info="If True, the record will be appended to the notification.",
            value=False,
            required=False,
        ),
    ]

    outputs = [
        Output(
            display_name="Data",
            name="result",
            method="build",
            cache=False,
        ),
    ]

    async def build(self) -> Data:
        """Processes and stores a notification in the context, optionally appending to existing records.

        If `append` is True, adds the input value to a list of notifications under the specified context key; otherwise, replaces the existing value. Converts input values to `Data` objects as needed and updates the component's status and state. Returns the processed `Data` object.
        """
        if self.input_value and not isinstance(self.input_value, Data):
            if isinstance(self.input_value, str):
                self.input_value = Data(text=self.input_value)
            elif isinstance(self.input_value, dict):
                self.input_value = Data(data=self.input_value)
            else:
                self.input_value = Data(text=str(self.input_value))
        elif not self.input_value:
            self.input_value = Data(text="")
        if self.input_value:
            if self.append:
                current_data = self.ctx.get(self.context_key, [])
                if not isinstance(current_data, list):
                    current_data = [current_data]
                current_data.append(self.input_value)
                self.update_ctx({self.context_key: current_data})
            else:
                self.update_ctx({self.context_key: self.input_value})
        else:
            self.status = "No record provided."
        self.status = self.input_value
        self._vertex.is_state = True
        self.graph.activate_state_vertices(name=self.context_key, caller=self._id)
        return self.input_value
