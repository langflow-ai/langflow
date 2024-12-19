from collections.abc import AsyncIterator, Generator, Iterator
from datetime import datetime
from typing import Annotated
from uuid import UUID

from loguru import logger
from pydantic import BaseModel, BeforeValidator
from pydantic.v1 import BaseModel as BaseModelV1


def str_to_uuid(v: str | UUID) -> UUID:
    if isinstance(v, str):
        return UUID(v)
    return v


UUIDstr = Annotated[UUID, BeforeValidator(str_to_uuid)]


def recursive_serialize_or_str(obj):
    try:
        if isinstance(obj, type) and issubclass(obj, BaseModel | BaseModelV1):
            # This a type BaseModel and not an instance of it
            return repr(obj)
        if isinstance(obj, str):
            return obj
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, dict):
            return {k: recursive_serialize_or_str(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [recursive_serialize_or_str(v) for v in obj]
        if isinstance(obj, BaseModel | BaseModelV1):
            if hasattr(obj, "model_dump"):
                obj_dict = obj.model_dump()
            elif hasattr(obj, "dict"):
                obj_dict = obj.dict()
            return {k: recursive_serialize_or_str(v) for k, v in obj_dict.items()}

        if isinstance(obj, AsyncIterator | Generator | Iterator):
            # contain memory addresses
            # without consuming the iterator
            # return list(obj) consumes the iterator
            # return f"{obj}" this generates '<generator object BaseChatModel.stream at 0x33e9ec770>'
            # it is not useful
            return "Unconsumed Stream"
        if hasattr(obj, "dict") and not isinstance(obj, type):
            return {k: recursive_serialize_or_str(v) for k, v in obj.dict().items()}
        if hasattr(obj, "model_dump") and not isinstance(obj, type):
            return {k: recursive_serialize_or_str(v) for k, v in obj.model_dump().items()}
        return str(obj)
    except Exception:  # noqa: BLE001
        logger.debug(f"Cannot serialize object {obj}")
        return str(obj)
