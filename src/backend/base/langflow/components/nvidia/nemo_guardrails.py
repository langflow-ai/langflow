from langflow.custom import Component
from langflow.io import FileInput, MultilineInput, Output
from langflow.base.data.utils import read_text_file
from langflow.schema import Data
import yaml
from pathlib import Path

class NVIDIANemoGuardrailsComponent(Component):
    display_name = "NVIDIA NeMo Guardrails"
    description = "Apply guardrails to LLM interactions. Load guardrail definintions from a YAML file, or provide directly as multiline text"
    icon = "NVIDIA"
    name = "NVIDIANemoGuardrails"
    beta = True

    file_types = ["yaml"]

    inputs = [
        MultilineInput(
            name="yaml_content",
            display_name="YAML Content (takes precedence)",
            info="Enter YAML content here"
        ),
        FileInput(
            name="path",
            display_name="YAML File Path",
            file_types=file_types,
            info="yaml files"
        ),
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
                raise ValueError(f"Invalid YAML syntax: {e}")

        # Fall back to FileInput
        if not self.path:
            raise ValueError("Please, upload a file or provide YAML content.")

        resolved_path = self.resolve_path(self.path)
        extension = Path(resolved_path).suffix[1:].lower()

        if extension not in self.file_types:
            raise ValueError(f"Unsupported file type: {extension}")

        text = read_text_file(resolved_path)
        try:
            data_dict = yaml.safe_load(text)
            return Data(data={"file_path": resolved_path, "text": text, "parsed_data": data_dict})
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML syntax in file: {e}")
