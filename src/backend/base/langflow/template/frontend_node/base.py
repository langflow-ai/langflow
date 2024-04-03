import re
from collections import defaultdict
from typing import ClassVar, Dict, List, Optional, Union

from pydantic import BaseModel, Field, field_serializer, model_serializer

from langflow.template.field.base import TemplateField
from langflow.template.frontend_node.constants import FORCE_SHOW_FIELDS
from langflow.template.frontend_node.formatter import field_formatters
from langflow.template.template.base import Template
from langflow.utils import constants


class FieldFormatters(BaseModel):
    formatters: ClassVar[Dict] = {
        "openai_api_key": field_formatters.OpenAIAPIKeyFormatter(),
    }
    base_formatters: ClassVar[Dict] = {
        "kwargs": field_formatters.KwargsFormatter(),
        "optional": field_formatters.RemoveOptionalFormatter(),
        "list": field_formatters.ListTypeFormatter(),
        "dict": field_formatters.DictTypeFormatter(),
        "union": field_formatters.UnionTypeFormatter(),
        "multiline": field_formatters.MultilineFieldFormatter(),
        "show": field_formatters.ShowFieldFormatter(),
        "password": field_formatters.PasswordFieldFormatter(),
        "default": field_formatters.DefaultValueFormatter(),
        "headers": field_formatters.HeadersDefaultValueFormatter(),
        "dict_code_file": field_formatters.DictCodeFileFormatter(),
        "model_fields": field_formatters.ModelSpecificFieldFormatter(),
    }

    def format(self, field: TemplateField, name: Optional[str] = None) -> None:
        for key, formatter in self.base_formatters.items():
            formatter.format(field, name)

        for key, formatter in self.formatters.items():
            if key == field.name:
                formatter.format(field, name)


class FrontendNode(BaseModel):
    _format_template: bool = True
    template: Template
    """Template for the frontend node."""
    description: Optional[str] = None
    """Description of the frontend node."""
    icon: Optional[str] = None
    """Icon of the frontend node."""
    is_input: Optional[bool] = None
    """Whether the frontend node is used as an input when processing the Graph.
    If True, there should be a field named 'input_value'."""
    is_output: Optional[bool] = None
    """Whether the frontend node is used as an output when processing the Graph.
    If True, there should be a field named 'input_value'."""
    is_composition: Optional[bool] = None
    """Whether the frontend node is used for composition."""
    base_classes: List[str]
    """List of base classes for the frontend node."""
    name: str = ""
    """Name of the frontend node."""
    display_name: Optional[str] = ""
    """Display name of the frontend node."""
    documentation: str = ""
    """Documentation of the frontend node."""
    custom_fields: Optional[Dict] = defaultdict(list)
    """Custom fields of the frontend node."""
    output_types: List[str] = []
    """List of output types for the frontend node."""
    full_path: Optional[str] = None
    """Full path of the frontend node."""
    field_formatters: FieldFormatters = Field(default_factory=FieldFormatters)
    """Field formatters for the frontend node."""
    frozen: bool = False
    """Whether the frontend node is frozen."""

    field_order: list[str] = []
    """Order of the fields in the frontend node."""

    beta: bool = False
    error: Optional[str] = None

    # field formatters is an instance attribute but it is not used in the class
    # so we need to create a method to get it
    @staticmethod
    def get_field_formatters() -> FieldFormatters:
        return FieldFormatters()

    def set_documentation(self, documentation: str) -> None:
        """Sets the documentation of the frontend node."""
        self.documentation = documentation

    @field_serializer("base_classes")
    def process_base_classes(self, base_classes: List[str]) -> List[str]:
        """Removes unwanted base classes from the list of base classes."""

        sorted_base_classes = sorted(list(set(base_classes)), key=lambda x: x.lower())
        return sorted_base_classes

    @field_serializer("display_name")
    def process_display_name(self, display_name: str) -> str:
        """Sets the display name of the frontend node."""

        return display_name or self.name

    @model_serializer(mode="wrap")
    def serialize_model(self, handler):
        result = handler(self)
        if hasattr(self, "template") and hasattr(self.template, "to_dict"):
            format_func = self.format_field if self._format_template else None
            result["template"] = self.template.to_dict(format_func)
        name = result.pop("name")

        return {name: result}

    # For backwards compatibility
    def to_dict(self, add_name=True) -> dict:
        """Returns a dict representation of the frontend node."""
        dump = self.model_dump(by_alias=True, exclude_none=True)
        if not add_name:
            return dump.pop(self.name)
        return dump

    def add_extra_fields(self) -> None:
        pass

    def add_extra_base_classes(self) -> None:
        pass

    def add_base_class(self, base_class: Union[str, List[str]]) -> None:
        """Adds a base class to the frontend node."""
        if isinstance(base_class, str):
            self.base_classes.append(base_class)
        elif isinstance(base_class, list):
            self.base_classes.extend(base_class)

    def add_output_type(self, output_type: Union[str, List[str]]) -> None:
        """Adds an output type to the frontend node."""
        if isinstance(output_type, str):
            self.output_types.append(output_type)
        elif isinstance(output_type, list):
            self.output_types.extend(output_type)

    @staticmethod
    def format_field(field: TemplateField, name: Optional[str] = None) -> None:
        """Formats a given field based on its attributes and value."""

        FrontendNode.get_field_formatters().format(field, name)

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
    def handle_special_field(field, key: str, _type: str, SPECIAL_FIELD_HANDLERS) -> str:
        """Handles special field by using the respective handler if present."""
        handler = SPECIAL_FIELD_HANDLERS.get(key)
        return handler(field) if handler else _type

    @staticmethod
    def handle_dict_type(field: TemplateField, _type: str) -> str:
        """Handles 'dict' type by replacing it with 'code' or 'file' based on the field name."""
        if "dict" in _type.lower() and field.name == "dict_":
            field.field_type = "file"
            field.file_types = [".json", ".yaml", ".yml"]
        elif _type.startswith("Dict") or _type.startswith("Mapping") or _type.startswith("dict"):
            field.field_type = "dict"
        return _type

    @staticmethod
    def replace_default_value(field: TemplateField, value: dict) -> None:
        """Replaces default value with actual value if 'default' is present in value."""
        if "default" in value:
            field.value = value["default"]

    @staticmethod
    def handle_specific_field_values(field: TemplateField, key: str, name: Optional[str] = None) -> None:
        """Handles specific field values for certain fields."""
        if key == "headers":
            field.value = """{"Authorization": "Bearer <token>"}"""
        FrontendNode._handle_model_specific_field_values(field, key, name)
        FrontendNode._handle_api_key_specific_field_values(field, key, name)

    @staticmethod
    def _handle_model_specific_field_values(field: TemplateField, key: str, name: Optional[str] = None) -> None:
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
    def _handle_api_key_specific_field_values(field: TemplateField, key: str, name: Optional[str] = None) -> None:
        """Handles specific field values related to API keys."""
        if "api_key" in key and "OpenAI" in str(name):
            field.display_name = "OpenAI API Key"
            field.required = False
            if field.value is None:
                field.value = ""

    @staticmethod
    def handle_kwargs_field(field: TemplateField) -> None:
        """Handles kwargs field by setting certain attributes."""

        if "kwargs" in (field.name or "").lower():
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
        return any(text in key.lower() for text in {"password", "token", "api", "key"}) and show

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
    def set_field_default_value(field: TemplateField, value: dict, key: str) -> None:
        """Sets the field value with the default value if present."""
        if "default" in value:
            field.value = value["default"]
        if key == "headers":
            field.value = """{"Authorization": "Bearer <token>"}"""
