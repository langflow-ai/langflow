from pathlib import Path

import yaml
from langchain_community.agent_toolkits.openapi.toolkit import BaseToolkit, OpenAPIToolkit
from langchain_community.tools.json.tool import JsonSpec
from langchain_community.utilities.requests import TextRequestsWrapper

from langflow.custom import CustomComponent
from langflow.field_typing import BaseLanguageModel


class OpenAPIToolkitComponent(CustomComponent):
    display_name = "OpenAPIToolkit"
    description = "Toolkit for interacting with an OpenAPI API."

    def build_config(self):
        return {
            "json_agent": {"display_name": "JSON Agent"},
            "requests_wrapper": {"display_name": "Text Requests Wrapper"},
        }

    def build(self, llm: BaseLanguageModel, path: str, allow_dangerous_requests: bool = False) -> BaseToolkit:
        if path.endswith("yaml") or path.endswith("yml"):
            yaml_dict = yaml.load(open(path, "r"), Loader=yaml.FullLoader)
            spec = JsonSpec(dict_=yaml_dict)
        else:
            spec = JsonSpec.from_file(Path(path))
        requests_wrapper = TextRequestsWrapper()
        return OpenAPIToolkit.from_llm(
            llm=llm,
            json_spec=spec,
            requests_wrapper=requests_wrapper,
            allow_dangerous_requests=allow_dangerous_requests,
        )
