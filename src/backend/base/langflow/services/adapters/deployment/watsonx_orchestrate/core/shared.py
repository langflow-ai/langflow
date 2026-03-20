"""Operation-agnostic helper contracts/utilities shared by create/update."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from fastapi import HTTPException, status
from ibm_watsonx_orchestrate_clients.tools.tool_client import ClientAPIException
from lfx.services.adapters.deployment.exceptions import DeploymentConflictError

from langflow.services.adapters.deployment.watsonx_orchestrate.core.config import create_config
from langflow.services.adapters.deployment.watsonx_orchestrate.core.retry import (
    delete_config_if_exists,
    retry_create,
    retry_rollback,
)
from langflow.services.adapters.deployment.watsonx_orchestrate.utils import extract_error_detail

if TYPE_CHECKING:
    from collections.abc import Iterator

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
