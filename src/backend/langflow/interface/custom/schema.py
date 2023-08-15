from pydantic import BaseModel, Field


from typing import Optional


class ClassCodeDetails(BaseModel):
    """
    A dataclass for storing details about a class.
    """

    name: str
    doc: Optional[str]
    bases: list
    attributes: list
    methods: list
    init: Optional[dict] = Field(default_factory=dict)


class CallableCodeDetails(BaseModel):
    """
    A dataclass for storing details about a callable.
    """

    name: str
    doc: Optional[str]
    args: list
    body: list
    return_type: Optional[str]
