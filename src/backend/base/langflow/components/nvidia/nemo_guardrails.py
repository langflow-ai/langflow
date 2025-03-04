from pathlib import Path

import yaml

from langflow.base.data.utils import read_text_file
from langflow.custom import Component
from langflow.io import FileInput, MultilineInput, Output
from langflow.schema import Data


class NvidiaNeMoGuardrailsComponent(Component):
    display_name = "NeMo Guardrails"
    description = """NVIDIA NeMo framework for enforcing constraints and safety in conversational AI."""
    icon = "NVIDIA"
    name = "NVIDIANeMoGuardrails"
    beta = True

    file_types = ["yaml"]

    inputs = [
        MultilineInput(
            name="yaml_content", display_name="YAML Content", info="Defines the guardrails rules. Takes precedence over the file path"
        ),
        FileInput(name="path", display_name="YAML File Path", file_types=file_types, info="File path to the guardrails rules"),
    ]

    outputs = [
        Output(display_name="Data", name="data", method="load_file"),
    ]

    def load_file(self) -> Data:
        # Prioritize MultilineInput if provided
        yaml_content = self.yaml_content
        if yaml_content:
            try:
                data_dict = yaml.safe_load(yaml_content)
                return Data(data={"text": yaml_content, "parsed_data": data_dict})
            except yaml.YAMLError as e:
                err_msg = "Invalid YAML syntax"
                raise ValueError(err_msg) from e

        # Fall back to FileInput
        if not self.path:
            err_msg = "Upload a file or provide YAML content."
            raise ValueError(err_msg)

        resolved_path = self.resolve_path(self.path)
        extension = Path(resolved_path).suffix[1:].lower()

        if extension not in self.file_types:
            err_msg = f"Unsupported file type: {extension}"
            raise ValueError(err_msg)

        text = read_text_file(resolved_path)
        try:
            data_dict = yaml.safe_load(text)
            return Data(data={"file_path": resolved_path, "text": text, "parsed_data": data_dict})
        except yaml.YAMLError as e:
            error_msg = "Invalid YAML syntax in file"
            raise ValueError(error_msg) from e