import requests
from langflow.custom import Component
from langflow.inputs import DictInput, SecretStrInput, StrInput
from langflow.io import Output

class TessAIExecuteAgentComponent(Component):
    display_name = "Execute Agent"
    description = "Executes a TessAI agent."
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
            required=True,
            info="The ID of the agent to execute.",
        ),
        DictInput(
            name="parameters",
            display_name="Parameters",
            required=True,
            info="The parameters for the agent execution.",
            is_list=True,
        ),
    ]
    
    outputs = [
        Output(display_name="Output", name="output", method="execute_agent")
    ]
    
    BASE_URL = "https://tess.pareto.io"
    
    def execute_agent(self) -> str:
        headers = self._get_headers()
        execute_endpoint = f"{self.BASE_URL}/api/agents/{self.agent_id}/execute?waitExecution=true"
        
        try:
            response = requests.post(execute_endpoint, headers=headers, json=self.parameters)
            response.raise_for_status()
            execution_data = response.json()

            if execution_data['responses'][0]['status'] not in ['succeeded', 'failed', 'error']:
                raise ValueError(f"Unexpected status: {execution_data.get('status', None)}")

            response_id = execution_data['responses'][0]['id']
            return self._get_agent_response(headers, response_id)
        except requests.RequestException as e:
            raise RuntimeError(f"Error executing agent: {str(e)}") from e

    def _get_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "accept": "*/*",
            "Content-Type": "application/json"
        }

    def _get_agent_response(self, headers: dict, response_id: str) -> str:
        endpoint = f"{self.BASE_URL}/api/agent-responses/{response_id}"
        try:
            response = requests.get(endpoint, headers=headers)
            response.raise_for_status()
            response_data = response.json()
            return response_data.get('output', '')
        except requests.RequestException as e:
            raise RuntimeError(f"Error getting agent response: {str(e)}") from e