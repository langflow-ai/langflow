import json
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional
from collections.abc import Generator
from uuid import UUID

from langchain_core.documents import Document
from loguru import logger
from pydantic import BaseModel
from pydantic.v1 import BaseModel as V1BaseModel

from langflow.interface.utils import extract_input_variables_from_prompt
from langflow.schema.data import Data
from langflow.schema.message import Message
from langflow.services.database.models.transactions.crud import log_transaction as crud_log_transaction
from langflow.services.database.models.transactions.model import TransactionBase
from langflow.services.database.models.vertex_builds.crud import log_vertex_build as crud_log_vertex_build
from langflow.services.database.models.vertex_builds.model import VertexBuildBase
from langflow.services.database.utils import session_getter
from langflow.services.deps import get_db_service, get_settings_service

if TYPE_CHECKING:
    from langflow.api.v1.schemas import ResultDataResponse
    from langflow.graph.vertex.base import Vertex


class UnbuiltObject:
    pass


class UnbuiltResult:
    pass


class ArtifactType(str, Enum):
    TEXT = "text"
    RECORD = "record"
    OBJECT = "object"
    ARRAY = "array"
    STREAM = "stream"
    UNKNOWN = "unknown"
    MESSAGE = "message"


def validate_prompt(prompt: str):
    """Validate prompt."""
    if extract_input_variables_from_prompt(prompt):
        return prompt

    return fix_prompt(prompt)


def fix_prompt(prompt: str):
    """Fix prompt."""
    return prompt + " {input}"


def flatten_list(list_of_lists: list[list | Any]) -> list:
    """Flatten list of lists."""
    new_list = []
    for item in list_of_lists:
        if isinstance(item, list):
            new_list.extend(item)
        else:
            new_list.append(item)
    return new_list


def serialize_field(value):
    """Unified serialization function for handling both BaseModel and Document types,
    including handling lists of these types."""

    if isinstance(value, (list, tuple)):
        return [serialize_field(v) for v in value]
    elif isinstance(value, Document):
        return value.to_json()
    elif isinstance(value, BaseModel):
        return value.model_dump()
    elif isinstance(value, V1BaseModel):
        if hasattr(value, "to_json"):
            return value.to_json()
        else:
            return value.dict()
    elif isinstance(value, str):
        return {"result": value}
    return value


def get_artifact_type(value, build_result) -> str:
    result = ArtifactType.UNKNOWN
    match value:
        case Data():
            result = ArtifactType.RECORD

        case str():
            result = ArtifactType.TEXT

        case dict():
            result = ArtifactType.OBJECT

        case list():
            result = ArtifactType.ARRAY

        case Message():
            result = ArtifactType.MESSAGE

    if result == ArtifactType.UNKNOWN:
        if isinstance(build_result, Generator):
            result = ArtifactType.STREAM
        elif isinstance(value, Message) and isinstance(value.text, Generator):
            result = ArtifactType.STREAM

    return result.value


def post_process_raw(raw, artifact_type: str):
    if artifact_type == ArtifactType.STREAM.value:
        raw = ""

    return raw


def _vertex_to_primitive_dict(target: "Vertex") -> dict:
    """
    Cleans the parameters of the target vertex.
    """
    # Removes all keys that the values aren't python types like str, int, bool, etc.
    params = {
        key: value for key, value in target.params.items() if isinstance(value, (str, int, bool, float, list, dict))
    }
    # if it is a list we need to check if the contents are python types
    for key, value in params.items():
        if isinstance(value, list):
            params[key] = [item for item in value if isinstance(item, (str, int, bool, float, list, dict))]
    return params


async def log_transaction(
    flow_id: str | UUID, source: "Vertex", status, target: Optional["Vertex"] = None, error=None
) -> None:
    try:
        if not get_settings_service().settings.transactions_storage_enabled:
            return
        inputs = _vertex_to_primitive_dict(source)
        transaction = TransactionBase(
            vertex_id=source.id,
            target_id=target.id if target else None,
            inputs=inputs,
            # ugly hack to get the model dump with weird datatypes
            outputs=json.loads(source.result.model_dump_json()) if source.result else None,
            status=status,
            error=error,
            flow_id=flow_id if isinstance(flow_id, UUID) else UUID(flow_id),
        )
        with session_getter(get_db_service()) as session:
            inserted = crud_log_transaction(session, transaction)
            logger.debug(f"Logged transaction: {inserted.id}")
    except Exception as e:
        logger.error(f"Error logging transaction: {e}")


def log_vertex_build(
    flow_id: str,
    vertex_id: str,
    valid: bool,
    params: Any,
    data: "ResultDataResponse",
    artifacts: dict | None = None,
):
    try:
        if not get_settings_service().settings.vertex_builds_storage_enabled:
            return
        vertex_build = VertexBuildBase(
            flow_id=flow_id,
            id=vertex_id,
            valid=valid,
            params=str(params) if params else None,
            # ugly hack to get the model dump with weird datatypes
            data=json.loads(data.model_dump_json()),
            # ugly hack to get the model dump with weird datatypes
            artifacts=json.loads(json.dumps(artifacts, default=str)),
        )
        with session_getter(get_db_service()) as session:
            inserted = crud_log_vertex_build(session, vertex_build)
            logger.debug(f"Logged vertex build: {inserted.build_id}")
    except Exception as e:
        logger.exception(f"Error logging vertex build: {e}")
