from langflow.template.frontend_node.prompts import FORCE_SHOW_FIELDS
from langflow.utils import constants
from pydantic import BaseModel


from abc import ABC
from typing import Any, Dict, Optional, Union


class TemplateFieldCreator(BaseModel, ABC):
    field_type: str = "str"
    required: bool = False
    placeholder: str = ""
    is_list: bool = False
    show: bool = True
    multiline: bool = False
    value: Any = None
    suffixes: list[str] = []
    fileTypes: list[str] = []
    file_types: list[str] = []
    content: Union[str, None] = None
    password: bool = False
    options: list[str] = []
    name: str = ""
    display_name: Optional[str] = None
    advanced: bool = False
    root:bool = False

    def to_dict(self):
        result = self.dict()
        # Remove key if it is None
        for key in list(result.keys()):
            if result[key] is None or result[key] == []:
                del result[key]
        result["type"] = result.pop("field_type")
        result["list"] = result.pop("is_list")

        if result.get("file_types"):
            result["fileTypes"] = result.pop("file_types")

        if self.field_type == "file":
            result["content"] = self.content
        return result

    def process_field(
        self, key: str, value: Dict[str, Any], name: Optional[str] = None
    ) -> None:
        _type = value["type"]

        # Remove 'Optional' wrapper
        if "Optional" in _type:
            _type = _type.replace("Optional[", "")[:-1]

        # Check for list type
        if "List" in _type:
            _type = _type.replace("List[", "")[:-1]
            self.is_list = True

        # Replace 'Mapping' with 'dict'
        if "Mapping" in _type:
            _type = _type.replace("Mapping", "dict")

        # Change type from str to Tool
        self.field_type = "Tool" if key in {"allowed_tools"} else self.field_type

        self.field_type = "int" if key in {"max_value_length"} else self.field_type

        # Show or not field
        self.show = bool(
            (self.required and key not in ["input_variables"])
            or key in FORCE_SHOW_FIELDS
            or "api_key" in key
        )

        # Add password field
        self.password = any(
            text in key.lower() for text in {"password", "token", "api", "key"}
        )

        # Add multline
        self.multiline = key in {
            "suffix",
            "prefix",
            "template",
            "examples",
            "code",
            "headers",
        }

        # Replace dict type with str
        if "dict" in self.field_type.lower():
            self.field_type = "code"

        if key == "dict_":
            self.field_type = "file"
            self.suffixes = [".json", ".yaml", ".yml"]
            self.file_types = ["json", "yaml", "yml"]

        # Replace default value with actual value
        if "default" in value:
            self.value = value["default"]

        if key == "headers":
            self.value = """{'Authorization':
            'Bearer <token>'}"""

        # Add options to openai
        if name == "OpenAI" and key == "model_name":
            self.options = constants.OPENAI_MODELS
            self.is_list = True
        elif name == "ChatOpenAI" and key == "model_name":
            self.options = constants.CHAT_OPENAI_MODELS
            self.is_list = True


class TemplateField(TemplateFieldCreator):
    pass
