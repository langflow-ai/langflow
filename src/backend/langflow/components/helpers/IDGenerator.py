import uuid
from typing import Any, Text

from langflow import CustomComponent


class UUIDGeneratorComponent(CustomComponent):
    documentation: str = "http://docs.langflow.org/components/custom"
    display_name = "Unique ID Generator"
    description = "Generates a unique ID."

    def update_build_config(
        self, build_config: dict, field_name: Text, field_value: Any
    ):
        if field_name == "unique_id":
            build_config[field_name]["value"] = str(uuid.uuid4())
        return build_config

    def build_config(self):
        return {
            "unique_id": {
                "display_name": "Value",
                "refresh": True,
            }
        }

    def build(self, unique_id: str) -> str:
        return unique_id
