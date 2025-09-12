import uuid
from typing import Any

from typing_extensions import override

from lfx.custom.custom_component.component import Component
from lfx.io import MessageTextInput, Output
from lfx.schema.dotdict import dotdict
from lfx.schema.message import Message


class IDGeneratorComponent(Component):
    display_name = "ID Generator"
    description = "Generates a unique ID."
    icon = "fingerprint"
    name = "IDGenerator"
    legacy = True

    inputs = [
        MessageTextInput(
            name="unique_id",
            display_name="Value",
            info="The generated unique ID.",
            refresh_button=True,
            tool_mode=True,
        ),
    ]

    outputs = [
        Output(display_name="ID", name="id", method="generate_id"),
    ]

    @override
    def update_build_config(self, build_config: dotdict, field_value: Any, field_name: str | None = None):
        if field_name == "unique_id":
            build_config[field_name]["value"] = str(uuid.uuid4())
        return build_config

    def generate_id(self) -> Message:
        unique_id = self.unique_id or str(uuid.uuid4())
        self.status = f"Generated ID: {unique_id}"
        return Message(text=unique_id)
