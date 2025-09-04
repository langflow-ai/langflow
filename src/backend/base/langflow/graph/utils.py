from __future__ import annotations

from collections.abc import Generator
from enum import Enum
from typing import TYPE_CHECKING, Any
from uuid import UUID

import pandas as pd

from langflow.interface.utils import extract_input_variables_from_prompt
from langflow.logging.logger import logger
from langflow.schema.data import Data
from langflow.schema.message import Message
from langflow.serialization.serialization import get_max_items_length, get_max_text_length, serialize
from langflow.services.database.models.transactions.crud import log_transaction as crud_log_transaction
from langflow.services.database.models.transactions.crud import log_transactions_batch as crud_log_transactions_batch
from langflow.services.database.models.transactions.model import TransactionBase
from langflow.services.database.models.vertex_builds.crud import log_vertex_build as crud_log_vertex_build
from langflow.services.database.models.vertex_builds.crud import log_vertex_builds_batch as crud_log_vertex_builds_batch
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


def prepare_transaction(
    flow_id: str | UUID, source: Vertex, status, target: Vertex | None = None, error=None
) -> TransactionBase | None:
    """Prepare a transaction object from vertex data.

    Converts vertex parameters and results into a TransactionBase object suitable for database storage.
    Handles serialization of complex types like DataFrames.

    Args:
        flow_id: The flow ID
        source: Source vertex
        status: Transaction status
        target: Optional target vertex
        error: Optional error information

    Returns:
        TransactionBase object ready for database insertion, or None if flow_id is missing
    """
    if not flow_id:
        if source.graph and source.graph.flow_id:
            flow_id = source.graph.flow_id
        else:
            return None

    inputs = _vertex_to_primitive_dict(source)

    # Convert the result to a serializable format
    outputs = None
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

    return TransactionBase(
        vertex_id=source.id,
        target_id=target.id if target else None,
        inputs=serialize(inputs, max_length=get_max_text_length(), max_items=get_max_items_length()),
        outputs=serialize(outputs, max_length=get_max_text_length(), max_items=get_max_items_length()),
        status=status,
        error=error,
        flow_id=flow_id,
    )


async def log_transaction(
    flow_id: str | UUID, source: Vertex, status, target: Vertex | None = None, error=None
) -> None:
    """Asynchronously logs a transaction record for a vertex in a flow if transaction storage is enabled.

    This is kept for backward compatibility but now uses the batch logging approach internally.
    """
    try:
        if not get_settings_service().settings.transactions_storage_enabled:
            return

        transaction = prepare_transaction(flow_id, source, status, target, error)
        if not transaction:
            return

        async with session_getter(get_db_service()) as session:
            with session.no_autoflush:
                inserted = await crud_log_transaction(session, transaction)
                if inserted:
                    await logger.adebug(f"Logged transaction: {inserted.id}")
    except Exception as exc:  # noqa: BLE001
        await logger.aerror(f"Error logging transaction: {exc!s}")


async def flush_transaction_queue(transaction_queue: list[tuple[str | UUID, Any, str, Any | None, Any]]) -> None:
    """Flush a queue of transactions to the database in batch.

    Takes a list of transaction tuples and processes them all at once to avoid
    database contention and deadlocks.

    Args:
        transaction_queue: List of tuples containing (flow_id, source, status, target, error)
    """
    if not transaction_queue:
        return

    if not get_settings_service().settings.transactions_storage_enabled:
        return

    transactions_to_log = []

    for flow_id, source, status, target, error in transaction_queue:
        try:
            transaction = prepare_transaction(flow_id, source, status, target, error)
        except Exception as e:  # noqa: BLE001
            logger.debug(f"Skipping invalid transaction during prepare: {e!s}")
            continue
        if transaction:
            transactions_to_log.append(transaction)

    if transactions_to_log:
        try:
            async with session_getter(get_db_service()) as session:
                await crud_log_transactions_batch(session, transactions_to_log)
                logger.debug(f"Flushed {len(transactions_to_log)} transactions to database")
        except Exception as exc:  # noqa: BLE001
            logger.error(f"Error flushing transaction queue: {exc!s}")


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
            await logger.adebug(f"Logged vertex build: {inserted.build_id}")
    except Exception:  # noqa: BLE001
        await logger.aexception("Error logging vertex build")


def prepare_vertex_build(
    flow_id: str | UUID,
    vertex_id: str,
    *,
    valid: bool,
    params: Any,
    data: ResultDataResponse | dict,
    artifacts: dict | None = None,
) -> VertexBuildBase | None:
    """Prepare a vertex build object from parameters.

    Converts parameters and data into a VertexBuildBase object suitable for database storage.
    Handles serialization of complex types.

    Args:
        flow_id: The flow ID
        vertex_id: The vertex ID
        valid: Whether the build was valid
        params: Build parameters
        data: Result data
        artifacts: Optional artifacts

    Returns:
        VertexBuildBase object ready for database insertion, or None if flow_id is invalid
    """
    try:
        if isinstance(flow_id, str):
            flow_id = UUID(flow_id)
    except ValueError:
        logger.warning(f"Invalid flow_id passed to prepare_vertex_build: {flow_id!r}")
        return None

    return VertexBuildBase(
        flow_id=flow_id,
        id=vertex_id,
        valid=valid,
        params=str(params) if params else None,
        data=serialize(data, max_length=get_max_text_length(), max_items=get_max_items_length()),
        artifacts=serialize(artifacts, max_length=get_max_text_length(), max_items=get_max_items_length()),
    )


async def flush_vertex_build_queue(
    vertex_build_queue: list[tuple[str | UUID, str, bool, Any, ResultDataResponse | dict, dict | None]],
) -> None:
    """Flush a queue of vertex builds to the database in batch.

    Takes a list of vertex build tuples and processes them all at once to avoid
    database contention and deadlocks.

    Args:
        vertex_build_queue: List of tuples containing (flow_id, vertex_id, valid, params, data, artifacts)
    """
    if not vertex_build_queue:
        return

    if not get_settings_service().settings.vertex_builds_storage_enabled:
        return

    vertex_builds_to_log = []

    for flow_id, vertex_id, valid, params, data, artifacts in vertex_build_queue:
        vertex_build = prepare_vertex_build(
            flow_id, vertex_id, valid=valid, params=params, data=data, artifacts=artifacts
        )
        if vertex_build:
            vertex_builds_to_log.append(vertex_build)

    if vertex_builds_to_log:
        try:
            async with session_getter(get_db_service()) as session:
                await crud_log_vertex_builds_batch(session, vertex_builds_to_log)
                logger.debug(f"Flushed {len(vertex_builds_to_log)} vertex builds to database")
        except Exception as exc:  # noqa: BLE001
            logger.error(f"Error flushing vertex build queue: {exc!s}")


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
    from langflow.graph.schema import InterfaceComponentTypes

    return any(InterfaceComponentTypes.ChatOutput in vertex.id for vertex in vertices)
