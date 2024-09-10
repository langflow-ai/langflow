from enum import Enum
from typing import GenericAlias  # type: ignore
from typing import _GenericAlias  # type: ignore
from typing import _UnionGenericAlias  # type: ignore
from typing import Any
from collections.abc import Callable

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_serializer,
    model_validator,
)

from langflow.field_typing import Text
from langflow.field_typing.range_spec import RangeSpec
from langflow.helpers.custom import format_type
from langflow.type_extraction.type_extraction import post_process_type


class UndefinedType(Enum):
    undefined = "__UNDEFINED__"


UNDEFINED = UndefinedType.undefined


class Input(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    field_type: str | type | None = Field(default=str, serialization_alias="type")
    """The type of field this is. Default is a string."""

    required: bool = False
    """Specifies if the field is required. Defaults to False."""

    placeholder: str = ""
    """A placeholder string for the field. Default is an empty string."""

    is_list: bool = Field(default=False, serialization_alias="list")
    """Defines if the field is a list. Default is False."""

    show: bool = True
    """Should the field be shown. Defaults to True."""

    multiline: bool = False
    """Defines if the field will allow the user to open a text editor. Default is False."""

    value: Any = None
    """The value of the field. Default is None."""

    file_types: list[str] = Field(default=[], serialization_alias="fileTypes")
    """List of file types associated with the field . Default is an empty list."""

    file_path: str | None = ""
    """The file path of the field if it is a file. Defaults to None."""

    password: bool | None = None
    """Specifies if the field is a password. Defaults to None."""

    options: list[str] | Callable | None = None
    """List of options for the field. Only used when is_list=True. Default is an empty list."""

    name: str | None = None
    """Name of the field. Default is an empty string."""

    display_name: str | None = None
    """Display name of the field. Defaults to None."""

    advanced: bool = False
    """Specifies if the field will an advanced parameter (hidden). Defaults to False."""

    input_types: list[str] | None = None
    """List of input types for the handle when the field has more than one type. Default is an empty list."""

    dynamic: bool = False
    """Specifies if the field is dynamic. Defaults to False."""

    info: str | None = ""
    """Additional information about the field to be shown in the tooltip. Defaults to an empty string."""

    real_time_refresh: bool | None = None
    """Specifies if the field should have real time refresh. `refresh_button` must be False. Defaults to None."""

    refresh_button: bool | None = None
    """Specifies if the field should have a refresh button. Defaults to False."""
    refresh_button_text: str | None = None
    """Specifies the text for the refresh button. Defaults to None."""

    range_spec: RangeSpec | None = Field(default=None, serialization_alias="rangeSpec")
    """Range specification for the field. Defaults to None."""

    load_from_db: bool = False
    """Specifies if the field should be loaded from the database. Defaults to False."""
    title_case: bool = False
    """Specifies if the field should be displayed in title case. Defaults to True."""

    def to_dict(self):
        return self.model_dump(by_alias=True, exclude_none=True)

    @model_serializer(mode="wrap")
    def serialize_model(self, handler):
        result = handler(self)
        # If the field is str, we add the Text input type
        if self.field_type in ["str", "Text"]:
            if "input_types" not in result:
                result["input_types"] = ["Text"]
        if self.field_type == Text:
            result["type"] = "str"
        else:
            result["type"] = self.field_type
        return result

    @model_validator(mode="after")
    def validate_model(self):
        # if field_type is int, we need to set the range_spec
        if self.field_type == "int" and self.range_spec is not None:
            self.range_spec = RangeSpec.set_step_type("int", self.range_spec)
        return self

    @field_serializer("file_path")
    def serialize_file_path(self, value):
        return value if self.field_type == "file" else ""

    @field_serializer("field_type")
    def serialize_field_type(self, value, _info):
        if value is float and self.range_spec is None:
            self.range_spec = RangeSpec()
        return value

    @field_serializer("display_name")
    def serialize_display_name(self, value, _info):
        # If display_name is not set, use name and convert to title case
        # if title_case is True
        if value is None:
            # name is probably a snake_case string
            # Ex: "file_path" -> "File Path"
            value = self.name.replace("_", " ")
            if self.title_case:
                value = value.title()
        return value

    @field_validator("file_types")
    def validate_file_types(cls, value):
        if not isinstance(value, list):
            raise ValueError("file_types must be a list")
        return [
            (f".{file_type}" if isinstance(file_type, str) and not file_type.startswith(".") else file_type)
            for file_type in value
        ]

    @field_validator("field_type", mode="before")
    @classmethod
    def validate_type(cls, v):
        # If the user passes CustomComponent as a type insteado of "CustomComponent" we need to convert it to a string
        # this should be done for all types
        # How to check if v is a type?
        if isinstance(v, (type, _GenericAlias, GenericAlias, _UnionGenericAlias)):
            v = post_process_type(v)[0]
            v = format_type(v)
        elif not isinstance(v, str):
            raise ValueError(f"type must be a string or a type, not {type(v)}")
        return v


class Output(BaseModel):
    types: list[str] = Field(default=[])
    """List of output types for the field."""

    selected: str | None = Field(default=None)
    """The selected output type for the field."""

    name: str = Field(description="The name of the field.")
    """The name of the field."""

    hidden: bool | None = Field(default=None)
    """Dictates if the field is hidden."""

    display_name: str | None = Field(default=None)
    """The display name of the field."""

    method: str | None = Field(default=None)
    """The method to use for the output."""

    value: Any | None = Field(default=UNDEFINED)
    """The result of the Output. Dynamically updated as execution occurs."""

    cache: bool = Field(default=True)

    def to_dict(self):
        return self.model_dump(by_alias=True, exclude_none=True)

    def add_types(self, _type: list[Any]):
        if self.types is None:
            self.types = []
        self.types.extend([t for t in _type if t not in self.types])

    def set_selected(self):
        if not self.selected and self.types:
            self.selected = self.types[0]

    @model_serializer(mode="wrap")
    def serialize_model(self, handler):
        result = handler(self)
        if self.value == UNDEFINED:
            result["value"] = UNDEFINED.value

        return result

    @model_validator(mode="after")
    def validate_model(self):
        if self.value == UNDEFINED.value:
            self.value = UNDEFINED
        if self.name is None:
            raise ValueError("name must be set")
        if self.display_name is None:
            self.display_name = self.name
        return self
