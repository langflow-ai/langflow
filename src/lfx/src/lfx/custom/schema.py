from typing import Any

from pydantic import BaseModel, Field


class ClassCodeDetails(BaseModel):
    """A dataclass for storing details about a class."""

    name: str
    doc: str | None = None
    bases: list
    attributes: list
    methods: list
    init: dict | None = Field(default_factory=dict)


class CallableCodeDetails(BaseModel):
    """A dataclass for storing details about a callable."""

    name: str
    doc: str | None = None
    args: list
    body: list
    return_type: Any | None = None
    has_return: bool = False


class MissingDefault:
    """A class to represent a missing default value."""

    def __repr__(self) -> str:
        return "MISSING"
