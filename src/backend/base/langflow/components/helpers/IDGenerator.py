import uuid
from typing import Any, Optional

from langflow.custom import Component
from langflow.io import MessageTextInput, Output
from langflow.schema import dotdict
from langflow.schema.message import Message


class IDGeneratorComponent(Component):
    display_name = "ID Generator"
    description = "Generates a unique ID."
    icon = "fingerprint"
    name = "IDGenerator"

    inputs = [
        MessageTextInput(
            name="unique_id",
            display_name="Value",
            info="The generated unique ID.",
            refresh_button=True,
        ),
    ]

    outputs = [
        Output(display_name="ID", name="id", method="generate_id"),
    ]

    def update_build_config(self, build_config: dotdict, field_value: Any, field_name: Optional[str] = None):
        if field_name == "unique_id":
            build_config[field_name]["value"] = str(uuid.uuid4())
        return build_config

    def generate_id(self) -> Message:
        unique_id = self.unique_id or str(uuid.uuid4())
        self.status = f"Generated ID: {unique_id}"
        return Message(text=unique_id)
