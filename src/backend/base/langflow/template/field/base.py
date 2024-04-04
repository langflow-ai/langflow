from typing import Any, Callable, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator, model_serializer, model_validator

from langflow.field_typing.range_spec import RangeSpec


class TemplateField(BaseModel):
    model_config = ConfigDict()

    field_type: str = Field(default="str", serialization_alias="type")
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

    value: Any = ""
    """The value of the field. Default is None."""

    file_types: list[str] = Field(default=[], serialization_alias="fileTypes")
    """List of file types associated with the field . Default is an empty list."""

    file_path: Optional[str] = ""
    """The file path of the field if it is a file. Defaults to None."""

    password: bool = False
    """Specifies if the field is a password. Defaults to False."""

    options: Optional[Union[list[str], Callable]] = None
    """List of options for the field. Only used when is_list=True. Default is an empty list."""

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

    range_spec: Optional[RangeSpec] = Field(default=None, serialization_alias="rangeSpec")
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
        if self.field_type == "Text":
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
        if value == "float" and self.range_spec is None:
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
