from langflow import CustomComponent
from langflow.field_typing import Tool
from langchain_community.tools.json.tool import JsonSpec
from langchain_community.agent_toolkits.json.toolkit import JsonToolkit


class JsonToolkitComponent(CustomComponent):
    display_name = "JsonToolkit"
    description = "Toolkit for interacting with a JSON spec."

    def build_config(self):
        return {
            "spec": {"display_name": "Spec", "type": JsonSpec},
        }

    def build(self, spec: JsonSpec) -> Tool:
        # Assuming JsonToolkit is the class that should be instantiated with the spec
        # The actual class name should be used in place of JsonToolkit if it is different
        return JsonToolkit(spec=spec)  # Replace JsonToolkit with the actual class name if necessary
