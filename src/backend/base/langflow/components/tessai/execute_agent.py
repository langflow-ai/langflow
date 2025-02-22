import requests

from langflow.custom import Component
from langflow.inputs import SecretStrInput, StrInput
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
    FIELD_SUFFIX = "tess_ai_dynamic_field"

    def execute_agent(self) -> str:
        headers = self._get_headers()
        execute_endpoint = f"{self.BASE_URL}/api/agents/{self.agent_id}/execute?waitExecution=true"

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
        for attr_name in dir(self):
            if attr_name.endswith(suffix):
                param_name = attr_name[: -len(suffix)]
                parameters[param_name] = getattr(self, attr_name)
        return parameters

    def update_build_config(self, build_config: dict, field_value: str, field_name: str | None = None) -> dict:
        if field_name == "agent_id" and field_value and build_config.get("api_key", {}).get("value"):
            print(f"Updating build config for agent {field_value}")
            try:
                for key in list(build_config.keys()):
                    if key.endswith(self.FIELD_SUFFIX):
                        del build_config[key]

                endpoint = f"{self.BASE_URL}/api/agents/{field_value}"
                response = requests.get(endpoint, headers=self._get_headers())
                response.raise_for_status()
                template = response.json()
                questions = template.get("questions", [])

                for question in questions:
                    key = f"{question['name']}{self.FIELD_SUFFIX}"
                    config = self._create_field_config(question)
                    print(f"Creating field config for question {question['name']}")
                    build_config[key] = config

            except requests.RequestException:
                self._clear_dynamic_fields(build_config)

        return build_config

    def _create_field_config(self, question: dict) -> dict:
        field_type = question.get("type", "text")
        common = {
            "required": question.get("required", False),
            "placeholder": question.get("placeholder", ""),
            "show": True,
            "name": question["name"],
            "value": question.get("default", ""),
            "display_name": question["name"].replace("_", " ").capitalize(),
            "advanced": False,
            "dynamic": False,
            "info": question.get("description", ""),
        }

        if field_type == "textarea":
            return {
                **common,
                "tool_mode": False,
                "trace_as_input": True,
                "multiline": True,
                "trace_as_metadata": True,
                "load_from_db": False,
                "list": False,
                "list_add_label": "Add More",
                "input_types": ["Message"],
                "real_time_refresh": True,
                "title_case": False,
                "type": "str",
                "_input_type": "MultilineInput",
            }
        if field_type == "select":
            return {
                **common,
                "tool_mode": False,
                "trace_as_metadata": True,
                "options": [opt.split(":")[-1] for opt in question.get("options", [])],
                "combobox": False,
                "type": "str",
                "_input_type": "DropdownInput",
            }
        if field_type == "multiselect":
            return {
                **common,
                "tool_mode": False,
                "trace_as_metadata": True,
                "options": [opt.split(":")[-1].strip() for opt in question.get("description", "").split(",")],
                "combobox": False,
                "list": True,
                "list_add_label": "Add More",
                "type": "list",
                "_input_type": "MultiselectInput",
            }
        if field_type == "file":
            return {
                **common,
                "trace_as_metadata": True,
                "file_path": "",
                "fileTypes": [
                    "pdf",
                    "docx",
                    "txt",
                    "csv",
                    "xlsx",
                    "xls",
                    "ppt",
                    "pptx",
                    "png",
                    "jpg",
                    "jpeg",
                    "gif",
                    "bmp",
                    "tiff",
                    "ico",
                    "webp",
                ],
                "list": False,
                "title_case": False,
                "type": "file",
                "_input_type": "FileInput",
            }
        return {
            **common,
            "tool_mode": False,
            "trace_as_input": True,
            "input_types": ["Message"],
            "real_time_refresh": True,
            "title_case": False,
            "type": "str",
            "_input_type": "Input",
        }

    def _clear_dynamic_fields(self, build_config: dict):
        for key in list(build_config.keys()):
            if key.endswith(self.FIELD_SUFFIX):
                print(f"Clearing dynamic field {key}")
                del build_config[key]
