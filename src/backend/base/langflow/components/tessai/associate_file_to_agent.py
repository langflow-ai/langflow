import requests
from langflow.custom import Component
from langflow.inputs import SecretStrInput, StrInput
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
        ),
        StrInput(
            name="agent_id",
            display_name="Agent ID",
            info="The ID of the agent to associate the file with.",
            required=True,
        ),
        StrInput(
            name="file_id",
            display_name="File ID",
            info="The ID of the file to associate with the agent.",
            required=True,
        ),
    ]
    
    outputs = [
        Output(display_name="Association Result", name="association_result", method="associate_file_to_agent")
    ]
    
    BASE_URL = "https://tess.pareto.io"
    
    def associate_file_to_agent(self) -> Data:
        headers = self._get_headers()
        endpoint = f"{self.BASE_URL}/api/agents/{self.agent_id}/files?waitExecution=True"

        try:
            payload = {
                "file_ids": [int(self.file_id)]
            }
            
            response = requests.post(endpoint, headers=headers, json=payload)
            response.raise_for_status()
            result = response.json()
            
            return Data(data=result)
        except requests.RequestException as e:
            raise RuntimeError(f"Error associating file to agent: {str(e)}") from e

    def _get_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }