from typing import Any

from lfx.custom import Component
from lfx.io import (
    BoolInput,
    HandleInput,
    IntInput,
    MultilineInput,
    Output,
    TableInput,
)
from lfx.schema.data import Data
from lfx.schema.table import EditMode


class DynamicCreateDataComponent(Component):
    display_name: str = "Combine Inputs"
    description: str = "Define custom inputs and combine them into a single output."
    name: str = "CombineInputs"
    icon = "ListFilter"
    metadata = {
        "previous_names": ["Dynamic Inputs", "DynamicInputs", "Dynamic Create Data", "DynamicCreateData"],
        "previous_params": ["form_fields", "field_name", "field_type"],
    }

    inputs = [
        TableInput(
            name="inputs_config",
            display_name="Inputs",
            info="Define custom inputs. Each row creates a new input handle.",
            table_schema=[
                {
                    "name": "input_name",
                    "display_name": "Input Name",
                    "type": "str",
                    "description": "Name for the input (used as both internal name and display label)",
                    "edit_mode": EditMode.INLINE,
                },
                {
                    "name": "input_type",
                    "display_name": "Input Type",
                    "type": "str",
                    "description": "Type of input to create",
                    "options": ["Text", "Data", "Number", "Handle", "Boolean"],
                    "default": "Text",
                    "edit_mode": EditMode.INLINE,
                },
            ],
            value=[],
            real_time_refresh=True,
        ),
    ]

    outputs = [
        Output(display_name="Data", name="data_output", method="process_inputs"),
    ]

    def update_build_config(self, build_config: dict, field_value: Any, field_name: str | None = None) -> dict:
        """Update build configuration to add dynamic inputs that can connect to other components."""
        if field_name != "inputs_config":
            return build_config

        # Clear existing dynamic inputs from build config
        keys_to_remove = [key for key in build_config if key.startswith("dynamic_")]
        for key in keys_to_remove:
            del build_config[key]

        if field_value is None:
            return build_config

        # Map input type options to input class and accepted types
        input_type_mapping = {
            "Text": {"class": MultilineInput, "input_types": ["Text", "Message"]},
            "Data": {"class": HandleInput, "input_types": ["Data"]},
            "Number": {"class": IntInput, "input_types": ["Text", "Message"]},
            "Handle": {"class": HandleInput, "input_types": ["Text", "Data", "Message"]},
            "Boolean": {"class": BoolInput, "input_types": []},
        }

        for i, input_config in enumerate(field_value):
            if input_config is None:
                continue

            input_name = input_config.get("input_name", f"input_{i}")
            input_type_option = input_config.get("input_type", "Text")
            dynamic_input_name = f"dynamic_{input_name}"

            mapping = input_type_mapping.get(input_type_option, input_type_mapping["Text"])
            input_class = mapping["class"]
            input_types = mapping["input_types"]

            # Build common kwargs
            kwargs = {
                "name": dynamic_input_name,
                "display_name": input_name,
                "input_types": input_types,
            }

            # Add type-specific defaults
            if input_class == BoolInput:
                kwargs["value"] = False
            elif input_class == MultilineInput:
                kwargs["value"] = ""
            elif input_class == IntInput:
                kwargs["value"] = 0

            build_config[dynamic_input_name] = input_class(**kwargs)

        return build_config

    def get_dynamic_values(self) -> dict[str, Any]:
        """Extract values from all dynamic inputs."""
        dynamic_values = {}
        inputs_config = getattr(self, "inputs_config", [])

        for input_config in inputs_config:
            if input_config is None:
                continue

            input_name = input_config.get("input_name", "")
            if not input_name:
                continue

            dynamic_input_name = f"dynamic_{input_name}"
            value = getattr(self, dynamic_input_name, None)

            if value is not None:
                dynamic_values[input_name] = self._extract_simple_value(value)
            else:
                dynamic_values[input_name] = ""

        return dynamic_values

    def _extract_simple_value(self, value: Any) -> Any:
        """Extract the simplest, most useful value from any input type."""
        if value is None:
            return None

        if isinstance(value, (str, int, float, bool)):
            return value

        if isinstance(value, (list, tuple)):
            return [self._extract_simple_value(item) for item in value]

        if isinstance(value, dict):
            return {str(k): self._extract_simple_value(v) for k, v in value.items()}

        # Handle Message objects - extract only the text
        if hasattr(value, "text"):
            return str(value.text) if value.text is not None else ""

        # Handle Data objects - extract the data content
        if hasattr(value, "data") and value.data is not None:
            return self._extract_simple_value(value.data)

        return str(value)

    def process_inputs(self) -> Data:
        """Process all dynamic inputs and return combined data."""
        dynamic_values = self.get_dynamic_values()
        self.status = f"Combined {len(dynamic_values)} inputs."
        return Data(data=dynamic_values)
