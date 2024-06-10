import os
from langflow.custom import CustomComponent


class GetEnvVar(CustomComponent):
    display_name = "Get env var"
    description = "Get env var"
    icon = "custom_components"

    def build_config(self):
        return {"env_var_name": {"display_name": "Env var name"}}

    def build(self, env_var_name: str) -> str:
        return os.environ[env_var_name]
