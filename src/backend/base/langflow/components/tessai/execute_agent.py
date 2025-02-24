import requests
from langflow.custom import Component
from langflow.inputs import DropdownInput, MultilineInput, MultiselectInput, SecretStrInput, StrInput
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
            real_time_refresh=True,
        ),
    ]

    outputs = [Output(display_name="Output", name="output", method="execute_agent")]

    BASE_URL = "https://tess.pareto.io"
    FIELD_SUFFIX = "_tess_ai_dynamic_field"

    def execute_agent(self) -> str:
        headers = self._get_headers()
        execute_endpoint = f"{self.BASE_URL}/api/agents/{self.agent_id.strip()}/execute?waitExecution=true"

        parameters = self._collect_dynamic_parameters()

        try:
            response = requests.post(execute_endpoint, headers=headers, json=parameters)
            response.raise_for_status()
            execution_data = response.json()

            if execution_data["responses"][0]["status"] not in ["succeeded", "failed", "error"]:
                raise ValueError(f"Unexpected status: {execution_data.get('status', None)}")

            response_id = execution_data["responses"][0]["id"]
            return self._get_agent_response(headers, response_id)
        except requests.RequestException as e:
            raise RuntimeError(f"Error executing agent: {e!s}") from e

    def update_build_config(self, build_config: dict, field_value: str, field_name: str | None = None) -> dict:
        print(dir(self.api_key))
        if field_name == "agent_id" and field_value and build_config.get("api_key", {}).get("value"):
            try:
                for key in list(build_config.keys()):
                    if key.endswith(self.FIELD_SUFFIX):
                        del build_config[key]

                questions = self._get_agent_questions(field_value)

                for question in questions:
                    config = self._create_field_config(question)
                    build_config[config.name] = config

            except requests.RequestException:
                self._clear_dynamic_fields(build_config)

        return build_config

    def _get_headers(self) -> dict:
        return {"Authorization": f"Bearer {self.api_key}", "accept": "*/*", "Content-Type": "application/json"}

    def _get_agent_response(self, headers: dict, response_id: str) -> str:
        endpoint = f"{self.BASE_URL}/api/agent-responses/{response_id}"
        try:
            response = requests.get(endpoint, headers=headers)
            response.raise_for_status()
            return response.json().get("output", "")
        except requests.RequestException as e:
            raise RuntimeError(f"Error getting agent response: {e!s}") from e

    def _collect_dynamic_parameters(self) -> dict:
        parameters = {}
        suffix = self.FIELD_SUFFIX
        for key in self._parameters:
            if key.endswith(suffix):
                param_name = key[: -len(suffix)]
                if param_name == "messages":
                    parameters[param_name] = [{
                        "role": "user",
                        "content": self._parameters[key]
                    }]
                else:
                    parameters[param_name] = self._parameters[key]
        return parameters
    
    def _get_agent_questions(self, agent_id):
        endpoint = f"{self.BASE_URL}/api/agents/{agent_id}"
        response = requests.get(endpoint, headers=self._get_headers())
        
        if response.status_code == 404:
            return []
        elif response.status_code != 200:
            raise Exception(f"Error getting information for agent {agent_id}: {response.status_code}")
        
        template = response.json()
        return template.get("questions", [])

    def _create_field_config(self, question: dict) -> dict:
        field_type = question.get("type", "text")
        key = f"{question['name']}{self.FIELD_SUFFIX}"
        name = question["name"].replace("_", " ").capitalize()
    
        args = {
            "name": key,
            "display_name": name,
            "required": question.get("required", False),
            "info": question.get("description", ""),
            "placeholder": question.get("placeholder", ""),
        }
    
        if field_type == "textarea":
            input_class = MultilineInput
        elif field_type == "select":
            input_class = DropdownInput
            args["options"] = [opt.split(":")[-1] for opt in question.get("options", [])]
        elif field_type == "multiselect":
            input_class = MultiselectInput
            args["options"] = [opt.split(":")[-1].strip() for opt in question.get("description", "").split(",")]
        else:
            input_class = StrInput
            if field_type == "file":
                args["display_name"] += " (direct URL)"
            args["input_types"] = ["Message"]
    
        return input_class(**args)

    def _clear_dynamic_fields(self, build_config: dict):
        for key in list(build_config.keys()):
            if key.endswith(self.FIELD_SUFFIX):
                del build_config[key]