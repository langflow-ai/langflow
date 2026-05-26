"""Retry/backoff and rollback logic for the Watsonx Orchestrate adapter."""

from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any, TypeVar

from fastapi import HTTPException, status
from ibm_watsonx_orchestrate_clients.tools.tool_client import ClientAPIException
from lfx.log.logger import logger
from lfx.services.adapters.deployment.exceptions import (
    InvalidContentError,
    InvalidDeploymentOperationError,
    InvalidDeploymentTypeError,
    ResourceConflictError,
)

from langflow.services.adapters.deployment.watsonx_orchestrate.constants import (
    CREATE_MAX_RETRIES,
    RETRY_INITIAL_DELAY_SECONDS,
    ROLLBACK_MAX_RETRIES,
    UPDATE_MAX_RETRIES,
    RollbackErrorLabel,
    RollbackSourceOperation,
    rollback_batch_failure_log_label,
    rollback_log_prefix,
)

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
            ResourceConflictError,
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


async def _run_rollback_batch(
    *,
    source_operation: RollbackSourceOperation,
    error_label: RollbackErrorLabel,
    resource_ids: list[str],
    coroutines: list[Awaitable[None]],
) -> None:
    if not coroutines:
        return
    log_label = rollback_batch_failure_log_label(source_operation=source_operation, error_label=error_label)
    results = await asyncio.gather(*coroutines, return_exceptions=True)
    total = len(resource_ids)
    for index, (resource_id, result) in enumerate(zip(resource_ids, results, strict=True), start=1):
        if not isinstance(result, BaseException):
            continue
        logger.error(
            "%s [%d/%d] for %s: %s",
            log_label,
            index,
            total,
            resource_id,
            result,
            exc_info=(type(result), result, result.__traceback__),
        )


async def rollback_tools(
    *,
    clients: WxOClient,
    source_operation: RollbackSourceOperation,
    created_tool_ids: list[str],
    original_tools: dict[str, dict],
) -> None:
    """Best-effort rollback for tool mutations during create/update.

    Restores mutated tools first, then deletes newly created tools. Unlike
    ``rollback_created_resources`` this never deletes the deployment/agent
    itself. Created connection cleanup is handled separately via
    ``rollback_created_app_ids``.
    """
    logger.warning(
        "%s rolling back tool resources: created_tool_ids=%s, mutated_tools=%s",
        rollback_log_prefix(source_operation),
        created_tool_ids,
        list(original_tools.keys()),
    )
    restore_items = list(original_tools.items())
    await _run_rollback_batch(
        source_operation=source_operation,
        error_label=RollbackErrorLabel.UPDATE_TOOL,
        resource_ids=[tool_id for tool_id, _ in restore_items],
        coroutines=[
            retry_rollback(asyncio.to_thread, clients.tool.update, tool_id, original_tool)
            for tool_id, original_tool in restore_items
        ],
    )

    await _run_rollback_batch(
        source_operation=source_operation,
        error_label=RollbackErrorLabel.CREATE_TOOL,
        resource_ids=created_tool_ids,
        coroutines=[retry_rollback(delete_tool_if_exists, clients, tool_id=tool_id) for tool_id in created_tool_ids],
    )


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
