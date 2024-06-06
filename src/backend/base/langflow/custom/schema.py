from typing import Any, Optional

from pydantic import BaseModel, Field


class ClassCodeDetails(BaseModel):
    """
    A dataclass for storing details about a class.
    """

    name: str
    doc: Optional[str] = None
    bases: list
    attributes: list
    methods: list
    init: Optional[dict] = Field(default_factory=dict)


class CallableCodeDetails(BaseModel):
    """
    A dataclass for storing details about a callable.
    """

    name: str
    doc: Optional[str] = None
    args: list
    body: list
    return_type: Optional[Any] = None
    has_return: bool = False


class MissingDefault:
    """
    A class to represent a missing default value.
    """

    def __repr__(self):
        return "MISSING"
