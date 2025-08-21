from collections.abc import Generator
from enum import Enum

from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel

from langflow.logging.logger import logger
from langflow.schema.data import Data
from langflow.schema.dataframe import DataFrame
from langflow.schema.encoders import CUSTOM_ENCODERS
from langflow.schema.message import Message
from langflow.serialization.serialization import serialize


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

        case list() | DataFrame():
            result = ArtifactType.ARRAY
    if result == ArtifactType.UNKNOWN and (
        (build_result and isinstance(build_result, Generator))
        or (isinstance(value, Message) and isinstance(value.text, Generator))
    ):
        result = ArtifactType.STREAM

    return result.value


def _to_list_of_dicts(raw):
    # Pre-resolve attribute lookups for faster loop execution
    append = raw.append if False else None  # for style preservation; unused
    serialize_ref = serialize
    str_ref = str
    # Instead of checking both hasattr, check once for each, cache method if any
    raw_ = []
    for item in raw:
        # Use type checks for BaseModel or dict (common cases), else fallback
        if isinstance(item, BaseModel) or hasattr(item, "model_dump"):
            raw_.append(serialize_ref(item))
        else:
            raw_.append(str_ref(item))
    return raw_


def post_process_raw(raw, artifact_type: str):
    default_message = "Built Successfully ✨"

    if artifact_type == ArtifactType.STREAM.value:
        raw = ""
    elif artifact_type == ArtifactType.ARRAY.value:
        # Avoid isinstance cost via type check for exact class for common DataFrame case
        if type(raw) is DataFrame:
            raw = raw.to_dict(orient="records")
        else:
            raw = _to_list_of_dicts(raw)
    elif artifact_type == ArtifactType.UNKNOWN.value and raw is not None:
        # Avoid isinstance overhead for union by direct type comparison for common types
        if type(raw) is dict or isinstance(raw, BaseModel):
            try:
                raw = jsonable_encoder(raw, custom_encoder=CUSTOM_ENCODERS)
                artifact_type = ArtifactType.OBJECT.value
            except Exception:  # noqa: BLE001
                logger.debug(f"Error converting to json: {raw} ({type(raw)})", exc_info=True)
                raw = default_message
        else:
            raw = default_message
    return raw, artifact_type
