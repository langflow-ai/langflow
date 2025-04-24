import json

from langflow.custom import Component
from langflow.io import MultilineInput, Output
from langflow.schema import JSON


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

    def build_data(self) -> JSON:
        message: str | JSON = ""
        if not self.data:
            self.status = "No data provided."
            return JSON(data={})
        try:
            body = json.loads(self.data or "{}")
        except json.JSONDecodeError:
            body = {"payload": self.data}
            message = f"Invalid JSON payload. Please check the format.\n\n{self.data}"
        data = JSON(data=body)
        if not message:
            message = data
        self.status = message
        return data
