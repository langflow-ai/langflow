from abc import ABC
from typing import Any, Optional, Union

from pydantic import BaseModel


class TemplateFieldCreator(BaseModel, ABC):
    field_type: str = "str"
    """The type of field this is. Default is a string."""

    required: bool = False
    """Specifies if the field is required. Defaults to False."""

    placeholder: str = ""
    """A placeholder string for the field. Default is an empty string."""

    is_list: bool = False
    """Defines if the field is a list. Default is False."""

    show: bool = True
    """Should the field be shown. Defaults to True."""

    multiline: bool = False
    """Defines if the field will allow the user to open a text editor. Default is False."""

    value: Any = None
    """The value of the field. Default is None."""

    suffixes: list[str] = []
    """List of suffixes for a file field. Default is an empty list."""

    file_types: list[str] = []
    """List of file types associated with the field. Default is an empty list. (duplicate)"""

    file_path: Union[str, None] = None
    """The file path of the field if it is a file. Defaults to None."""

    password: bool = False
    """Specifies if the field is a password. Defaults to False."""

    options: list[str] = []
    """List of options for the field. Only used when is_list=True. Default is an empty list."""

    name: str = ""
    """Name of the field. Default is an empty string."""

    display_name: Optional[str] = None
    """Display name of the field. Defaults to None."""

    advanced: bool = False
    """Specifies if the field will an advanced parameter (hidden). Defaults to False."""

    input_types: list[str] = []
    """List of input types for the handle when the field has more than one type. Default is an empty list."""

    dynamic: bool = False
    """Specifies if the field is dynamic. Defaults to False."""

    info: Optional[str] = ""
    """Additional information about the field to be shown in the tooltip. Defaults to an empty string."""

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
