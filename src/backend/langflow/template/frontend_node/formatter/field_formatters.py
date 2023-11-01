from typing import Optional
from langflow.template.field.base import TemplateField
from langflow.template.frontend_node.constants import FORCE_SHOW_FIELDS
from langflow.template.frontend_node.formatter.base import FieldFormatter
import re

from langflow.utils.constants import (
    ANTHROPIC_MODELS,
    CHAT_OPENAI_MODELS,
    OPENAI_MODELS,
)


class OpenAIAPIKeyFormatter(FieldFormatter):
    def format(self, field: TemplateField, name: Optional[str] = None) -> None:
        if "api_key" in field.name and "OpenAI" in str(name):
            field.display_name = "OpenAI API Key"
            field.required = False
            if field.value is None:
                field.value = ""


class ModelSpecificFieldFormatter(FieldFormatter):
    MODEL_DICT = {
        "OpenAI": OPENAI_MODELS,
        "ChatOpenAI": CHAT_OPENAI_MODELS,
        "Anthropic": ANTHROPIC_MODELS,
        "ChatAnthropic": ANTHROPIC_MODELS,
    }

    def format(self, field: TemplateField, name: Optional[str] = None) -> None:
        if name in self.MODEL_DICT and field.name == "model_name":
            field.options = self.MODEL_DICT[name]
            field.is_list = True


class KwargsFormatter(FieldFormatter):
    def format(self, field: TemplateField, name: Optional[str] = None) -> None:
        if "kwargs" in field.name.lower():
            field.advanced = True
            field.required = False
            field.show = False


class APIKeyFormatter(FieldFormatter):
    def format(self, field: TemplateField, name: Optional[str] = None) -> None:
        if "api" in field.name.lower() and "key" in field.name.lower():
            field.required = False
            field.advanced = False

            field.display_name = field.name.replace("_", " ").title()
            field.display_name = field.display_name.replace("Api", "API")


class RemoveOptionalFormatter(FieldFormatter):
    def format(self, field: TemplateField, name: Optional[str] = None) -> None:
        _type = field.field_type
        field.field_type = re.sub(r"Optional\[(.*)\]", r"\1", _type)


class ListTypeFormatter(FieldFormatter):
    def format(self, field: TemplateField, name: Optional[str] = None) -> None:
        _type = field.field_type
        is_list = "List" in _type or "Sequence" in _type
        if is_list:
            _type = re.sub(r"(List|Sequence)\[(.*)\]", r"\2", _type)
            field.is_list = True
        field.field_type = _type


class DictTypeFormatter(FieldFormatter):
    def format(self, field: TemplateField, name: Optional[str] = None) -> None:
        _type = field.field_type
        _type = _type.replace("Mapping", "dict")
        field.field_type = _type


class UnionTypeFormatter(FieldFormatter):
    def format(self, field: TemplateField, name: Optional[str] = None) -> None:
        _type = field.field_type
        if "Union" in _type:
            _type = _type.replace("Union[", "")[:-1]
            _type = _type.split(",")[0]
            _type = _type.replace("]", "").replace("[", "")
        field.field_type = _type


class SpecialFieldFormatter(FieldFormatter):
    SPECIAL_FIELD_HANDLERS = {
        "allowed_tools": lambda field: "Tool",
        "max_value_length": lambda field: "int",
    }

    def format(self, field: TemplateField, name: Optional[str] = None) -> None:
        handler = self.SPECIAL_FIELD_HANDLERS.get(field.name)
        field.field_type = handler(field) if handler else field.field_type


class ShowFieldFormatter(FieldFormatter):
    def format(self, field: TemplateField, name: Optional[str] = None) -> None:
        key = field.name
        required = field.required
        field.show = (
            (required and key not in ["input_variables"])
            or key in FORCE_SHOW_FIELDS
            or "api" in key
            or ("key" in key and "input" not in key and "output" not in key)
        )


class PasswordFieldFormatter(FieldFormatter):
    def format(self, field: TemplateField, name: Optional[str] = None) -> None:
        key = field.name
        show = field.show
        if (
            any(text in key.lower() for text in {"password", "token", "api", "key"})
            and show
        ):
            field.password = True


class MultilineFieldFormatter(FieldFormatter):
    def format(self, field: TemplateField, name: Optional[str] = None) -> None:
        key = field.name
        if key in {
            "suffix",
            "prefix",
            "template",
            "examples",
            "code",
            "headers",
            "description",
        }:
            field.multiline = True


class DefaultValueFormatter(FieldFormatter):
    def format(self, field: TemplateField, name: Optional[str] = None) -> None:
        value = field.to_dict()
        if "default" in value:
            field.value = value["default"]


class HeadersDefaultValueFormatter(FieldFormatter):
    def format(self, field: TemplateField, name: Optional[str] = None) -> None:
        key = field.name
        if key == "headers":
            field.value = """{"Authorization": "Bearer <token>"}"""


class DictCodeFileFormatter(FieldFormatter):
    def format(self, field: TemplateField, name: Optional[str] = None) -> None:
        key = field.name
        value = field.to_dict()
        _type = value["type"]
        if "dict" in _type.lower() and key == "dict_":
            field.field_type = "file"
            field.suffixes = [".json", ".yaml", ".yml"]
            field.file_types = ["json", "yaml", "yml"]
        elif (
            _type.startswith("Dict")
            or _type.startswith("Mapping")
            or _type.startswith("dict")
        ):
            field.field_type = "dict"
