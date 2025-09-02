from typing import Annotated
from uuid import UUID

from pydantic import BeforeValidator


def str_to_uuid(v: str | UUID) -> UUID:
    if isinstance(v, str):
        return UUID(v)
    return v


UUIDstr = Annotated[UUID, BeforeValidator(str_to_uuid)]
