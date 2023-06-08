import re
from typing import List, Optional

from pydantic import BaseModel

from langflow.template.frontend_node.constants import FORCE_SHOW_FIELDS
from langflow.template.field.base import TemplateField
from langflow.template.template.base import Template
from langflow.utils import constants


class FrontendNode(BaseModel):
    template: Template
    description: str
    base_classes: List[str]
    name: str = ""

    def to_dict(self) -> dict:
        return {
            self.name: {
                "template": self.template.to_dict(self.format_field),
                "description": self.description,
                "base_classes": self.base_classes,
            }
        }

    def add_extra_fields(self) -> None:
        pass

    @staticmethod
    def format_field(field: TemplateField, name: Optional[str] = None) -> None:
        """Formats a given field based on its attributes and value."""
        SPECIAL_FIELD_HANDLERS = {
            "allowed_tools": lambda field: "Tool",
            "max_value_length": lambda field: "int",
        }

        key = field.name
        value = field.to_dict()
        _type = value["type"]

        _type = FrontendNode.remove_optional(_type)
        _type, is_list = FrontendNode.check_for_list_type(_type)
        field.is_list = is_list or field.is_list
        _type = FrontendNode.replace_mapping_with_dict(_type)
        _type = FrontendNode.handle_union_type(_type)

        field.field_type = FrontendNode.handle_special_field(
            field, key, _type, SPECIAL_FIELD_HANDLERS
        )
        field.field_type = FrontendNode.handle_dict_type(field, _type)
        field.show = FrontendNode.should_show_field(key, field.required)
        field.password = FrontendNode.should_be_password(key, field.show)
        field.multiline = FrontendNode.should_be_multiline(key)

        FrontendNode.replace_default_value(field, value)
        FrontendNode.handle_specific_field_values(field, key, name)
        FrontendNode.handle_kwargs_field(field)
        FrontendNode.handle_api_key_field(field, key)

    @staticmethod
    def remove_optional(_type: str) -> str:
        """Removes 'Optional' wrapper from the type if present."""
        return re.sub(r"Optional\[(.*)\]", r"\1", _type)

    @staticmethod
    def check_for_list_type(_type: str) -> tuple:
        """Checks for list type and returns the modified type and a boolean indicating if it's a list."""
        is_list = "List" in _type or "Sequence" in _type
        if is_list:
            _type = re.sub(r"(List|Sequence)\[(.*)\]", r"\2", _type)
        return _type, is_list

    @staticmethod
    def replace_mapping_with_dict(_type: str) -> str:
        """Replaces 'Mapping' with 'dict'."""
        return _type.replace("Mapping", "dict")

    @staticmethod
    def handle_union_type(_type: str) -> str:
        """Simplifies the 'Union' type to the first type in the Union."""
        if "Union" in _type:
            _type = _type.replace("Union[", "")[:-1]
            _type = _type.split(",")[0]
            _type = _type.replace("]", "").replace("[", "")
        return _type

    @staticmethod
    def handle_special_field(
        field, key: str, _type: str, SPECIAL_FIELD_HANDLERS
    ) -> str:
        """Handles special field by using the respective handler if present."""
        handler = SPECIAL_FIELD_HANDLERS.get(key)
        return handler(field) if handler else _type

    @staticmethod
    def handle_dict_type(field: TemplateField, _type: str) -> str:
        """Handles 'dict' type by replacing it with 'code' or 'file' based on the field name."""
        if "dict" in _type.lower():
            if field.name == "dict_":
                field.field_type = "file"
                field.suffixes = [".json", ".yaml", ".yml"]
                field.file_types = ["json", "yaml", "yml"]
            else:
                field.field_type = "code"
        return _type

    @staticmethod
    def replace_default_value(field: TemplateField, value: dict) -> None:
        """Replaces default value with actual value if 'default' is present in value."""
        if "default" in value:
            field.value = value["default"]

    @staticmethod
    def handle_specific_field_values(
        field: TemplateField, key: str, name: Optional[str] = None
    ) -> None:
        """Handles specific field values for certain fields."""
        if key == "headers":
            field.value = """{'Authorization': 'Bearer <token>'}"""
        FrontendNode._handle_model_specific_field_values(field, key, name)
        FrontendNode._handle_api_key_specific_field_values(field, key, name)

    @staticmethod
    def _handle_model_specific_field_values(
        field: TemplateField, key: str, name: Optional[str] = None
    ) -> None:
        """Handles specific field values related to models."""
        model_dict = {
            "OpenAI": constants.OPENAI_MODELS,
            "ChatOpenAI": constants.CHAT_OPENAI_MODELS,
            "Anthropic": constants.ANTHROPIC_MODELS,
            "ChatAnthropic": constants.ANTHROPIC_MODELS,
        }
        if name in model_dict and key == "model_name":
            field.options = model_dict[name]
            field.is_list = True

    @staticmethod
    def _handle_api_key_specific_field_values(
        field: TemplateField, key: str, name: Optional[str] = None
    ) -> None:
        """Handles specific field values related to API keys."""
        if "api_key" in key and "OpenAI" in str(name):
            field.display_name = "OpenAI API Key"
            field.required = False
            if field.value is None:
                field.value = ""

    @staticmethod
    def handle_kwargs_field(field: TemplateField) -> None:
        """Handles kwargs field by setting certain attributes."""
        if "kwargs" in field.name.lower():
            field.advanced = True
            field.required = False
            field.show = False

    @staticmethod
    def handle_api_key_field(field: TemplateField, key: str) -> None:
        """Handles api key field by setting certain attributes."""
        if "api" in key.lower() and "key" in key.lower():
            field.required = False
            field.advanced = False

            field.display_name = key.replace("_", " ").title()
            field.display_name = field.display_name.replace("Api", "API")

    @staticmethod
    def should_show_field(key: str, required: bool) -> bool:
        """Determines whether the field should be shown."""
        return (
            (required and key not in ["input_variables"])
            or key in FORCE_SHOW_FIELDS
            or "api" in key
            or ("key" in key and "input" not in key and "output" not in key)
        )

    @staticmethod
    def should_be_password(key: str, show: bool) -> bool:
        """Determines whether the field should be a password field."""
        return (
            any(text in key.lower() for text in {"password", "token", "api", "key"})
            and show
        )

    @staticmethod
    def should_be_multiline(key: str) -> bool:
        """Determines whether the field should be multiline."""
        return key in {
            "suffix",
            "prefix",
            "template",
            "examples",
            "code",
            "headers",
            "description",
        }

    @staticmethod
    def replace_dict_with_code_or_file(
        field: TemplateField, _type: str, key: str
    ) -> str:
        """Replaces 'dict' type with 'code' or 'file'."""
        if "dict" in _type.lower():
            if key == "dict_":
                field.field_type = "file"
                field.suffixes = [".json", ".yaml", ".yml"]
                field.file_types = ["json", "yaml", "yml"]
            else:
                field.field_type = "code"
        return field.field_type

    @staticmethod
    def set_field_default_value(field: TemplateField, value: dict, key: str) -> None:
        """Sets the field value with the default value if present."""
        if "default" in value:
            field.value = value["default"]
        if key == "headers":
            field.value = """{'Authorization': 'Bearer <token>'}"""
