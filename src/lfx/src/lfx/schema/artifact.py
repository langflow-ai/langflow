from __future__ import annotations

from collections.abc import Generator
from enum import Enum
from typing import TYPE_CHECKING

from pydantic import BaseModel

from lfx.log.logger import logger
from lfx.schema.data import Data
from lfx.schema.encoders import CUSTOM_ENCODERS
from lfx.schema.message import Message
from lfx.serialization.serialization import serialize

if TYPE_CHECKING:
    from lfx.schema.dataframe import DataFrame  # noqa: F401


def _is_dataframe(value: object) -> bool:
    """Return True if value is an lfx DataFrame (Table) instance.

    Imported lazily so the module-level import of artifact.py does not pull
    pandas into the cold-start path. Callers that hit the runtime path pay the
    pandas import cost on first use; callers on the cold path never do.
    """
    from lfx.schema.dataframe import DataFrame as _DataFrame

    return isinstance(value, _DataFrame)


class ArtifactType(str, Enum):
    TEXT = "text"
    DATA = "data"
    OBJECT = "object"
    ARRAY = "array"
    STREAM = "stream"
    UNKNOWN = "unknown"
    MESSAGE = "message"
    RECORD = "record"


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
        case _ if _is_dataframe(value):
            result = ArtifactType.ARRAY
    if result == ArtifactType.UNKNOWN and (
        (build_result and isinstance(build_result, Generator))
        or (isinstance(value, Message) and isinstance(value.text, Generator))
    ):
        result = ArtifactType.STREAM

    return result.value


def _to_list_of_dicts(raw):
    raw_ = []
    for item in raw:
        if hasattr(item, "dict") or hasattr(item, "model_dump"):
            raw_.append(serialize(item))
        else:
            raw_.append(str(item))
    return raw_


def post_process_raw(raw, artifact_type: str):
    default_message = "Built Successfully ✨"

    if artifact_type == ArtifactType.STREAM.value:
        raw = ""
    elif artifact_type == ArtifactType.ARRAY.value:
        raw = raw.to_dict(orient="records") if _is_dataframe(raw) else _to_list_of_dicts(raw)
    elif artifact_type == ArtifactType.UNKNOWN.value and raw is not None:
        if isinstance(raw, BaseModel | dict):
            from fastapi.encoders import jsonable_encoder

            try:
                raw = jsonable_encoder(raw, custom_encoder=CUSTOM_ENCODERS)
                artifact_type = ArtifactType.OBJECT.value
            except Exception:  # noqa: BLE001
                logger.debug(f"Error converting to json: {raw} ({type(raw)})", exc_info=True)
                raw = default_message
        else:
            raw = default_message
    return raw, artifact_type
