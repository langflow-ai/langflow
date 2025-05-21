import json

from langflow.custom import Component
from langflow.io import MultilineInput, Output
from langflow.schema import Data


class WebhookComponent(Component):
    display_name = "Webhook"
    name = "Webhook"
    icon = "webhook"

    inputs = [
        MultilineInput(
            name="data",
            display_name="Payload",
            info="Receives a payload from external systems via HTTP POST.",
            advanced=True,
        ),
        MultilineInput(
            name="curl",
            display_name="cURL",
            value="CURL_WEBHOOK",
            advanced=True,
            input_types=[],
        ),
        MultilineInput(
            name="endpoint",
            display_name="Endpoint",
            value="BACKEND_URL",
            advanced=False,
            copy_field=True,
            input_types=[],
        ),
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
            my_data = self.data.replace('"\n"', '"\\n"')
            body = json.loads(my_data or "{}")
        except json.JSONDecodeError:
            body = {"payload": self.data}
            message = f"Invalid JSON payload. Please check the format.\n\n{self.data}"
        data = Data(data=body)
        if not message:
            message = data
        self.status = message
        return data
