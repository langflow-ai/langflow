from typing import Any, List

from langflow import CustomComponent
from langflow.schema import Record
from langflow.template.field.base import TemplateField


class RecordComponent2(CustomComponent):
    display_name = "Record Text"
    description = "A component to create a record from key-value pairs."
    field_order = ["keys"]

    def update_build_config(self, build_config: dict, field_name: str, field_value: Any):
        if field_value is None:
            field_value = []
        if field_name is None:
            return build_config
        elif len(field_value) == 0:
            keep = ["keys", "code"]
            for key in build_config.copy():
                if key in keep:
                    continue
                del build_config[key]
        build_config[field_name]["value"] = field_value

        # Add new fields depending on the field value
        for val in field_value:
            if not isinstance(val, str) or val == "":
                continue
            field = TemplateField(
                name=val,
                field_type="str",
                display_name="",
                info="The key for the record.",
            )
            build_config[field.name] = field.to_dict()

    def build_config(self):
        return {
            "keys": {
                "display_name": "Keys",
                "refresh": True,
                "info": "The number of keys to create in the record.",
                "input_types": [],
            },
        }

    def build(self, keys: List[str], **kwargs) -> Record:
        record = Record(data=kwargs)
        self.status = record
        return record
