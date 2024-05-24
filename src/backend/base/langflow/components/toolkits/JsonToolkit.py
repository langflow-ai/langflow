from pathlib import Path

import yaml
from langchain_community.agent_toolkits.json.toolkit import JsonToolkit
from langchain_community.tools.json.tool import JsonSpec

from langflow.custom import CustomComponent


class JsonToolkitComponent(CustomComponent):
    display_name = "JsonToolkit"
    description = "Toolkit for interacting with a JSON spec."

    def build_config(self):
        return {
            "path": {
                "display_name": "Path",
                "field_type": "file",
                "file_types": ["json", "yaml", "yml"],
            },
        }

    def build(self, path: str) -> JsonToolkit:
        if path.endswith("yaml") or path.endswith("yml"):
            yaml_dict = yaml.load(open(path, "r"), Loader=yaml.FullLoader)
            spec = JsonSpec(dict_=yaml_dict)
        else:
            spec = JsonSpec.from_file(Path(path))
        return JsonToolkit(spec=spec)
