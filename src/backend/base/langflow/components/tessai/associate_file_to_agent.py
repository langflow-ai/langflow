import requests

from langflow.custom import Component
from langflow.inputs import DataInput, SecretStrInput, StrInput
from langflow.io import Output
from langflow.schema import Data


class TessAIAssociateFileToAgentComponent(Component):
    display_name = "Associate File to Agent"
    description = "Associates a file with an agent in the TessAI platform."
    documentation = "https://docs.tess.pareto.io/"
    icon = "TessAI"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="Tess AI API Key",
            info="The API key to use for TessAI.",
            advanced=False,
            input_types=[]
        ),
        StrInput(
            name="agent_id",
            display_name="User-Owned Agent ID",
            info="The ID of an agent you created in the Tess AI platform.",
            required=True,
        ),
        DataInput(
            name="files",
            display_name="File(s)",
            info="The file(s) to associate with the agent.",
            required=True,
            is_list=True
        ),
    ]

    outputs = [Output(display_name="Association Result", name="association_result", method="associate_file_to_agent")]

    BASE_URL = "https://tess.pareto.io/api"

    def associate_file_to_agent(self) -> Data:
        headers = self._get_headers()
        endpoint = f"{self.BASE_URL}/agents/{self.agent_id}/files?waitExecution=True"

        try:
            payload = {"file_ids": [int(file.data["id"]) for file in self.files]}

            response = requests.post(endpoint, headers=headers, json=payload)
            response.raise_for_status()
            result = response.json()

            return Data(data=result)
        except requests.RequestException as e:
            raise RuntimeError(f"Error associating file to agent: {e!s}") from e

    def _get_headers(self) -> dict:
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}