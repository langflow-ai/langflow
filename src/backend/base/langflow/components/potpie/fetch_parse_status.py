import httpx

from langflow.custom import Component
from langflow.inputs import MessageTextInput
from langflow.io import SecretStrInput
from langflow.schema import Message
from langflow.template import Output


class FetchParseStatus(Component):
    display_name = "Fetch Parse Status"
    description = "Fetch the current status of parse repository task."
    documentation = "https://docs.potpie.ai"
    icon = "Potpie"

    inputs = [
        SecretStrInput(
            name="potpie_api_key",
            display_name="Potpie API Key",
            info="API Key from app.potpie.ai",
            required=True,
        ),
        MessageTextInput(
            name="project_id",
            display_name="ProjectID",
            info="ID of the project from Potpie.",
            required=True,
        ),
    ]

    outputs = [Output(display_name="Status", name="status", method="fetch_status")]

    def fetch_status(self) -> Message:
        endpoint = f"https://production-api.potpie.ai/api/v2/parsing-status/{self.project_id}"

        headers = {
            "X-API-Key": self.potpie_api_key,
            "Content-Type": "application/json",
        }

        try:
            response = httpx.get(endpoint, headers=headers, timeout=10000)
            response.raise_for_status()

            json = response.json()
            data = Message(text=json["status"])

        except httpx.HTTPStatusError as e:
            raise ValueError(e.response.text) from e

        return data
