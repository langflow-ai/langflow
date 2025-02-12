import time

import httpx

from langflow.custom import Component
from langflow.inputs import MessageTextInput
from langflow.io import SecretStrInput
from langflow.schema import Message
from langflow.template import Output


class ParseRepository(Component):
    display_name = "Parse Repository"
    description = "Parses a github repository and stores the knowledge graph in potpie."
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

    def get_status(self, project_id: str) -> str:
        endpoint = f"https://production-api.potpie.ai/api/v2/parsing-status/{project_id}"

        headers = {
            "X-API-Key": self.potpie_api_key,
            "Content-Type": "application/json",
        }

        try:
            response = httpx.get(endpoint, headers=headers, timeout=10000)
            response.raise_for_status()

            json = response.json()
            status: str = json["status"]

        except httpx.HTTPStatusError as e:
            raise ValueError(e.response.text) from e

        return status

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
            project_id: str = json["project_id"]

        except httpx.HTTPStatusError as e:
            raise ValueError(e.response.text) from e

        # Wait for status change
        status_res = "ready"

        while True:
            status = self.get_status(project_id)
            if status in ("ready", "error"):
                status_res = status
                break
            time.sleep(10)

        return Message(text=project_id, status=status_res)
