"""Operation-agnostic helper contracts/utilities shared by create/update."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from fastapi import HTTPException, status
from ibm_watsonx_orchestrate_clients.tools.tool_client import ClientAPIException
from lfx.services.adapters.deployment.exceptions import DeploymentConflictError, InvalidContentError

from langflow.services.adapters.deployment.watsonx_orchestrate.core.config import create_config, validate_connection
from langflow.services.adapters.deployment.watsonx_orchestrate.core.retry import (
    delete_config_if_exists,
    retry_create,
    retry_rollback,
)
from langflow.services.adapters.deployment.watsonx_orchestrate.core.tools import (
    FlowToolBindingSpec,
    create_and_upload_wxo_flow_tools_with_bindings,
)
from langflow.services.adapters.deployment.watsonx_orchestrate.payloads import WatsonxResultToolRefBinding
from langflow.services.adapters.deployment.watsonx_orchestrate.utils import extract_error_detail

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Iterator

    from lfx.services.adapters.deployment.schema import BaseFlowArtifact, IdLike
    from sqlalchemy.ext.asyncio import AsyncSession

    from langflow.services.adapters.deployment.watsonx_orchestrate.payloads import (
        WatsonxConnectionRawPayload,
        WatsonxFlowArtifactProviderData,
    )
    from langflow.services.adapters.deployment.watsonx_orchestrate.types import WxOClient

logger = logging.getLogger(__name__)


class OrderedUniqueStrs:
    """Ordered, de-duplicating string collection for deterministic plans."""

    def __init__(self, items: dict[str, None] | None = None) -> None:
        self._items: dict[str, None] = items or {}

    @classmethod
    def from_values(cls, values: list[str]) -> OrderedUniqueStrs:
        ordered = cls()
        ordered.extend(values)
        return ordered

    def __iter__(self) -> Iterator[str]:
        return iter(self._items)

    def to_list(self) -> list[str]:
        return list(self._items)

    def add(self, value: str) -> None:
        self._items.setdefault(value, None)

    def extend(self, values: list[str]) -> None:
        for value in values:
            self.add(value)

    def discard(self, value: str) -> None:
        self._items.pop(value, None)


@dataclass(slots=True)
class RawConnectionCreatePlan:
    operation_app_id: str
    provider_app_id: str
    payload: WatsonxConnectionRawPayload


@dataclass(slots=True)
class RawToolCreatePlan:
    raw_name: str
    payload: BaseFlowArtifact[WatsonxFlowArtifactProviderData]
    app_ids: list[str]


class ConnectionCreateBatchError(RuntimeError):
    """Raised when a concurrent connection-create batch partially succeeds."""

    def __init__(self, *, created_app_ids: list[str], errors: list[Exception]) -> None:
        self.created_app_ids = created_app_ids
        self.errors = errors
        super().__init__("One or more connection creations failed.")


def log_batch_errors(*, error_label: str, errors: list[Exception]) -> None:
    """Log each error from a concurrent batch while preserving first-failure raising."""
    for i, err in enumerate(errors):
        logger.exception("%s [%d/%d]: %s", error_label, i + 1, len(errors), err)


@dataclass(slots=True)
class ConnectionResolutionResult:
    operation_to_provider_app_id: dict[str, str]
    resolved_connections: dict[str, str]
    created_app_ids: list[str]


@dataclass(slots=True)
class RawToolCreateResult:
    created_tool_ids: list[str]
    snapshot_bindings: list[WatsonxResultToolRefBinding]


async def create_connection_with_conflict_mapping(
    *,
    clients: WxOClient,
    app_id: str,
    payload: WatsonxConnectionRawPayload,
    user_id: IdLike,
    db: AsyncSession,
    error_prefix: str,
) -> str:
    from lfx.services.adapters.deployment.schema import DeploymentConfig

    config_payload = DeploymentConfig(
        name=app_id,
        description=None,
        environment_variables=payload.environment_variables,
        provider_config=payload.provider_config,
    )
    try:
        return await retry_create(
            create_config,
            clients=clients,
            config=config_payload,
            user_id=user_id,
            db=db,
        )
    except (ClientAPIException, HTTPException) as exc:
        if isinstance(exc, ClientAPIException):
            status_code = exc.response.status_code
            error_detail = str(extract_error_detail(exc.response.text))
        else:
            status_code = exc.status_code
            error_detail = str(extract_error_detail(str(exc.detail)))
        is_conflict = status_code == status.HTTP_409_CONFLICT or "already exists" in error_detail.lower()
        if is_conflict:
            msg = f"{error_prefix} error details: {error_detail}"
            raise DeploymentConflictError(message=msg) from exc
        raise


async def resolve_connections_for_operations(
    *,
    clients: WxOClient,
    user_id: IdLike,
    db: AsyncSession,
    existing_app_ids: list[str],
    raw_connections_to_create: list[RawConnectionCreatePlan],
    error_prefix: str,
    validate_connection_fn: Callable[..., Awaitable[object]] = validate_connection,
    create_connection_fn: Callable[..., Awaitable[str]] = create_connection_with_conflict_mapping,
) -> ConnectionResolutionResult:
    operation_to_provider_app_id = {app_id: app_id for app_id in existing_app_ids}
    resolved_connections: dict[str, str] = {}

    if existing_app_ids:
        existing_connections: list[object] = await asyncio.gather(
            *(retry_create(validate_connection_fn, clients.connections, app_id=app_id) for app_id in existing_app_ids)
        )
        for app_id, connection in zip(existing_app_ids, existing_connections, strict=True):
            resolved_connections[app_id] = connection.connection_id  # type: ignore[attr-defined]

    if not raw_connections_to_create:
        return ConnectionResolutionResult(
            operation_to_provider_app_id=operation_to_provider_app_id,
            resolved_connections=resolved_connections,
            created_app_ids=[],
        )

    created_connections_results = await asyncio.gather(
        *(
            create_connection_fn(
                clients=clients,
                app_id=create_plan.provider_app_id,
                payload=create_plan.payload,
                user_id=user_id,
                db=db,
                error_prefix=error_prefix,
            )
            for create_plan in raw_connections_to_create
        ),
        return_exceptions=True,
    )

    create_connection_errors: list[Exception] = []
    created_app_ids_journal: list[str] = []
    for result in created_connections_results:
        if isinstance(result, BaseException):
            if isinstance(result, Exception):
                create_connection_errors.append(result)
            else:
                create_connection_errors.append(
                    RuntimeError(f"Connection create failed with non-standard exception: {type(result).__name__}")
                )
            continue
        created_app_ids_journal.append(result)
    created_app_ids = list(dict.fromkeys(created_app_ids_journal))
    if create_connection_errors:
        raise ConnectionCreateBatchError(created_app_ids=created_app_ids, errors=create_connection_errors)

    validated_created_connections: list[object] = await asyncio.gather(
        *(
            retry_create(
                validate_connection_fn,
                clients.connections,
                app_id=create_plan.provider_app_id,
            )
            for create_plan in raw_connections_to_create
        )
    )
    for create_plan, connection in zip(raw_connections_to_create, validated_created_connections, strict=True):
        operation_to_provider_app_id[create_plan.operation_app_id] = create_plan.provider_app_id
        resolved_connections[create_plan.provider_app_id] = connection.connection_id  # type: ignore[attr-defined]

    return ConnectionResolutionResult(
        operation_to_provider_app_id=operation_to_provider_app_id,
        resolved_connections=resolved_connections,
        created_app_ids=created_app_ids,
    )


def build_tool_bindings_for_raw_tool_creates(
    *,
    raw_tools_to_create: list[RawToolCreatePlan],
    operation_to_provider_app_id: dict[str, str],
    resolved_connections: dict[str, str],
) -> list[FlowToolBindingSpec]:
    tool_bindings: list[FlowToolBindingSpec] = []
    for raw_plan in raw_tools_to_create:
        binding_connections: dict[str, str] = {}
        for operation_app_id in raw_plan.app_ids:
            provider_app_id = operation_to_provider_app_id.get(operation_app_id)
            if not provider_app_id:
                msg = f"No provider app id available for operation app_id '{operation_app_id}'."
                raise InvalidContentError(message=msg)
            connection_id = resolved_connections.get(provider_app_id)
            if not connection_id:
                msg = f"No resolved connection id available for app_id '{operation_app_id}'."
                raise InvalidContentError(message=msg)
            binding_connections[provider_app_id] = connection_id
        tool_bindings.append(
            FlowToolBindingSpec(
                flow_payload=raw_plan.payload,
                connections=binding_connections,
            )
        )
    return tool_bindings


async def create_raw_tools_with_bindings(
    *,
    clients: WxOClient,
    raw_tools_to_create: list[RawToolCreatePlan],
    operation_to_provider_app_id: dict[str, str],
    resolved_connections: dict[str, str],
    resource_prefix: str,
    create_and_upload_tools_fn: Callable[..., Awaitable[list[str]]] = create_and_upload_wxo_flow_tools_with_bindings,
) -> RawToolCreateResult:
    if not raw_tools_to_create:
        return RawToolCreateResult(created_tool_ids=[], snapshot_bindings=[])

    tool_bindings = build_tool_bindings_for_raw_tool_creates(
        raw_tools_to_create=raw_tools_to_create,
        operation_to_provider_app_id=operation_to_provider_app_id,
        resolved_connections=resolved_connections,
    )
    raw_create_results = await create_and_upload_tools_fn(
        clients=clients,
        tool_bindings=tool_bindings,
        tool_name_prefix=resource_prefix,
    )

    created_tool_ids: list[str] = []
    created_snapshot_bindings: list[WatsonxResultToolRefBinding] = []
    for raw_plan, created_tool_id in zip(raw_tools_to_create, raw_create_results, strict=True):
        tool_id = str(created_tool_id).strip()
        if not tool_id:
            msg = f"Failed to create tool for raw payload '{raw_plan.raw_name}'."
            raise InvalidContentError(message=msg)
        created_tool_ids.append(tool_id)
        created_snapshot_bindings.append(
            WatsonxResultToolRefBinding(
                source_ref=raw_plan.payload.provider_data.source_ref,
                tool_id=tool_id,
                created=True,
            )
        )

    return RawToolCreateResult(
        created_tool_ids=created_tool_ids,
        snapshot_bindings=created_snapshot_bindings,
    )


async def rollback_created_app_ids(
    *,
    clients: WxOClient,
    created_app_ids: list[str],
) -> None:
    for app_id in reversed(created_app_ids):
        try:
            await retry_rollback(delete_config_if_exists, clients, app_id=app_id)
        except Exception:
            logger.exception("Rollback failed for created app_id=%s — resource may be orphaned", app_id)
