import uuid
from typing import Any, Optional

from langflow.interface.custom.custom_component import CustomComponent


class UUIDGeneratorComponent(CustomComponent):
    documentation: str = "http://docs.langflow.org/components/custom"
    display_name = "ID Generator"
    description = "Generates a unique ID."

    def update_build_config(
        self,
        build_config: dict,
        field_value: Any,
        field_name: Optional[str] = None,
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
