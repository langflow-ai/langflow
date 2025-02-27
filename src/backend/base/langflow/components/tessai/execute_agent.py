import json
from copy import deepcopy

import requests

from langflow.custom import Component
from langflow.inputs import BoolInput, DropdownInput, IntInput, MultilineInput, MultiselectInput, SecretStrInput, StrInput
from langflow.io import Output
from langflow.schema.message import Message

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

    BASE_URL = "https://tess.pareto.io/api"
    FIELD_SUFFIX = "_tess_ai_dynamic_field"
    CHAT_MESSAGE_INPUT_SUFFIX = "_tess_ai_chat_message_input"

    def execute_agent(self) -> str:
        headers = self._get_headers()
        execute_endpoint = f"{self.BASE_URL}/agents/{self.agent_id.strip()}/execute?waitExecution=true"
        attributes = self._collect_dynamic_attributes()

        try:
            response = requests.post(execute_endpoint, headers=headers, json=attributes)
            response.raise_for_status()
            execution_data = response.json()

            if execution_data["responses"][0]["status"] not in ["succeeded", "failed", "error"]:
                raise ValueError(json.dumps(execution_data))

            response_id = execution_data["responses"][0]["id"]
            return self._get_agent_response(headers, response_id)
        except requests.RequestException as e:
            error_json = e.response.json() if e.response is not None else {"error": str(e)}
            raise RuntimeError(json.dumps(error_json)) from e

    def update_build_config(self, build_config: dict, field_value: str, field_name: str|None = None) -> dict:
        if field_name == "agent_id" and field_value and build_config.get("api_key", {}).get("value"):
            try:
                agent = self._get_agent(field_value)
                old_build_config = deepcopy(dict(build_config))
                
                for key in list(build_config.keys()):
                    if key.endswith(self.FIELD_SUFFIX):
                        del build_config[key]
                
                questions = agent.get("questions", [])
                for question in questions:
                    name = question.get("name", "")
                    
                    if name == "messages" and agent.get("type") == "chat":
                        name += self.CHAT_MESSAGE_INPUT_SUFFIX
                    
                    key = name + self.FIELD_SUFFIX
                    old_config = old_build_config.get(key, {})
                    
                    field = self._create_field(key, question, old_config.get("value"))
                    config = field.model_dump(by_alias=True, exclude_none=True)
                    
                    self.inputs.append(field)
                    build_config[key] = config
                    
            except requests.RequestException:
                for key in list(build_config.keys()):
                    if key.endswith(self.FIELD_SUFFIX):
                        del build_config[key]

        self.map_inputs(self.inputs)
        self.build_inputs()

        return build_config

    def _get_headers(self) -> dict:
        return {"Authorization": f"Bearer {self.api_key}", "accept": "*/*", "Content-Type": "application/json"}

    def _get_agent(self, agent_id):
        endpoint = f"{self.BASE_URL}/agents/{agent_id}"
        response = requests.get(endpoint, headers=self._get_headers())

        if response.status_code not in [200, 404]:
            raise Exception(json.dumps(response.json()))

        return response.json()

    def _get_agent_response(self, headers: dict, response_id: str) -> str:
        endpoint = f"{self.BASE_URL}/agent-responses/{response_id}"
        try:
            response = requests.get(endpoint, headers=headers)
            response.raise_for_status()
            return response.json().get("output", "")
        except requests.RequestException as e:
            error_json = e.response.json() if e.response is not None else {"error": str(e)}
            raise RuntimeError(json.dumps(error_json)) from e

    def _create_field(self, key: str, question: dict, value: str|None = None) -> dict:
        field_type = question.get("type", "text")

        args = {
            "name": key,
            "display_name": question["name"],
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
            options = question.get("options", [])
            if all(isinstance(option, bool) for option in options):
                input_class = BoolInput
                if value:
                    args["value"] = value
                elif args["required"]:
                    args["value"] = args.get("default", options[0])
            else:
                input_class = DropdownInput
                args["options"] = [str(option) for option in options]
                if value and value in args["options"]:
                    args["value"] = value
                elif args["required"]:
                    args["value"] = args.get("default", args["options"][0])
        elif field_type == "number":
            input_class = IntInput
            args["input_types"] = ["Message"]
        elif field_type == "multiselect":
            input_class = MultiselectInput
            args["options"] = question.get("description", "").split(",")
            if value and isinstance(value, list):
                args["value"] = [val for val in value if val in args["options"]]
            else:
                args["value"] = []
        else:
            input_class = StrInput
            if field_type == "file":
                args["display_name"] += " (direct URL)"
            args["input_types"] = ["Message"]

        return input_class(**args)

    def _collect_dynamic_attributes(self) -> dict:
        attributes = {}
        suffix = self.FIELD_SUFFIX
        suffix_length = len(suffix)

        for key in self._attributes:
            if key.endswith(suffix):
                value = self._attributes[key]
                name = key[:-suffix_length]

                if isinstance(value, Message):
                    value = value.text

                if name.endswith(self.CHAT_MESSAGE_INPUT_SUFFIX):
                    name = name[:-len(self.CHAT_MESSAGE_INPUT_SUFFIX)]
                    attributes[name] = [{"role": "user", "content": value}]
                elif isinstance(value, list):
                    attributes[name] = ",".join(str(val) for val in value)
                elif value != "":
                    attributes[name] = value
        return attributes