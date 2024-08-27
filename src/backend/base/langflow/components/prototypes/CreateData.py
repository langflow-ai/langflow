from typing import Any

from langflow.custom import Component
from langflow.inputs.inputs import IntInput, MessageTextInput, DictInput
from langflow.io import Output

from langflow.field_typing.range_spec import RangeSpec
from langflow.schema import Data
from langflow.schema.dotdict import dotdict


class CreateDataComponent(Component):
    display_name: str = "Create Data"
    description: str = "Dynamically create a Data with a specified number of fields."
    name: str = "CreateData"

    inputs = [
        IntInput(
            name="number_of_fields",
            display_name="Number of Fields",
            info="Number of fields to be added to the record.",
            real_time_refresh=True,
            value=0,
            range_spec=RangeSpec(min=1, max=15, step=1, step_type="int"),
        ),
        MessageTextInput(name="text_key", display_name="Text Key", info="Key to be used as text.", advanced=True),
    ]

    outputs = [
        Output(display_name="Data", name="data", method="build_data"),
    ]

    def update_build_config(self, build_config: dotdict, field_value: Any, field_name: str | None = None):
        if field_name == "number_of_fields":
            default_keys = ["code", "_type", "number_of_fields", "text_key"]
            try:
                field_value_int = int(field_value)
            except ValueError:
                return build_config
            existing_fields = {}
            if field_value_int > 15:
                build_config["number_of_fields"]["value"] = 15
                raise ValueError("Number of fields cannot exceed 15. Try using a Component to combine two Data.")
            if len(build_config) > len(default_keys):
                # back up the existing template fields
                for key in build_config.copy():
                    if key not in default_keys:
                        existing_fields[key] = build_config.pop(key)

            for i in range(1, field_value_int + 1):
                key = f"field_{i}_key"
                if key in existing_fields:
                    field = existing_fields[key]
                    build_config[key] = field
                else:
                    field = DictInput(
                        display_name=f"Field {i}",
                        name=key,
                        info=f"Key for field {i}.",
                        input_types=["Text", "Data"],
                    )
                    build_config[field.name] = field.to_dict()

            build_config["number_of_fields"]["value"] = field_value_int
        return build_config

    async def build_data(self) -> Data:
        data = {}
        for value_dict in self._attributes.values():
            if isinstance(value_dict, dict):
                # Check if the value of the value_dict is a Data
                value_dict = {
                    key: value.get_text() if isinstance(value, Data) else value for key, value in value_dict.items()
                }
                data.update(value_dict)
        return_data = Data(data=data, text_key=self.text_key)
        self.status = return_data
        return return_data

    def post_code_processing(self, new_frontend_node: dict, current_frontend_node: dict):
        """
        This function is called after the code validation is done.
        """
        frontend_node = super().post_code_processing(new_frontend_node, current_frontend_node)
        frontend_node["template"] = self.update_build_config(
            frontend_node["template"], frontend_node["template"]["number_of_fields"]["value"], "number_of_fields"
        )
        frontend_node = super().post_code_processing(new_frontend_node, current_frontend_node)
        return frontend_node
