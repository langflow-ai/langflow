import json
import requests
from copy import deepcopy
from langflow.custom import Component
from langflow.inputs import DropdownInput, FileInput, MultilineInput, MultiselectInput, SecretStrInput, StrInput
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
                raise ValueError(json.dumps(execution_data))
    
            response_id = execution_data["responses"][0]["id"]
            return self._get_agent_response(headers, response_id)
        except requests.RequestException as e:
            error_json = e.response.json() if e.response is not None else {"error": str(e)}
            raise RuntimeError(json.dumps(error_json)) from e


    def update_build_config(self, build_config: dict, field_value: str, field_name: str | None = None) -> dict:
        if field_name == "agent_id" and field_value and build_config.get("api_key", {}).get("value"):
            try:
                questions = self._get_agent_questions(field_value)
                self._update_dynamic_fields(build_config, questions)
            except requests.RequestException:
                self._clear_dynamic_fields(build_config)

        self.map_inputs(self.inputs)
        self.build_inputs()

        return build_config

    def _get_headers(self) -> dict:
        return {"Authorization": f"Bearer {self.api_key}", "accept": "*/*", "Content-Type": "application/json"}
    
    def _get_agent_questions(self, agent_id):
        endpoint = f"{self.BASE_URL}/api/agents/{agent_id}"
        response = requests.get(endpoint, headers=self._get_headers())

        if response.status_code not in [200, 404]:
            raise Exception(json.dumps(response.json()))

        
        template = response.json()
        return template.get("questions", [])

    def _update_dynamic_fields(self, build_config: dict, questions: list[dict]):
        old_build_config = deepcopy(dict(build_config))

        for key in list(build_config.keys()):
            if key.endswith(self.FIELD_SUFFIX):
                del build_config[key]

        for question in questions:
            key = f"{question['name']}{self.FIELD_SUFFIX}"
            old_config = old_build_config.get(key, {})
            field = self._create_field(key, question, old_config.get("value"))
            config = field.model_dump(by_alias=True, exclude_none=True)

            self.inputs.append(field)
            build_config[key] = config

    def _get_agent_response(self, headers: dict, response_id: str) -> str:
        endpoint = f"{self.BASE_URL}/api/agent-responses/{response_id}"
        try:
            response = requests.get(endpoint, headers=headers)
            response.raise_for_status()
            return response.json().get("output", "")
        except requests.RequestException as e:
            error_json = e.response.json() if e.response is not None else {"error": str(e)}
            raise RuntimeError(json.dumps(error_json)) from e

    def _create_field(self, key: str, question: dict, value: str | None = None) -> dict:
        field_type = question.get("type", "text")
        name = question["name"].replace("_", " ").capitalize()
    
        args = {
            "name": key,
            "display_name": name,
            "required": question.get("required", False),
            "info": question.get("description", ""),
            "placeholder": question.get("placeholder", ""),
        }
        
        if value:
            args["value"] = value
        elif question.get("default"):
            args["value"] = question.get("default")
    
        if field_type == "textarea":
            input_class = MultilineInput
        elif field_type == "select":
            input_class = DropdownInput
            args["options"] = question.get("options", [])
            if value and value in args["options"]:
                args["value"] = value
            elif args["required"]:
                args["value"] = args.get("default", args["options"][0])
        elif field_type == "multiselect":
            input_class = MultiselectInput
            args["options"] = [opt.split(":")[-1].strip() for opt in question.get("description", "").strip().split(",")]
            if value:
                args["value"] = [val for val in value.split(",") if val in args["options"]]
            else:
                args["value"] = []
        elif field_type == "file":
            input_class = FileInput
            args["file_path"] = ""
            args["fileTypes"] = ['pdf', 'docx', 'txt', 'csv', 'xlsx', 'xls', 'ppt', 'pptx', 
                             'png', 'jpg', 'jpeg', 'gif', 'bmp', 'tiff', 'ico', 'webp']
        else:
            input_class = StrInput
            args["input_types"] = ["Message"]
    
        return input_class(**args)

    def _clear_dynamic_fields(self, build_config: dict):
        for key in list(build_config.keys()):
            if key.endswith(self.FIELD_SUFFIX):
                del build_config[key]

    def _collect_dynamic_parameters(self) -> dict:
        parameters = {}
        suffix = self.FIELD_SUFFIX
        suffix_length = len(suffix)

        for key in self._parameters:
            if key.endswith(suffix):
                param_name = key[: -suffix_length]
                value = self._parameters[key]

                if param_name == "messages":
                    parameters[param_name] = [{
                        "role": "user",
                        "content": value
                    }]
                elif isinstance(value, list):
                    parameters[param_name] = ','.join(value)
                else:
                    parameters[param_name] = value
        return parameters