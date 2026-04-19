"""Rollback helpers for the Watsonx Orchestrate adapter.

Forward operations (create/update) currently run without retries so that
failures surface immediately to the caller. Only rollback/cleanup paths
use ``retry_rollback``.

TODO: Add retries for transient server-side errors (5xx, timeouts, etc.)
on forward create/update operations across the adapter (create.py,
update.py, shared.py, tools.py, service.py, and the frontend
use-post-deployment hook). For now we fail fast so users get prompt
feedback on failures.
"""

from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any, TypeVar

from fastapi import HTTPException, status
from ibm_watsonx_orchestrate_clients.tools.tool_client import ClientAPIException
from lfx.log.logger import logger

from langflow.services.adapters.deployment.watsonx_orchestrate.constants import (
    ROLLBACK_INITIAL_DELAY_SECONDS,
    ROLLBACK_MAX_RETRIES,
)

if TYPE_CHECKING:
    from langflow.services.adapters.deployment.watsonx_orchestrate.types import WxOClient

T = TypeVar("T")
Operation = Callable[..., Awaitable[T]]
ShouldRetry = Callable[[Exception], bool]


async def _retry_with_backoff(
    operation: Operation[T],
    max_attempts: int,
    *args: Any,
    should_retry: ShouldRetry | None = None,
    **kwargs: Any,
) -> T:
    """Retry an async operation with exponential backoff (used only for rollbacks)."""
    delay_seconds = ROLLBACK_INITIAL_DELAY_SECONDS
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


def _is_retryable_rollback_exception(exc: Exception) -> bool:
    """Determine whether a rollback operation should be retried."""
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
    return True


async def retry_rollback(operation: Operation[T], *args: Any, **kwargs: Any) -> T:
    """Retry a rollback/cleanup operation with exponential backoff."""
    return await _retry_with_backoff(
        operation,
        ROLLBACK_MAX_RETRIES,
        *args,
        should_retry=_is_retryable_rollback_exception,
        **kwargs,
    )


async def rollback_created_resources(
    *,
    clients: WxOClient,
    agent_id: str | None,
    tool_ids: list[str],
    app_ids: list[str] | None = None,
) -> None:
    app_ids_to_rollback = list(app_ids or [])
    logger.info(
        "Rolling back resources: agent_id=%s, tool_ids=%s, app_ids=%s",
        agent_id,
        tool_ids,
        app_ids_to_rollback,
    )
    if agent_id:
        try:
            await retry_rollback(delete_agent_if_exists, clients, agent_id=agent_id)
        except Exception:  # noqa: BLE001
            logger.exception("Rollback failed for agent_id=%s — resource may be orphaned", agent_id)
    if tool_ids:
        for tool_id in reversed(tool_ids):
            try:
                await retry_rollback(delete_tool_if_exists, clients, tool_id=tool_id)
            except Exception:  # noqa: BLE001
                logger.exception("Rollback failed for tool_id=%s — resource may be orphaned", tool_id)
    for created_app_id in reversed(app_ids_to_rollback):
        try:
            await retry_rollback(delete_config_if_exists, clients, app_id=created_app_id)
        except Exception:  # noqa: BLE001
            logger.exception("Rollback failed for app_id=%s — resource may be orphaned", created_app_id)


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
    logger.warning(
        "Rolling back update resources: created_tool_ids=%s, created_app_id=%s, mutated_tools=%s",
        created_tool_ids,
        created_app_id,
        list(original_tools.keys()),
    )
    for tool_id, original_tool in reversed(list(original_tools.items())):
        try:
            await retry_rollback(asyncio.to_thread, clients.tool.update, tool_id, original_tool)
        except Exception:  # noqa: BLE001
            logger.exception(
                "Rollback failed: could not restore tool payload for tool_id=%s — resource may be orphaned",
                tool_id,
            )

    for tool_id in reversed(created_tool_ids):
        try:
            await retry_rollback(delete_tool_if_exists, clients, tool_id=tool_id)
        except Exception:  # noqa: BLE001
            logger.exception("Rollback failed for created tool_id=%s — resource may be orphaned", tool_id)

    if created_app_id:
        try:
            await retry_rollback(delete_config_if_exists, clients, app_id=created_app_id)
        except Exception:  # noqa: BLE001
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
