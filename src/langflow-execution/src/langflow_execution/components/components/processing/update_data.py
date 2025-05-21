from typing import Any

from langflow.custom import Component
from langflow.field_typing.range_spec import RangeSpec
from langflow.inputs.inputs import (
    BoolInput,
    DataInput,
    DictInput,
    IntInput,
    MessageTextInput,
)
from langflow.io import Output
from langflow.schema import Data
from langflow.schema.dotdict import dotdict


class UpdateDataComponent(Component):
    display_name: str = "Update Data"
    description: str = "Dynamically update or append data with the specified fields."
    name: str = "UpdateData"
    MAX_FIELDS = 15  # Define a constant for maximum number of fields
    icon = "FolderSync"

    inputs = [
        DataInput(
            name="old_data",
            display_name="Data",
            info="The record to update.",
            is_list=True,  # Changed to True to handle list of Data objects
            required=True,
        ),
        IntInput(
            name="number_of_fields",
            display_name="Number of Fields",
            info="Number of fields to be added to the record.",
            real_time_refresh=True,
            value=0,
            range_spec=RangeSpec(min=1, max=MAX_FIELDS, step=1, step_type="int"),
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
        """Update the build configuration when the number of fields changes.

        Args:
            build_config (dotdict): The current build configuration.
            field_value (Any): The new value for the field.
            field_name (Optional[str]): The name of the field being updated.
        """
        if field_name == "number_of_fields":
            default_keys = {
                "code",
                "_type",
                "number_of_fields",
                "text_key",
                "old_data",
                "text_key_validator",
            }
            try:
                field_value_int = int(field_value)
            except ValueError:
                return build_config

            if field_value_int > self.MAX_FIELDS:
                build_config["number_of_fields"]["value"] = self.MAX_FIELDS
                msg = f"Number of fields cannot exceed {self.MAX_FIELDS}. Try using a Component to combine two Data."
                raise ValueError(msg)

            existing_fields = {}
            # Back up the existing template fields
            for key in list(build_config.keys()):
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
                        input_types=["Message", "Data"],
                    )
                    build_config[field.name] = field.to_dict()

            build_config["number_of_fields"]["value"] = field_value_int
        return build_config

    async def build_data(self) -> Data | list[Data]:
        """Build the updated data by combining the old data with new fields."""
        new_data = self.get_data()
        if isinstance(self.old_data, list):
            for data_item in self.old_data:
                if not isinstance(data_item, Data):
                    continue  # Skip invalid items
                data_item.data.update(new_data)
                if self.text_key:
                    data_item.text_key = self.text_key
                self.validate_text_key(data_item)
            self.status = self.old_data
            return self.old_data  # Returns List[Data]
        if isinstance(self.old_data, Data):
            self.old_data.data.update(new_data)
            if self.text_key:
                self.old_data.text_key = self.text_key
            self.status = self.old_data
            self.validate_text_key(self.old_data)
            return self.old_data  # Returns Data
        msg = "old_data is not a Data object or list of Data objects."
        raise ValueError(msg)

    def get_data(self):
        """Function to get the Data from the attributes."""
        data = {}
        default_keys = {
            "code",
            "_type",
            "number_of_fields",
            "text_key",
            "old_data",
            "text_key_validator",
        }
        for attr_name, attr_value in self._attributes.items():
            if attr_name in default_keys:
                continue  # Skip default attributes
            if isinstance(attr_value, dict):
                for key, value in attr_value.items():
                    data[key] = value.get_text() if isinstance(value, Data) else value
            elif isinstance(attr_value, Data):
                data[attr_name] = attr_value.get_text()
            else:
                data[attr_name] = attr_value
        return data

    def validate_text_key(self, data: Data) -> None:
        """This function validates that the Text Key is one of the keys in the Data."""
        data_keys = data.data.keys()
        if self.text_key and self.text_key not in data_keys:
            msg = f"Text Key: '{self.text_key}' not found in the Data keys: {', '.join(data_keys)}"
            raise ValueError(msg)
