from enum import Enum
from typing import Annotated, Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PlainSerializer,
    field_validator,
    model_serializer,
)

from lfx.field_typing.range_spec import RangeSpec
from lfx.inputs.validators import CoalesceBool


class FieldTypes(str, Enum):
    TEXT = "str"
    INTEGER = "int"
    PASSWORD = "str"  # noqa: PIE796
    FLOAT = "float"
    BOOLEAN = "bool"
    DICT = "dict"
    NESTED_DICT = "NestedDict"
    SORTABLE_LIST = "sortableList"
    CONNECTION = "connect"
    AUTH = "auth"
    FILE = "file"
    PROMPT = "prompt"
    CODE = "code"
    OTHER = "other"
    TABLE = "table"
    LINK = "link"
    SLIDER = "slider"
    TAB = "tab"
    QUERY = "query"
    TOOLS = "tools"
    MCP = "mcp"


SerializableFieldTypes = Annotated[FieldTypes, PlainSerializer(lambda v: v.value, return_type=str)]


# Base mixin for common input field attributes and methods
class BaseInputMixin(BaseModel, validate_assignment=True):  # type: ignore[call-arg]
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        extra="forbid",
        populate_by_name=True,
    )

    field_type: SerializableFieldTypes = Field(default=FieldTypes.TEXT, alias="type")

    required: bool = False
    """Specifies if the field is required. Defaults to False."""

    placeholder: str = ""
    """A placeholder string for the field. Default is an empty string."""

    show: bool = True
    """Should the field be shown. Defaults to True."""

    name: str = Field(description="Name of the field.")
    """Name of the field. Default is an empty string."""

    value: Any = ""
    """The value of the field. Default is an empty string."""

    display_name: str | None = None
    """Display name of the field. Defaults to None."""

    advanced: bool = False
    """Specifies if the field will an advanced parameter (hidden). Defaults to False."""

    input_types: list[str] | None = None
    """List of input types for the handle when the field has more than one type. Default is an empty list."""

    dynamic: bool = False
    """Specifies if the field is dynamic. Defaults to False."""

    helper_text: str | None = None
    """Adds a helper text to the field. Defaults to an empty string."""

    info: str | None = ""
    """Additional information about the field to be shown in the tooltip. Defaults to an empty string."""

    real_time_refresh: bool | None = None
    """Specifies if the field should have real time refresh. `refresh_button` must be False. Defaults to None."""

    refresh_button: bool | None = None
    """Specifies if the field should have a refresh button. Defaults to False."""

    refresh_button_text: str | None = None
    """Specifies the text for the refresh button. Defaults to None."""

    title_case: bool = False
    """Specifies if the field should be displayed in title case. Defaults to True."""

    def to_dict(self):
        return self.model_dump(exclude_none=True, by_alias=True)

    @field_validator("field_type", mode="before")
    @classmethod
    def validate_field_type(cls, v):
        try:
            return FieldTypes(v)
        except ValueError:
            return FieldTypes.OTHER

    @model_serializer(mode="wrap")
    def serialize_model(self, handler):
        dump = handler(self)
        if "field_type" in dump:
            dump["type"] = dump.pop("field_type")
        dump["_input_type"] = self.__class__.__name__
        return dump


class ToolModeMixin(BaseModel):
    tool_mode: bool = False


class InputTraceMixin(BaseModel):
    trace_as_input: bool = True


class MetadataTraceMixin(BaseModel):
    trace_as_metadata: bool = True


# Mixin for input fields that can be listable
class ListableInputMixin(BaseModel):
    is_list: bool = Field(default=False, alias="list")
    list_add_label: str | None = Field(default="Add More")


# Specific mixin for fields needing database interaction
class DatabaseLoadMixin(BaseModel):
    load_from_db: bool = Field(default=True)


class AuthMixin(BaseModel):
    auth_tooltip: str | None = Field(default="")


class QueryMixin(BaseModel):
    separator: str | None = Field(default=None)
    """Separator for the query input. Defaults to None."""


# Specific mixin for fields needing file interaction
class FileMixin(BaseModel):
    file_path: list[str] | str | None = Field(default="")
    file_types: list[str] = Field(default=[], alias="fileTypes")
    temp_file: bool = Field(default=False)

    @field_validator("file_path")
    @classmethod
    def validate_file_path(cls, v):
        if v is None or v == "":
            return v
        # If it's already a list, validate each element is a string
        if isinstance(v, list):
            for item in v:
                if not isinstance(item, str):
                    msg = "All file paths must be strings"
                    raise TypeError(msg)
            return v
        # If it's a single string, that's also valid
        if isinstance(v, str):
            return v
        msg = "file_path must be a string, list of strings, or None"
        raise ValueError(msg)

    @field_validator("file_types")
    @classmethod
    def validate_file_types(cls, v):
        if not isinstance(v, list):
            msg = "file_types must be a list"
            raise ValueError(msg)  # noqa: TRY004
        # types should be a list of extensions without the dot
        for file_type in v:
            if not isinstance(file_type, str):
                msg = "file_types must be a list of strings"
                raise ValueError(msg)  # noqa: TRY004
            if file_type.startswith("."):
                msg = "file_types should not start with a dot"
                raise ValueError(msg)
        return v


