from typing import Optional

from pydantic import BaseModel

from langflow.template.field.base import TemplateField
from langflow.template.frontend_node.prompts import FORCE_SHOW_FIELDS
from langflow.template.template.base import Template
from langflow.utils import constants


class FrontendNode(BaseModel):
    template: Template
    description: str
    base_classes: list
    name: str = ""

    def add_field(self, field: TemplateField):
        self.template.fields.append(field)

    def add_text_output_to_base_classes(self):
        if "Text" not in self.base_classes:
            self.base_classes.append("Text")

    def to_dict(self):
        return {
            self.name: {
                "template": self.template.to_dict(self.format_field),
                "description": self.description,
                "base_classes": self.base_classes,
            }
        }

    @staticmethod
    def format_field(field: TemplateField, name: Optional[str] = None) -> None:
        key = field.name
        value = field.to_dict()
        _type = value["type"]

        # Remove 'Optional' wrapper
        if "Optional" in _type:
            _type = _type.replace("Optional[", "")[:-1]

        # Check for list type
        if "List" in _type or "Sequence" in _type:
            _type = _type.replace("List[", "")
            _type = _type.replace("Sequence[", "")[:-1]
            field.is_list = True

        # Replace 'Mapping' with 'dict'
        if "Mapping" in _type:
            _type = _type.replace("Mapping", "dict")

        # {'type': 'Union[float, Tuple[float, float], NoneType]'} != {'type': 'float'}
        if "Union" in _type:
            _type = _type.replace("Union[", "")[:-1]
            _type = _type.split(",")[0]
            _type = _type.replace("]", "").replace("[", "")

        field.field_type = _type

        # Change type from str to Tool
        field.field_type = "Tool" if key in {"allowed_tools"} else field.field_type

        field.field_type = "int" if key in {"max_value_length"} else field.field_type

        # Show or not field
        field.show = bool(
            (field.required and key not in ["input_variables"])
            or key in FORCE_SHOW_FIELDS
            or "api" in key
            or ("key" in key and "input" not in key and "output" not in key)
        )

        # Add password field
        field.password = (
            any(text in key.lower() for text in {"password", "token", "api", "key"})
            and field.show
        )

        # Add multline
        field.multiline = key in {
            "suffix",
            "prefix",
            "template",
            "examples",
            "code",
            "headers",
            "description",
        }

        # Replace dict type with str
        if "dict" in field.field_type.lower():
            field.field_type = "code"

        if key == "dict_":
            field.field_type = "file"
            field.suffixes = [".json", ".yaml", ".yml"]
            field.file_types = ["json", "yaml", "yml"]

        # Replace default value with actual value
        if "default" in value:
            field.value = value["default"]

        if key == "headers":
            field.value = """{'Authorization':
            'Bearer <token>'}"""

        # Add options to openai
        if name == "OpenAI" and key == "model_name":
            field.options = constants.OPENAI_MODELS
            field.is_list = True
        elif name == "ChatOpenAI":
            if key == "model_name":
                field.options = constants.CHAT_OPENAI_MODELS
                field.is_list = True
        if "api_key" in key and "OpenAI" in str(name):
            field.display_name = "OpenAI API Key"
            field.required = False
            if field.value is None:
                field.value = ""

        if "kwargs" in field.name.lower():
            field.advanced = True
            field.required = False
            field.show = False
        # If the field.name contains api or api and key, then it might be an api key
        # other conditions are to make sure that it is not an input or output variable
        if "api" in key.lower() and "key" in key.lower():
            field.required = False
            field.advanced = False
