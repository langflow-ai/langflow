from abc import ABC
from typing import Any, Optional, Union

from pydantic import BaseModel


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
    file_path: Union[str, None] = None
    password: bool = False
    options: list[str] = []
    name: str = ""
    display_name: Optional[str] = None
    advanced: bool = False
    input_types: list[str] = []
    info: Optional[str] = ""

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
            result["file_path"] = self.file_path
        return result


class TemplateField(TemplateFieldCreator):
    pass
