import uuid
from typing import Any, Optional

from langflow.custom import CustomComponent
from langflow.schema.dotdict import dotdict


class IDGeneratorComponent(CustomComponent):
    display_name = "ID Generator"
    description = "Generates a unique ID."
    name = "IDGenerator"

    def update_build_config(  # type: ignore
        self, build_config: dotdict, field_value: Any, field_name: Optional[str] = None
    ):
        if field_name == "unique_id":
            build_config[field_name]["value"] = str(uuid.uuid4())
        return build_config

    def build_config(self):
        return {
            "unique_id": {
                "display_name": "Value",
                "refresh_button": True,
            }
        }

    def build(self, unique_id: str) -> str:
        return unique_id
