from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

VALID_TYPES = ["date", "number", "text", "json", "integer", "int", "float", "str", "string", "boolean"]


class FormatterType(str, Enum):
    date = "date"
    text = "text"
    number = "number"
    json = "json"
    boolean = "boolean"


class EditMode(str, Enum):
    MODAL = "modal"
    INLINE = "inline"


class Column(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    name: str
    display_name: str = Field(default="")
    sortable: bool = Field(default=True)
    filterable: bool = Field(default=True)
    formatter: FormatterType | str | None = Field(default=None, alias="type")
    description: str | None = None
    default: str | None = None
    disable_edit: bool = Field(default=False)
    edit_mode: EditMode | None = Field(default=EditMode.MODAL)

    @model_validator(mode="after")
    def set_display_name(self):
        if not self.display_name:
            self.display_name = self.name
        return self

    @field_validator("formatter", mode="before")
    @classmethod
    def validate_formatter(cls, value):
        if value in {"integer", "int", "float"}:
            value = FormatterType.number
        if value in {"str", "string"}:
            value = FormatterType.text
        if value == "dict":
            value = FormatterType.json
        if isinstance(value, str):
            return FormatterType(value)
        if isinstance(value, FormatterType):
            return value
        msg = f"Invalid formatter type: {value}. Valid types are: {FormatterType}"
        raise ValueError(msg)


class TableSchema(BaseModel):
    columns: list[Column]


class FieldValidatorType(str, Enum):
    """Enum for field validation types."""

    NO_SPACES = "no_spaces"  # Prevents spaces in input
    LOWERCASE = "lowercase"  # Forces lowercase
    UPPERCASE = "uppercase"  # Forces uppercase
    EMAIL = "email"  # Validates email format
    URL = "url"  # Validates URL format
    ALPHANUMERIC = "alphanumeric"  # Only letters and numbers
    NUMERIC = "numeric"  # Only numbers
    ALPHA = "alpha"  # Only letters
    PHONE = "phone"  # Phone number format
    SLUG = "slug"  # URL slug format (lowercase, hyphens)
    USERNAME = "username"  # Alphanumeric with underscores
    PASSWORD = "password"  # Minimum security requirements  # noqa: S105


class FieldParserType(str, Enum):
    """Enum for field parser types."""

    SNAKE_CASE = "snake_case"
    CAMEL_CASE = "camel_case"
    PASCAL_CASE = "pascal_case"
    KEBAB_CASE = "kebab_case"
    LOWERCASE = "lowercase"
    UPPERCASE = "uppercase"


class TableOptions(BaseModel):
    block_add: bool = Field(default=False)
    block_delete: bool = Field(default=False)
    block_edit: bool = Field(default=False)
    block_sort: bool = Field(default=False)
    block_filter: bool = Field(default=False)
    block_hide: bool | list[str] = Field(default=False)
    block_select: bool = Field(default=False)
    hide_options: bool = Field(default=False)
    field_validators: dict[str, list[FieldValidatorType] | FieldValidatorType] | None = Field(default=None)
    field_parsers: dict[str, list[FieldParserType] | FieldParserType] | None = Field(default=None)
