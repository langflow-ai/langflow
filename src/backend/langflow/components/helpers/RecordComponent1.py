from typing import Any

from langflow import CustomComponent
from langflow.schema import Record
from langflow.template.field.base import TemplateField


class RecordComponent(CustomComponent):
    display_name = "Record Numbers"
    description = "A component to create a record from key-value pairs."
    field_order = ["n_keys"]

    def update_build_config(self, build_config: dict, field_name: str, field_value: Any):
        if field_value is None:
            return
        elif int(field_value) == 0:
            keep = ["n_keys", "code"]
            for key in build_config.copy():
                if key in keep:
                    continue
                del build_config[key]
        build_config[field_name]["value"] = int(field_value)

        # Add new fields depending on the field value
        for i in range(int(field_value)):
            field = TemplateField(
                name=f"Key and Value {i}",
                field_type="dict",
                display_name="",
                info="The key for the record.",
                input_types=["Text"],
            )
            build_config[field.name] = field.to_dict()

    def build_config(self):
        return {
            "n_keys": {
                "display_name": "Number of Fields",
                "refresh": True,
                "info": "The number of keys to create in the record.",
            },
        }

    def build(self, n_keys: int, **kwargs) -> Record:
        data = {k: v for d in kwargs.values() for k, v in d.items()}
        record = Record(data=data)
        return record
