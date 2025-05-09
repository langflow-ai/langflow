from langflow.custom import Component
from langflow.io import BoolInput, HandleInput, Output, StrInput
from langflow.schema import Data


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
        if self.input_data and not isinstance(self.input_data, Data):
            if isinstance(self.input_data, str):
                self.input_data = Data(text=self.input_data)
            elif isinstance(self.input_data, dict):
                self.input_data = Data(data=self.input_data)
            else:
                self.input_data = Data(text=str(self.input_data))
        elif not self.input_data:
            self.input_data = Data(text="")
        if self.input_data:
            if self.append:
                current_data = self.ctx.get(self.context_key, [])
                if not isinstance(current_data, list):
                    current_data = [current_data]
                current_data.append(self.input_data)
                self.update_ctx({self.context_key: current_data})
            else:
                self.update_ctx({self.context_key: self.input_data})
        else:
            self.status = "No record provided."
        self.status = self.input_data
        self._vertex.is_state = True
        self.graph.activate_state_vertices(name=self.context_key, caller=self._id)
        return self.input_data
