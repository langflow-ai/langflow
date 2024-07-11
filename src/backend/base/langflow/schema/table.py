from enum import Enum
from typing import List, Optional

from pydantic import BaseModel


class FormatterType(str, Enum):
    date = "date"
    text = "text"
    number = "number"
    currency = "currency"
    json = "json"


class Column(BaseModel):
    header: str
    field: str
    sortable: bool
    filterable: bool
    width: int
    formatter: Optional[FormatterType] = None


class TableSchema(BaseModel):
    columns: List[Column]
