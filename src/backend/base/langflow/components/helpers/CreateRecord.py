from typing import Any

from langflow.custom import CustomComponent
from langflow.field_typing.range_spec import RangeSpec
from langflow.schema import Record
from langflow.schema.dotdict import dotdict
from langflow.template.field.base import TemplateField


class CreateRecordComponent(CustomComponent):
    display_name = "Create Record"
    description = "Dynamically create a Record with a specified number of fields."
    field_order = ["number_of_fields", "text_key"]

    def update_build_config(self, build_config: dotdict, field_value: Any, field_name: str | None = None):
        if field_name == "number_of_fields":
            default_keys = ["code", "_type", "number_of_fields", "text_key"]
            try:
                field_value_int = int(field_value)
            except TypeError:
                return build_config
            existing_fields = {}
            if field_value_int > 15:
                build_config["number_of_fields"]["value"] = 15
                raise ValueError("Number of fields cannot exceed 15. Try using a Component to combine two Records.")
            if len(build_config) > len(default_keys) + field_value_int:
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
                    field = TemplateField(
                        display_name=f"Field {i}",
                        name=key,
                        info=f"Key for field {i}.",
                        field_type="dict",
                        input_types=["Text", "Record"],
                    )
                    build_config[field.name] = field.to_dict()

            build_config["number_of_fields"]["value"] = field_value_int
        return build_config

    def build_config(self):
        return {
            "number_of_fields": {
                "display_name": "Number of Fields",
                "info": "Number of fields to be added to the record.",
                "real_time_refresh": True,
                "rangeSpec": RangeSpec(min=1, max=15, step=1, step_type="int"),
            },
            "text_key": {
                "display_name": "Text Key",
                "info": "Key to be used as text.",
                "advanced": True,
            },
        }

    def build(
        self,
        number_of_fields: int = 0,
        text_key: str = "text",
        **kwargs,
    ) -> Record:
        data = {}
        for value_dict in kwargs.values():
            if isinstance(value_dict, dict):
                # Check if the value of the value_dict is a Record
                value_dict = {
                    key: value.get_text() if isinstance(value, Record) else value for key, value in value_dict.items()
                }
                data.update(value_dict)
        return_record = Record(data=data, text_key=text_key)
        self.status = return_record
        return return_record
