from enum import Enum
from typing import List, Optional

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
    formatter: Optional[FormatterType | str] = None

    @field_validator("formatter")
    def validate_formatter(cls, value):
        if isinstance(value, str):
            return FormatterType(value)
        if isinstance(value, FormatterType):
            return value
        raise ValueError("Invalid formatter type")


class TableSchema(BaseModel):
    columns: List[Column]
