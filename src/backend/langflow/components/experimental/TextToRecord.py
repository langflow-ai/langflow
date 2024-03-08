from typing import Any

from langflow import CustomComponent
from langflow.schema import Record
from langflow.template.field.base import TemplateField


class TextToRecordComponent(CustomComponent):
    display_name = "Text to Record"
    description = "A component to create a record from key-value pairs."
    field_order = ["mode", "keys", "n_keys"]
    beta: bool = True

    def set_key_template(self, build_config, field_value):
        keys_template = TemplateField(
            name="n_keys" if field_value == "Number" else "keys",
            field_type="dict" if field_value == "Number" else "str",
            is_list=False if field_value == "Number" else True,
            display_name="Keys",
            info=(
                "The Number of keys to use for the record."
                if field_value == "Number"
                else "The keys to use for the record."
            ),
            input_types=["Text"],
        )
        build_config["keys"] = keys_template.to_dict()

    def set_n_keys(self, build_config, field_name, field_value):
        if int(field_value) == 0:
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

    def set_keys_template(self, build_config, field_value):
        for key in build_config.copy():
            if key == "keys":
                continue
            del build_config[key]
        for i in range(int(field_value)):
            field = TemplateField(
                name=f"Key and Value {i}",
                field_type="dict",
                display_name="",
                info="The key for the record.",
                input_types=["Text"],
            )
            build_config[field.name] = field.to_dict()

    def update_build_config(
        self, build_config: dict, field_name: str, field_value: Any
    ):
        if field_name == "mode":
            build_config["mode"]["value"] = field_value
            self.set_key_template(build_config, field_value)
        if field_value is None:
            return
        if field_name == "n_keys":
            self.set_n_keys(build_config, field_name, field_value)
        elif field_name == "keys":
            self.set_keys_template(build_config, field_value)
        return build_config

    def build_config(self):
        return {
            "mode": {
                "display_name": "Mode",
                "options": ["Text", "Number"],
                "info": "The mode to use for creating the record.",
                "real_time_refresh": True,
                "input_types": [],
            },
        }

    def build(self, mode: str, **kwargs) -> Record:
        if mode == "Text":
            data = kwargs
        else:
            data = {
                k: v
                for key, d in kwargs.items()
                for k, v in d.items()
                if key not in ["mode", "n_keys", "keys"]
            }
        record = Record(data=data)
        return record
