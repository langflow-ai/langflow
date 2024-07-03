import json

from langflow.custom import Component
from langflow.io import MultilineInput, Output
from langflow.schema import Data


class WebhookComponent(Component):
    display_name = "Webhook Input"
    description = "Defines a webhook input for the flow."
    name = "Webhook"

    inputs = [
        MultilineInput(
            name="data",
            display_name="Data",
            info="Use this field to quickly test the webhook component by providing a JSON payload.",
        )
    ]
    outputs = [
        Output(display_name="Data", name="output_data", method="build_data"),
    ]

    def build_data(self) -> Data:
        message: str | Data = ""
        if not self.data:
            self.status = "No data provided."
            return Data(data={})
        try:
            body = json.loads(self.data or "{}")
        except json.JSONDecodeError:
            body = {"payload": self.data}
            message = f"Invalid JSON payload. Please check the format.\n\n{self.data}"
        data = Data(data=body)
        if not message:
            message = data
        self.status = message
        return data
