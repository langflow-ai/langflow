from typing import cast

from lfx.custom import Component
from lfx.io import BoolInput, HandleInput, Output, StrInput
from lfx.schema.data import Data


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
            method="notify_components",
            cache=False,
        ),
    ]

    async def notify_components(self) -> Data:
        """Processes and stores a notification in the component's context.

        Normalizes the input value to a `Data` object and stores it under the
        specified context key. If `append` is True, adds the value to a list
        of notifications; otherwise, replaces the existing value. Updates the
        component's status and activates related state vertices in the graph.

        Returns:
            The processed `Data` object stored in the context.

        Raises:
            ValueError: If the component is not part of a graph.
        """
        if not self._vertex:
            msg = "Notify component must be used in a graph."
            raise ValueError(msg)
        input_value: Data | str | dict | None = self.input_value
        if input_value is None:
            input_value = Data(text="")
        elif not isinstance(input_value, Data):
            if isinstance(input_value, str):
                input_value = Data(text=input_value)
            elif isinstance(input_value, dict):
                input_value = Data(data=input_value)
            else:
                input_value = Data(text=str(input_value))
        if input_value:
            if self.append:
                current_data = self.ctx.get(self.context_key, [])
                if not isinstance(current_data, list):
                    current_data = [current_data]
                current_data.append(input_value)
                self.update_ctx({self.context_key: current_data})
            else:
                self.update_ctx({self.context_key: input_value})
            self.status = input_value
        else:
            self.status = "No record provided."
        self._vertex.is_state = True
        self.graph.activate_state_vertices(name=self.context_key, caller=self._id)
        return cast(Data, input_value)
