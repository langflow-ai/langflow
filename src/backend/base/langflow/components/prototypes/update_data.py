from typing import Any

from langflow.custom import Component
from langflow.field_typing.range_spec import RangeSpec
from langflow.inputs.inputs import BoolInput, DataInput, DictInput, IntInput, MessageTextInput
from langflow.io import Output
from langflow.schema import Data
from langflow.schema.dotdict import dotdict

MAX_NUMBER_OF_FIELDS = 15


class UpdateDataComponent(Component):
    display_name: str = "Update data"
    description: str = "Dynamically update or append data with the specified fields."
    name: str = "UpdateData"

    inputs = [
        DataInput(
            name="old_data",
            display_name="Data",
            info="The record to update.",
            is_list=False,
        ),
        IntInput(
            name="number_of_fields",
            display_name="Number of Fields",
            info="Number of fields to be added to the record.",
            real_time_refresh=True,
            value=0,
            range_spec=RangeSpec(min=1, max=15, step=1, step_type="int"),
        ),
        MessageTextInput(
            name="text_key",
            display_name="Text Key",
            info="Key that identifies the field to be used as the text content.",
            advanced=True,
        ),
        BoolInput(
            name="text_key_validator",
            display_name="Text Key Validator",
            advanced=True,
            info="If enabled, checks if the given 'Text Key' is present in the given 'Data'.",
        ),
    ]

    outputs = [
        Output(display_name="Data", name="data", method="build_data"),
    ]

    def update_build_config(self, build_config: dotdict, field_value: Any, field_name: str | None = None):
        if field_name == "number_of_fields":
            default_keys = ["code", "_type", "number_of_fields", "text_key", "old_data", "text_key_validator"]
            try:
                field_value_int = int(field_value)
            except ValueError:
                return build_config
            existing_fields = {}
            if field_value_int > MAX_NUMBER_OF_FIELDS:
                build_config["number_of_fields"]["value"] = MAX_NUMBER_OF_FIELDS
                msg = (
                    f"Number of fields cannot exceed {MAX_NUMBER_OF_FIELDS}. Try using a Component to combine two Data."
                )
                raise ValueError(msg)
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
        new_data = self.get_data()
        self.old_data.data.update(new_data)
        if self.text_key:
            self.old_data.text_key = self.text_key
        self.status = self.old_data
        self.validate_text_key(self.old_data)
        return self.old_data

    def get_data(self):
        """Function to get the Data from the attributes."""
        data = {}
        for value_dict in self._attributes.values():
            if isinstance(value_dict, dict):
                # Check if the value of the value_dict is a Data
                _value_dict = {
                    key: value.get_text() if isinstance(value, Data) else value for key, value in value_dict.items()
                }
                data.update(_value_dict)
        return data

    def validate_text_key(self, data: Data) -> None:
        """This function validates that the Text Key is one of the keys in the Data."""
        data_keys = data.data.keys()
        if self.text_key not in data_keys and self.text_key != "":
            msg = f"Text Key: {self.text_key} not found in the Data keys: {','.join(data_keys)}"
            raise ValueError(msg)
