from __future__ import annotations

from collections.abc import Generator
from enum import Enum
from typing import TYPE_CHECKING, Any
from uuid import UUID

from lfx.interface.utils import extract_input_variables_from_prompt
from lfx.log.logger import logger
from lfx.schema.data import Data
from lfx.schema.message import Message

# Database imports removed - lfx should be lightweight
from lfx.services.deps import get_db_service, get_settings_service

if TYPE_CHECKING:
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
    flow_id: str | UUID,
    source: Vertex,
    status,
    target: Vertex | None = None,
    error=None,
) -> None:
    """Asynchronously logs a transaction record for a vertex in a flow if transaction storage is enabled.

    This function saves transaction data to the database using langflow's CRUD functions.
    """
    try:
        settings_service = get_settings_service()
        if not settings_service or not getattr(settings_service.settings, "transactions_storage_enabled", False):
            return

        db_service = get_db_service()
        if db_service is None:
            logger.debug("Database service not available, skipping transaction logging")
            return

        if not flow_id:
            if source.graph.flow_id:
                flow_id = source.graph.flow_id
            else:
                return

        # Convert flow_id to UUID if needed
        try:
            if isinstance(flow_id, str):
                flow_id = UUID(flow_id)
        except ValueError:
            logger.debug(f"Invalid flow_id passed to log_transaction: {flow_id!r}")
            return

        # Import langflow CRUD and model dynamically to avoid circular dependencies
        try:
            from langflow.services.database.models.transactions.crud import (
                log_transaction as crud_log_transaction,
            )
            from langflow.services.database.models.transactions.model import TransactionBase

            # Extract source inputs/outputs
            source_inputs = _vertex_to_primitive_dict(source) if source else {}
            source_outputs = {}
            if source:
                try:
                    # First try to get results from vertex.results dict (populated by ComponentVertex.add_result)
                    if hasattr(source, "results") and source.results:
                        # Serialize Data objects to dicts
                        for key, value in source.results.items():
                            if hasattr(value, "model_dump"):
                                source_outputs[key] = value.model_dump()
                            elif isinstance(value, dict | str | int | float | bool | list):
                                source_outputs[key] = value
                    # Fallback to built_result
                    elif hasattr(source, "built_result"):
                        if hasattr(source.built_result, "model_dump"):
                            source_outputs = source.built_result.model_dump()
                        elif isinstance(source.built_result, dict):
                            source_outputs = source.built_result
                except Exception:
                    pass

            transaction = TransactionBase(
                flow_id=flow_id,
                vertex_id=source.id,
                target_id=target.id if target else None,
                inputs=source_inputs,
                outputs=source_outputs,
                status=str(status),
                error=str(error) if error else None,
            )

            from lfx.services.deps import session_scope

            async with session_scope() as session:
                await crud_log_transaction(session, transaction)

            logger.debug(f"Transaction saved to DB: vertex={source.id}, flow={flow_id}, status={status}")
        except ImportError:
            # Langflow CRUD not available, fall back to debug logging only
            logger.debug(f"Transaction logged (no DB): vertex={source.id}, flow={flow_id}, status={status}")
    except Exception as exc:  # noqa: BLE001
        logger.debug(f"Error logging transaction: {exc!s}")


async def log_vertex_build(
    *,
    flow_id: str | UUID,
    vertex_id: str,
    valid: bool,
    params: Any,
    data: dict | Any,
    artifacts: dict | None = None,
) -> None:
    """Asynchronously logs a vertex build record if vertex build storage is enabled.

    This function saves vertex build data to the database using langflow's CRUD functions.
    """
    try:
        settings_service = get_settings_service()
        if not settings_service or not getattr(settings_service.settings, "vertex_builds_storage_enabled", False):
            return

        db_service = get_db_service()
        if db_service is None:
            logger.debug("Database service not available, skipping vertex build logging")
            return

        try:
            if isinstance(flow_id, str):
                flow_id = UUID(flow_id)
        except ValueError:
            logger.debug(f"Invalid flow_id passed to log_vertex_build: {flow_id!r}")
            return

        # Import langflow CRUD and model dynamically to avoid circular dependencies
        try:
            from langflow.services.database.models.vertex_builds.crud import (
                log_vertex_build as crud_log_vertex_build,
            )
            from langflow.services.database.models.vertex_builds.model import VertexBuildBase

            # Serialize data if it has model_dump method (Pydantic model)
            data_dict = data.model_dump() if hasattr(data, "model_dump") else (data if isinstance(data, dict) else {})
            params_str = str(params) if params else None

            vertex_build = VertexBuildBase(
                flow_id=flow_id,
                id=vertex_id,
                valid=valid,
                params=params_str,
                data=data_dict,
                artifacts=artifacts or {},
            )

            from lfx.services.deps import session_scope

            async with session_scope() as session:
                await crud_log_vertex_build(session, vertex_build)

            logger.debug(f"Vertex build saved to DB: vertex={vertex_id}, flow={flow_id}, valid={valid}")
        except ImportError:
            # Langflow CRUD not available, fall back to debug logging only
            logger.debug(f"Vertex build logged (no DB): vertex={vertex_id}, flow={flow_id}, valid={valid}")
    except Exception as exc:  # noqa: BLE001
        logger.debug(f"Error logging vertex build: {exc}")


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
