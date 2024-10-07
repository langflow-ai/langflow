from enum import Enum

from pydantic import BaseModel, Field, field_validator


class FormatterType(str, Enum):
    date = "date"
    text = "text"
    number = "number"
    json = "json"


class Column(BaseModel):
    display_name: str
    name: str
    sortable: bool = Field(default=True)
    filterable: bool = Field(default=True)
    type: str | None = None
    formatter: FormatterType | str | None = None
    description: str | None = None
    default: str | None = None

    @field_validator("formatter")
    def validate_formatter(cls, value, info):
        # Check if type was passed and map it to the FormatterType enum
        if info.data.get("type") == "date":
            return FormatterType.date
        if info.data.get("type") == "number":
            return FormatterType.number
        if info.data.get("type") in ["str", "string", "text"]:
            return FormatterType.text
        if info.data.get("type") == "json":
            return FormatterType.json
        if isinstance(value, str):
            return FormatterType(value)
        if isinstance(value, FormatterType):
            return value
        msg = "Invalid formatter type"
        raise ValueError(msg)


class TableSchema(BaseModel):
    columns: list[Column]