class RangeMixin(BaseModel):
    range_spec: RangeSpec | None = None


class DropDownMixin(BaseModel):
    options: list[str] | None = None
    """List of options for the field. Only used when is_list=True. Default is an empty list."""
    options_metadata: list[dict[str, Any]] | None = None
    """List of dictionaries with metadata for each option."""
    combobox: CoalesceBool = False
    """Variable that defines if the user can insert custom values in the dropdown."""
    dialog_inputs: dict[str, Any] | None = None
    """Dictionary of dialog inputs for the field. Default is an empty object."""
    toggle: bool = False
    """Variable that defines if a toggle button is shown."""
    toggle_value: bool | None = None
    """Variable that defines the value of the toggle button. Defaults to None."""
    toggle_disable: bool | None = None
    """Variable that defines if the toggle button is disabled. Defaults to None."""

    @field_validator("toggle_value")
    @classmethod
    def validate_toggle_value(cls, v):
        if v is not None and not isinstance(v, bool):
            msg = "toggle_value must be a boolean or None"
            raise ValueError(msg)
        return v


class SortableListMixin(BaseModel):
    helper_text: str | None = None
    """Adds a helper text to the field. Defaults to an empty string."""
    helper_text_metadata: dict[str, Any] | None = None
    """Dictionary of metadata for the helper text."""
    search_category: list[str] = Field(default=[])
    """Specifies the category of the field. Defaults to an empty list."""
    options: list[dict[str, Any]] = Field(default_factory=list)
    """List of dictionaries with metadata for each option."""
    limit: int | None = None
    """Specifies the limit of the field. Defaults to None."""


class ConnectionMixin(BaseModel):
    helper_text: str | None = None
    """Adds a helper text to the field. Defaults to an empty string."""
    helper_text_metadata: dict[str, Any] | None = None
    """Dictionary of metadata for the helper text."""
    connection_link: str | None = None
    """Specifies the link of the connection. Defaults to an empty string."""
    button_metadata: dict[str, Any] | None = None
    """Dictionary of metadata for the button."""
    search_category: list[str] = Field(default=[])
    """Specifies the category of the field. Defaults to an empty list."""
    options: list[dict[str, Any]] = Field(default_factory=list)
    """List of dictionaries with metadata for each option."""


class TabMixin(BaseModel):
    """Mixin for tab input fields that allows a maximum of 3 values, each with a maximum of 20 characters."""

    options: list[str] = Field(default_factory=list, max_length=3)
    """List of tab options. Maximum of 3 values allowed."""

    @field_validator("options")
    @classmethod
    def validate_options(cls, v):
        """Validate that there are at most 3 tab values and each value has at most 20 characters."""
        max_tab_options = 3
        max_tab_option_length = 20

        if len(v) > max_tab_options:
            msg = f"Maximum of {max_tab_options} tab values allowed. Got {len(v)} values."
            raise ValueError(msg)

        for i, value in enumerate(v):
            if len(value) > max_tab_option_length:
                msg = (
                    f"Tab value at index {i} exceeds maximum length of {max_tab_option_length} "
                    f"characters. Got {len(value)} characters."
                )
                raise ValueError(msg)

        return v


class MultilineMixin(BaseModel):
    multiline: CoalesceBool = True


class LinkMixin(BaseModel):
    icon: str | None = None
    """Icon to be displayed in the link."""
    text: str | None = None
    """Text to be displayed in the link."""


class SliderMixin(BaseModel):
    min_label: str = Field(default="")
    max_label: str = Field(default="")
    min_label_icon: str = Field(default="")
    max_label_icon: str = Field(default="")
    slider_buttons: bool = Field(default=False)
    slider_buttons_options: list[str] = Field(default=[])
    slider_input: bool = Field(default=False)


class TableMixin(BaseModel):
    # For now we'll use simple types - in a full implementation these would be proper schema classes
    table_schema: dict | list | None = None
    trigger_text: str = Field(default="Open table")
    trigger_icon: str = Field(default="Table")
    table_icon: str = Field(default="Table")
    table_options: dict | None = None


class McpMixin(BaseModel):
    """Mixin for MCP input fields."""


class PromptFieldMixin(BaseModel):
    """Mixin for prompt input fields."""


class ToolsMixin(BaseModel):
    """Mixin for tools input fields."""
