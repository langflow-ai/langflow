import httpx

from langflow.custom import Component
from langflow.inputs import MessageTextInput
from langflow.io import SecretStrInput
from langflow.schema import Message
from langflow.template import Output


class ParseRepositoryAsync(Component):
    display_name = "Parse Repository Async"
    description = "Parses a github repository asynchronously and stores the knowledge graph in potpie."
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
            name="repo_name",
            display_name="Repository Name",
            info="From github (e.g. 'langflow-ai/langflow')",
            required=True,
        ),
        MessageTextInput(
            name="branch_name",
            display_name="Branch Name",
            info="Name of the branch to parse.",
            placeholder="main",
            required=True,
        ),
    ]

    outputs = [
        Output(display_name="Project ID", name="project_id", method="parse_repo"),
    ]

    def parse_repo(self) -> Message:
        endpoint = "https://production-api.potpie.ai/api/v2/parse"

        headers = {
            "X-API-Key": self.potpie_api_key,
            "Content-Type": "application/json",
        }

        payload = {
            "repo_name": self.repo_name,
            "branch_name": self.branch_name,
        }

        try:
            response = httpx.post(endpoint, headers=headers, json=payload, timeout=10000)
            response.raise_for_status()

            json = response.json()
            data = Message(text=json["project_id"])

        except httpx.HTTPStatusError as e:
            raise ValueError(e.response.text) from e

        return data
