import os
from langflow.custom import CustomComponent


class GetEnvVar(CustomComponent):
    display_name = "Get env var"
    description = "Get env var"
    icon = "custom_components"

    def build_config(self):
        return {"param": {"display_name": "Env var name"}}

    def build(self, param: str) -> str:
        return os.environ[param]
