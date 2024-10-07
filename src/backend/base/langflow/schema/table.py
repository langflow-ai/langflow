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
    formatter: FormatterType | str | None = None

    @field_validator("formatter")
    def validate_formatter(cls, value):
        if isinstance(value, str):
            return FormatterType(value)
        if isinstance(value, FormatterType):
            return value
        msg = "Invalid formatter type"
        raise ValueError(msg)


class TableSchema(BaseModel):
    columns: list[Column]
