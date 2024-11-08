from collections.abc import Generator
from enum import Enum

from fastapi.encoders import jsonable_encoder
from loguru import logger
from pydantic import BaseModel

from langflow.schema.data import Data
from langflow.schema.encoders import CUSTOM_ENCODERS
from langflow.schema.message import Message
from langflow.schema.serialize import recursive_serialize_or_str


class ArtifactType(str, Enum):
    TEXT = "text"
    DATA = "data"
    OBJECT = "object"
    ARRAY = "array"
    STREAM = "stream"
    UNKNOWN = "unknown"
    MESSAGE = "message"


def get_artifact_type(value, build_result=None) -> str:
    result = ArtifactType.UNKNOWN
    match value:
        case Message():
            if not isinstance(value.text, str):
                enum_value = get_artifact_type(value.text)
                result = ArtifactType(enum_value)
            else:
                result = ArtifactType.MESSAGE
        case Data():
            enum_value = get_artifact_type(value.data)
            result = ArtifactType(enum_value)

        case str():
            result = ArtifactType.TEXT

        case dict():
            result = ArtifactType.OBJECT

        case list():
            result = ArtifactType.ARRAY

    if result == ArtifactType.UNKNOWN and (
        (build_result and isinstance(build_result, Generator))
        or (isinstance(value, Message) and isinstance(value.text, Generator))
    ):
        result = ArtifactType.STREAM

    return result.value


def post_process_raw(raw, artifact_type: str):
    if artifact_type == ArtifactType.STREAM.value:
        raw = ""
    elif artifact_type == ArtifactType.ARRAY.value:
        _raw = []
        for item in raw:
            if hasattr(item, "dict") or hasattr(item, "model_dump"):
                _raw.append(recursive_serialize_or_str(item))
            else:
                _raw.append(str(item))
        raw = _raw
    elif artifact_type == ArtifactType.UNKNOWN.value and raw is not None:
        if isinstance(raw, BaseModel | dict):
            try:
                raw = jsonable_encoder(raw, custom_encoder=CUSTOM_ENCODERS)
                artifact_type = ArtifactType.OBJECT.value
            except Exception:  # noqa: BLE001
                logger.opt(exception=True).debug(f"Error converting to json: {raw} ({type(raw)})")
                raw = "Built Successfully ✨"
        else:
            raw = "Built Successfully ✨"
    return raw, artifact_type
