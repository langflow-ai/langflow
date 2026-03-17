"""Retry/backoff and rollback logic for the Watsonx Orchestrate adapter."""

from __future__ import annotations

import asyncio
import logging
import random
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any, TypeVar

from fastapi import HTTPException, status
from ibm_watsonx_orchestrate_clients.tools.tool_client import ClientAPIException
from lfx.services.adapters.deployment.exceptions import (
    DeploymentConflictError,
    InvalidContentError,
    InvalidDeploymentOperationError,
    InvalidDeploymentTypeError,
)

from langflow.services.adapters.deployment.watsonx_orchestrate.constants import (
    CREATE_MAX_RETRIES,
    RETRY_INITIAL_DELAY_SECONDS,
    ROLLBACK_MAX_RETRIES,
    UPDATE_MAX_RETRIES,
)

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from langflow.services.adapters.deployment.watsonx_orchestrate.types import WxOClient

T = TypeVar("T")
Operation = Callable[..., Awaitable[T]]
ShouldRetry = Callable[[Exception], bool]


async def retry_with_backoff(
    operation: Operation[T],
    max_attempts: int,
    *args: Any,
    should_retry: ShouldRetry | None = None,
    **kwargs: Any,
) -> T:
    delay_seconds = RETRY_INITIAL_DELAY_SECONDS
    for attempt in range(1, max_attempts + 1):
        try:
            return await operation(*args, **kwargs)
        except Exception as exc:
            retryable = True if should_retry is None else should_retry(exc)
            if not retryable or attempt == max_attempts:
                raise
            jittered_delay = delay_seconds * (0.5 + random.random())  # noqa: S311
            logger.info(
                "Retry attempt %d/%d after %.2fs (%s)", attempt, max_attempts, jittered_delay, type(exc).__name__
            )
            await asyncio.sleep(jittered_delay)
            delay_seconds *= 2
    msg = "Retry helper exhausted attempts without result."
    raise RuntimeError(msg)


async def retry_create(operation: Operation[T], *args: Any, **kwargs: Any) -> T:
    return await retry_with_backoff(
        operation,
        CREATE_MAX_RETRIES,
        *args,
        should_retry=is_retryable_create_exception,
        **kwargs,
    )


async def retry_update(operation: Operation[T], *args: Any, **kwargs: Any) -> T:
    """Retry write/update operations with the standard provider retry policy."""
    return await retry_with_backoff(
        operation,
        UPDATE_MAX_RETRIES,
        *args,
        should_retry=is_retryable_create_exception,
        **kwargs,
    )


async def retry_rollback(operation: Operation[T], *args: Any, **kwargs: Any) -> T:
    return await retry_with_backoff(
        operation,
        ROLLBACK_MAX_RETRIES,
        *args,
        should_retry=is_retryable_create_exception,
        **kwargs,
    )


def is_retryable_create_exception(exc: Exception) -> bool:
    non_retryable_status_codes = {
        status.HTTP_400_BAD_REQUEST,
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_409_CONFLICT,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    }
    if isinstance(exc, ClientAPIException):
        return exc.response.status_code not in non_retryable_status_codes
    if isinstance(exc, HTTPException):
        return exc.status_code not in non_retryable_status_codes
    return not isinstance(
        exc,
        (
            DeploymentConflictError,
            InvalidContentError,
            InvalidDeploymentOperationError,
            InvalidDeploymentTypeError,
        ),
    )


async def rollback_created_resources(
    *,
    clients: WxOClient,
    agent_id: str | None,
    tool_ids: list[str],
    app_id: str | None,
) -> None:
    logger.info("Rolling back resources: agent_id=%s, tool_ids=%s, app_id=%s", agent_id, tool_ids, app_id)
    if agent_id:
        try:
            await retry_rollback(delete_agent_if_exists, clients, agent_id=agent_id)
        except Exception:
            logger.exception("Rollback failed for agent_id=%s — resource may be orphaned", agent_id)
    if tool_ids:
        for tool_id in reversed(tool_ids):
            try:
                await retry_rollback(delete_tool_if_exists, clients, tool_id=tool_id)
            except Exception:
                logger.exception("Rollback failed for tool_id=%s — resource may be orphaned", tool_id)
    if app_id:
        try:
            await retry_rollback(delete_config_if_exists, clients, app_id=app_id)
        except Exception:
            logger.exception("Rollback failed for app_id=%s — resource may be orphaned", app_id)


async def rollback_update_resources(
    *,
    clients: WxOClient,
    created_tool_ids: list[str],
    created_app_id: str | None,
    original_tools: dict[str, dict],
) -> None:
    """Best-effort rollback for update operations.

    Restores mutated tools first, then deletes newly created tools, then deletes
    newly created config. Unlike ``rollback_created_resources`` this never
    deletes the deployment/agent itself.
    """
    logger.info(
        "Rolling back update resources: created_tool_ids=%s, created_app_id=%s, mutated_tools=%s",
        created_tool_ids,
        created_app_id,
        list(original_tools.keys()),
    )
    for tool_id, original_tool in reversed(list(original_tools.items())):
        try:
            await retry_rollback(asyncio.to_thread, clients.tool.update, tool_id, original_tool)
        except Exception:
            logger.exception(
                "Rollback failed: could not restore tool payload for tool_id=%s — resource may be orphaned",
                tool_id,
            )

    for tool_id in reversed(created_tool_ids):
        try:
            await retry_rollback(delete_tool_if_exists, clients, tool_id=tool_id)
        except Exception:
            logger.exception("Rollback failed for created tool_id=%s — resource may be orphaned", tool_id)

    if created_app_id:
        try:
            await retry_rollback(delete_config_if_exists, clients, app_id=created_app_id)
        except Exception:
            logger.exception("Rollback failed for created app_id=%s — resource may be orphaned", created_app_id)


async def delete_agent_if_exists(clients: WxOClient, *, agent_id: str) -> None:
    try:
        await asyncio.to_thread(clients.agent.delete, agent_id)
    except ClientAPIException as exc:
        if exc.response.status_code != status.HTTP_404_NOT_FOUND:
            raise


async def delete_tool_if_exists(clients: WxOClient, *, tool_id: str) -> None:
    try:
        await asyncio.to_thread(clients.tool.delete, tool_id)
    except ClientAPIException as exc:
        if exc.response.status_code != status.HTTP_404_NOT_FOUND:
            raise


async def delete_config_if_exists(clients: WxOClient, *, app_id: str) -> None:
    try:
        await asyncio.to_thread(clients.connections.delete, app_id)
    except ClientAPIException as exc:
        if exc.response.status_code != status.HTTP_404_NOT_FOUND:
            raise
