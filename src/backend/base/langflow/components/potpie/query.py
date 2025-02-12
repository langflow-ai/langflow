import httpx

from langflow.custom import Component
from langflow.inputs import MessageTextInput
from langflow.io import SecretStrInput
from langflow.schema import Data
from langflow.template import Output


class Query(Component):
    display_name = "Query Repository"
    description = "Queries a parsed project with a context rich ai agent."
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
        MessageTextInput(
            name="message_content",
            display_name="Message Content",
            info="The message content for the agent to query the project with.",
            placeholder="Example: What is the purpose of this project?",
            required=True,
        ),
    ]

    outputs = [
        Output(display_name="Agent Response", name="agent_response", method="run_query"),
    ]

    def run_query(self) -> Data:
        endpoint = f"https://production-api.potpie.ai/api/v2/project/{self.project_id}/message"
        headers = {
            "X-API-Key": self.potpie_api_key,
            "Content-Type": "application/json",
        }

        payload = {
            "message": self.message_content,
            "node_ids": [],
        }

        try:
            response = httpx.post(endpoint, headers=headers, json=payload, timeout=10000)
            response.raise_for_status()
            res = response.json()
            data = Data(response=res["message"])
        except httpx.HTTPStatusError as e:
            raise ValueError(e.response.text) from e

        return data
