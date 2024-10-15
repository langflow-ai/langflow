from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

VALID_TYPES = ["date", "number", "text", "json", "integer", "int", "float", "str", "string", "boolean"]


class FormatterType(str, Enum):
    date = "date"
    text = "text"
    number = "number"
    json = "json"
    boolean = "boolean"


class Column(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    name: str
    display_name: str = Field(default="")
    sortable: bool = Field(default=True)
    filterable: bool = Field(default=True)
    formatter: FormatterType | str | None = Field(default=None, alias="type")
    description: str | None = None
    default: str | None = None

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
