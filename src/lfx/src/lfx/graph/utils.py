from __future__ import annotations

from collections.abc import Generator
from enum import Enum
from typing import TYPE_CHECKING, Any
from uuid import UUID

import pandas as pd
from loguru import logger

from lfx.interface.utils import extract_input_variables_from_prompt
from lfx.schema.data import Data
from lfx.schema.message import Message
from lfx.serialization.serialization import get_max_items_length, get_max_text_length, serialize
from lfx.services.database.models.transactions.crud import log_transaction as crud_log_transaction
from lfx.services.database.models.transactions.model import TransactionBase
from lfx.services.database.models.vertex_builds.crud import log_vertex_build as crud_log_vertex_build
from lfx.services.database.models.vertex_builds.model import VertexBuildBase
from lfx.services.database.utils import session_getter
from lfx.services.deps import get_db_service, get_settings_service

if TYPE_CHECKING:
    from lfx.api.v1.schemas import ResultDataResponse
    from lfx.graph.vertex.base import Vertex


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

    if result == ArtifactType.UNKNOWN and (
        isinstance(build_result, Generator) or (isinstance(value, Message) and isinstance(value.text, Generator))
    ):
        result = ArtifactType.STREAM

    return result.value


def post_process_raw(raw, artifact_type: str):
    if artifact_type == ArtifactType.STREAM.value:
        raw = ""

    return raw


def _vertex_to_primitive_dict(target: Vertex) -> dict:
    """Cleans the parameters of the target vertex."""
    # Removes all keys that the values aren't python types like str, int, bool, etc.
    params = {
        key: value for key, value in target.params.items() if isinstance(value, str | int | bool | float | list | dict)
    }
    # if it is a list we need to check if the contents are python types
    for key, value in params.items():
        if isinstance(value, list):
            params[key] = [item for item in value if isinstance(item, str | int | bool | float | list | dict)]
    return params


async def log_transaction(
    flow_id: str | UUID, source: Vertex, status, target: Vertex | None = None, error=None
) -> None:
    """Asynchronously logs a transaction record for a vertex in a flow if transaction storage is enabled.

    Serializes the source vertex's primitive parameters and result, handling pandas DataFrames as needed,
    and records transaction details including inputs, outputs, status, error, and flow ID in the database.
    If the flow ID is not provided, attempts to retrieve it from the source vertex's graph.
    Logs warnings and errors on serialization or database failures.
    """
    try:
        if not get_settings_service().settings.transactions_storage_enabled:
            return
        if not flow_id:
            if source.graph.flow_id:
                flow_id = source.graph.flow_id
            else:
                return
        inputs = _vertex_to_primitive_dict(source)

        # Convert the result to a serializable format
        if source.result:
            try:
                result_dict = source.result.model_dump()
                for key, value in result_dict.items():
                    if isinstance(value, pd.DataFrame):
                        result_dict[key] = value.to_dict()
                outputs = result_dict
            except Exception as e:  # noqa: BLE001
                logger.warning(f"Error serializing result: {e!s}")
                outputs = None
        else:
            outputs = None

        transaction = TransactionBase(
            vertex_id=source.id,
            target_id=target.id if target else None,
            inputs=serialize(inputs, max_length=get_max_text_length(), max_items=get_max_items_length()),
            outputs=serialize(outputs, max_length=get_max_text_length(), max_items=get_max_items_length()),
            status=status,
            error=error,
            flow_id=flow_id if isinstance(flow_id, UUID) else UUID(flow_id),
        )
        async with session_getter(get_db_service()) as session:
            with session.no_autoflush:
                inserted = await crud_log_transaction(session, transaction)
                if inserted:
                    logger.debug(f"Logged transaction: {inserted.id}")
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Error logging transaction: {exc!s}")


async def log_vertex_build(
    *,
    flow_id: str | UUID,
    vertex_id: str,
    valid: bool,
    params: Any,
    data: ResultDataResponse | dict,
    artifacts: dict | None = None,
) -> None:
    """Asynchronously logs a vertex build record to the database if vertex build storage is enabled.

    Serializes the provided data and artifacts with configurable length and item limits before storing.
    Converts parameters to string if present. Handles exceptions by logging errors.
    """
    try:
        if not get_settings_service().settings.vertex_builds_storage_enabled:
            return
        try:
            if isinstance(flow_id, str):
                flow_id = UUID(flow_id)
        except ValueError:
            msg = f"Invalid flow_id passed to log_vertex_build: {flow_id!r}(type: {type(flow_id)})"
            raise ValueError(msg) from None

        vertex_build = VertexBuildBase(
            flow_id=flow_id,
            id=vertex_id,
            valid=valid,
            params=str(params) if params else None,
            data=serialize(data, max_length=get_max_text_length(), max_items=get_max_items_length()),
            artifacts=serialize(artifacts, max_length=get_max_text_length(), max_items=get_max_items_length()),
        )
        async with session_getter(get_db_service()) as session:
            inserted = await crud_log_vertex_build(session, vertex_build)
            logger.debug(f"Logged vertex build: {inserted.build_id}")
    except Exception:  # noqa: BLE001
        logger.exception("Error logging vertex build")


def rewrite_file_path(file_path: str):
    file_path = file_path.replace("\\", "/")

    if ":" in file_path:
        file_path = file_path.split(":", 1)[-1]

    file_path_split = [part for part in file_path.split("/") if part]

    if len(file_path_split) > 1:
        consistent_file_path = f"{file_path_split[-2]}/{file_path_split[-1]}"
    else:
        consistent_file_path = "/".join(file_path_split)

    return [consistent_file_path]


def has_output_vertex(vertices: dict[Vertex, int]):
    return any(vertex.is_output for vertex in vertices)


def has_chat_output(vertices: dict[Vertex, int]):
    from lfx.graph.schema import InterfaceComponentTypes

    return any(InterfaceComponentTypes.ChatOutput in vertex.id for vertex in vertices)
