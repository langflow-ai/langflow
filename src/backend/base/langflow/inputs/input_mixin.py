from enum import Enum
from typing import Annotated, Any, Optional

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer, field_validator, model_serializer

from langflow.field_typing.range_spec import RangeSpec
from langflow.inputs.validators import CoalesceBool
from langflow.schema.table import Column, TableSchema


class FieldTypes(str, Enum):
    TEXT = "str"
    INTEGER = "int"
    PASSWORD = "str"
    FLOAT = "float"
    BOOLEAN = "bool"
    DICT = "dict"
    NESTED_DICT = "NestedDict"
    FILE = "file"
    PROMPT = "prompt"
    OTHER = "other"
    TABLE = "table"


SerializableFieldTypes = Annotated[FieldTypes, PlainSerializer(lambda v: v.value, return_type=str)]


# Base mixin for common input field attributes and methods
class BaseInputMixin(BaseModel, validate_assignment=True):
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    field_type: Optional[SerializableFieldTypes] = Field(default=FieldTypes.TEXT)

    required: bool = False
    """Specifies if the field is required. Defaults to False."""

    placeholder: str = ""
    """A placeholder string for the field. Default is an empty string."""

    show: bool = True
    """Should the field be shown. Defaults to True."""

    value: Any = ""
    """The value of the field. Default is an empty string."""

    name: Optional[str] = None
    """Name of the field. Default is an empty string."""

    display_name: Optional[str] = None
    """Display name of the field. Defaults to None."""

    advanced: bool = False
    """Specifies if the field will an advanced parameter (hidden). Defaults to False."""

    input_types: Optional[list[str]] = None
    """List of input types for the handle when the field has more than one type. Default is an empty list."""

    dynamic: bool = False
    """Specifies if the field is dynamic. Defaults to False."""

    info: Optional[str] = ""
    """Additional information about the field to be shown in the tooltip. Defaults to an empty string."""

    real_time_refresh: Optional[bool] = None
    """Specifies if the field should have real time refresh. `refresh_button` must be False. Defaults to None."""

    refresh_button: Optional[bool] = None
    """Specifies if the field should have a refresh button. Defaults to False."""
    refresh_button_text: Optional[str] = None
    """Specifies the text for the refresh button. Defaults to None."""

    title_case: bool = False
    """Specifies if the field should be displayed in title case. Defaults to True."""

    def to_dict(self):
        return self.model_dump(exclude_none=True, by_alias=True)

    @field_validator("field_type", mode="before")
    @classmethod
    def validate_field_type(cls, v):
        if v not in FieldTypes:
            return FieldTypes.OTHER
        return FieldTypes(v)

    @model_serializer(mode="wrap")
    def serialize_model(self, handler):
        dump = handler(self)
        if "field_type" in dump:
            dump["type"] = dump.pop("field_type")
        dump["_input_type"] = self.__class__.__name__
        return dump


class InputTraceMixin(BaseModel):
    trace_as_input: bool = True


class MetadataTraceMixin(BaseModel):
    trace_as_metadata: bool = True


# Mixin for input fields that can be listable
class ListableInputMixin(BaseModel):
    is_list: bool = Field(default=False, serialization_alias="list")


# Specific mixin for fields needing database interaction
class DatabaseLoadMixin(BaseModel):
    load_from_db: bool = Field(default=True)


# Specific mixin for fields needing file interaction
class FileMixin(BaseModel):
    file_path: Optional[str] = Field(default="")
    file_types: list[str] = Field(default=[], serialization_alias="fileTypes")

    @field_validator("file_types")
    @classmethod
    def validate_file_types(cls, v):
        if not isinstance(v, list):
            raise ValueError("file_types must be a list")
        # types should be a list of extensions without the dot
        for file_type in v:
            if not isinstance(file_type, str):
                raise ValueError("file_types must be a list of strings")
            if file_type.startswith("."):
                raise ValueError("file_types should not start with a dot")
        return v


class RangeMixin(BaseModel):
    range_spec: Optional[RangeSpec] = None


class DropDownMixin(BaseModel):
    options: Optional[list[str]] = None
    """List of options for the field. Only used when is_list=True. Default is an empty list."""
    combobox: CoalesceBool = False
    """Variable that defines if the user can insert custom values in the dropdown."""


class MultilineMixin(BaseModel):
    multiline: CoalesceBool = True


class TableMixin(BaseModel):
    table_schema: Optional[TableSchema | list[Column]] = None

    @field_validator("table_schema")
    @classmethod
    def validate_table_schema(cls, v):
        if isinstance(v, list) and all(isinstance(column, Column) for column in v):
            return TableSchema(columns=v)
        if isinstance(v, TableSchema):
            return v
        raise ValueError("table_schema must be a TableSchema or a list of Columns")
