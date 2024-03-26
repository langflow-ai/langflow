from langchain_community.agent_toolkits.json.toolkit import JsonToolkit
from langchain_community.tools.json.tool import JsonSpec

from langflow.interface.custom.custom_component import CustomComponent


class JsonToolkitComponent(CustomComponent):
    display_name = "JsonToolkit"
    description = "Toolkit for interacting with a JSON spec."

    def build_config(self):
        return {
            "spec": {"display_name": "Spec", "type": JsonSpec},
        }

    def build(self, spec: JsonSpec) -> JsonToolkit:
        return JsonToolkit(spec=spec)
