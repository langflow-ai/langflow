"""Authorization helpers for guarded API routes."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, TypeVar
from uuid import UUID

from fastapi import HTTPException, status
from lfx.log.logger import logger

from langflow.services.authorization.actions import (
    DeploymentAction,
    FileAction,
    FlowAction,
    KnowledgeBaseAction,
    ProjectAction,
    ShareAction,
    VariableAction,
)
from langflow.services.deps import get_authorization_service, get_settings_service

if TYPE_CHECKING:
    from collections.abc import Callable

    from langflow.services.auth.exceptions import InsufficientPermissionsError
    from langflow.services.database.models.user.model import User, UserRead


T = TypeVar("T")

# Shared audit result vocabulary.
_AUDIT_ALLOW = "allow"
_AUDIT_DENY = "deny"
_AUDIT_OWNER_OVERRIDE = "owner_override"

# Resource-owner keys included in audit details.
_OWNER_CONTEXT_KEYS = (
    "flow_user_id",
    "deployment_user_id",
    "project_user_id",
    "knowledge_base_user_id",
    "variable_user_id",
    "file_user_id",
    "share_user_id",
)

# Action enums coerced to string values.
_ACTION_ENUMS = (
    FlowAction,
    DeploymentAction,
    ProjectAction,
    KnowledgeBaseAction,
    VariableAction,
    FileAction,
    ShareAction,
)


def _auth_context(user: User | UserRead) -> dict[str, Any]:
    """Build the base context dict passed to authorization enforce calls."""
    return {"is_superuser": getattr(user, "is_superuser", False)}


def _coerce_action(
    act: DeploymentAction
    | FlowAction
    | ProjectAction
    | KnowledgeBaseAction
    | VariableAction
    | FileAction
    | ShareAction
    | str,
) -> str:
    """Return the string value of an action enum or pass through a raw string."""
    if isinstance(act, _ACTION_ENUMS):
        return act.value
    return act


def _split_obj(obj: str) -> tuple[str | None, UUID | None]:
    """Parse an authz obj key like 'flow:abc' into (resource_type, resource_id).

    Wildcards (``flow:*``) and unparseable ids return None for ``resource_id``
    so audit rows are still written with the right ``resource_type``.
    """
    if ":" not in obj:
        return None, None
    resource_type, _, suffix = obj.partition(":")
    if not suffix or suffix == "*":
        return resource_type, None
    try:
        return resource_type, UUID(suffix)
    except (ValueError, TypeError):
        return resource_type, None


# ----------------------------------------------------------------------------- #
# Batched audit pipeline.
#
# An earlier revision did ``asyncio.create_task(_write())`` per authorization
# decision, with each write opening its own ``session_scope()``. That works on
# light traffic, but on a real workload (every authenticated request emits at
# least one audit row) it turns into a connection-pool storm: per request you
# pay for the request session + a fresh audit session, and the unbounded
# ``_pending_audit_tasks`` set grows until shutdown drain.
#
# This version routes every decision through a bounded queue drained by a
# single long-lived writer task. The writer batches up to ``_AUDIT_BATCH_MAX``
# rows per ``session_scope()`` and commits them in one INSERT. ``audit_decision``
# stays a non-blocking ``put_nowait``: if the queue is saturated the row is
# dropped (with a periodic warning) so the request path is never gated on the
# audit DB.
# ----------------------------------------------------------------------------- #

_AUDIT_QUEUE_MAX = 10_000
_AUDIT_BATCH_MAX = 100


class _AuditEntry:
    """One pending audit row.

    A plain class (not a dataclass) so it can be instantiated cheaply from the
    request path without dataclass overhead. The fields mirror
    ``AuthzAuditLog`` columns plus the raw ``obj`` string — the writer splits
    ``obj`` into ``(resource_type, resource_id)`` once per batch.
    """

    __slots__ = ("action", "details", "obj", "result", "user_id")

    def __init__(
        self,
        *,
        user_id: UUID | None,
        action: str,
        obj: str,
        result: str,
        details: dict[str, Any] | None,
    ) -> None:
        self.user_id = user_id
        self.action = action
        self.obj = obj
        self.result = result
        self.details = details


# Module-level state. Bound to whichever event loop is running when the first
# ``audit_decision`` call happens. ``_audit_queue_loop`` lets us detect a fresh
# loop (e.g. between pytest test cases) and restart the writer in the new loop
# instead of writing to a queue tied to a dead loop.
_audit_queue: asyncio.Queue[_AuditEntry] | None = None
_audit_queue_loop: asyncio.AbstractEventLoop | None = None
_audit_writer_task: asyncio.Task[None] | None = None
_audit_dropped_count: int = 0
# Kept as a vestigial public name for backward compatibility with downstream
# callers (and the existing drain helper). The new pipeline tracks the single
# writer task here so ``drain_pending_audit_writes`` can await it.
_pending_audit_tasks: set[asyncio.Task[None]] = set()


def _ensure_audit_writer_started() -> asyncio.Queue[_AuditEntry] | None:
    """Lazily start the audit writer task in the current event loop.

    Returns the queue, or ``None`` if no event loop is running (audit is
    skipped entirely in that case — there's no place to schedule the writer).
    """
    global _audit_queue, _audit_queue_loop, _audit_writer_task  # noqa: PLW0603

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return None

    # A fresh event loop replaces the previous queue+writer. Without this,
    # a subsequent ``audit_decision`` call (e.g. in a new pytest test) would
    # ``put_nowait`` into a queue that no live task is consuming.
    if _audit_queue_loop is not loop:
        _audit_queue = asyncio.Queue(maxsize=_AUDIT_QUEUE_MAX)
        _audit_queue_loop = loop
        _audit_writer_task = None
        _pending_audit_tasks.clear()

    if _audit_writer_task is None or _audit_writer_task.done():
        _audit_writer_task = loop.create_task(_audit_writer_loop())
        _pending_audit_tasks.add(_audit_writer_task)
        _audit_writer_task.add_done_callback(_pending_audit_tasks.discard)

    return _audit_queue


async def _audit_writer_loop() -> None:
    """Drain the audit queue and write batches to the DB.

    Loops until cancelled. Each iteration blocks on the first row, then greedily
    pulls everything else already enqueued up to ``_AUDIT_BATCH_MAX`` and
    commits them as a single batch insert. DB exceptions are logged and
    swallowed — an audit-table outage must never crash the request path that
    triggered the row.
    """
    while True:
        queue = _audit_queue
        if queue is None:
            return
        try:
            first = await queue.get()
        except asyncio.CancelledError:
            return

        batch: list[_AuditEntry] = [first]
        try:
            while len(batch) < _AUDIT_BATCH_MAX:
                batch.append(queue.get_nowait())
        except asyncio.QueueEmpty:
            pass

        try:
            await _flush_audit_batch(batch)
        except Exception:  # noqa: BLE001 — never let the writer die quietly
            logger.exception("Authz audit writer batch flush failed for %d row(s)", len(batch))
        finally:
            for _ in batch:
                queue.task_done()


async def _flush_audit_batch(batch: list[_AuditEntry]) -> None:
    """Insert a batch of ``_AuditEntry`` rows in a single session."""
    if not batch:
        return
    # Imported lazily so the request path doesn't pull DB modules until the
    # writer first runs (matches the lazy import in the old per-row path).
    from langflow.services.database.models.auth import AuthzAuditLog
    from langflow.services.deps import session_scope

    async with session_scope() as session:
        for entry in batch:
            resource_type, resource_id = _split_obj(entry.obj)
            session.add(
                AuthzAuditLog(
                    user_id=entry.user_id,
                    action=entry.action,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    result=entry.result,
                    details=entry.details,
                )
            )


async def drain_pending_audit_writes(timeout: float = 5.0) -> None:
    """Flush the audit queue and stop the writer (bounded by ``timeout``).

    Safe to call multiple times; safe to call when no audit traffic has run.
    Splits the timeout between draining the queue and awaiting writer
    cancellation so neither side can hang shutdown indefinitely.
    """
    global _audit_writer_task  # noqa: PLW0603

    queue = _audit_queue
    writer = _audit_writer_task
    if queue is None or writer is None:
        return

    drain_budget = max(0.1, timeout * 0.8)
    cancel_budget = max(0.1, timeout - drain_budget)

    try:
        await asyncio.wait_for(queue.join(), timeout=drain_budget)
    except asyncio.TimeoutError:
        logger.warning(
            "drain_pending_audit_writes timed out after %.2fs with %d row(s) pending",
            drain_budget,
            queue.qsize(),
        )

    if not writer.done():
        writer.cancel()
        from contextlib import suppress

        with suppress(asyncio.CancelledError):
            await asyncio.wait_for(writer, timeout=cancel_budget)

    _pending_audit_tasks.discard(writer)
    _audit_writer_task = None


async def audit_decision(
    *,
    user_id: UUID | None,
    action: str,
    obj: str,
    result: str,
    details: dict[str, Any] | None = None,
) -> None:
    """Enqueue an AuthzAuditLog row for batched background insertion.

    Non-blocking from the caller's perspective. When the queue is saturated the
    row is dropped and a sample-rate warning is emitted so a stuck pipeline is
    operator-visible. Audit is fully bypassed when
    ``AUTHZ_AUDIT_ENABLED=False`` (the default).
    """
    global _audit_dropped_count  # noqa: PLW0603

    settings = get_settings_service()
    auth_settings = settings.auth_settings
    # Audit is independent of enforcement. ``AuthSettings.AUTHZ_AUDIT_ENABLED``
    # defaults to ``False`` (see lfx/services/settings/auth.py) because the
    # background writer still consumes a DB connection; operators opt in.
    if not getattr(auth_settings, "AUTHZ_AUDIT_ENABLED", False):
        return

    queue = _ensure_audit_writer_started()
    if queue is None:
        # No running event loop — nothing to schedule against. The caller is
        # likely outside an async context (e.g. a sync test); silently skip.
        return

    entry = _AuditEntry(
        user_id=user_id,
        action=action,
        obj=obj,
        result=result,
        details=details,
    )
    try:
        queue.put_nowait(entry)
    except asyncio.QueueFull:
        _audit_dropped_count += 1
        # Sample-log so a saturated pipeline surfaces in ops dashboards without
        # spamming the log on every drop. First drop + every 1000th drop.
        if _audit_dropped_count == 1 or _audit_dropped_count % 1000 == 0:
            logger.warning(
                "AuthzAuditLog queue full (%d/%d); dropped %d row(s) total. DB writer is likely behind or stalled.",
                queue.qsize(),
                _AUDIT_QUEUE_MAX,
                _audit_dropped_count,
            )


async def ensure_permission(
    user: User | UserRead,
    *,
    domain: str,
    obj: str,
    act: str,
    context: dict[str, Any] | None = None,
) -> None:
    """Raise HTTP 403 when the user may not perform the action (audited)."""
    settings = get_settings_service()
    if not settings.auth_settings.AUTHZ_ENABLED:
        return

    authz = get_authorization_service()
    # Caller context first; user auth fields cannot be overwritten.
    merged_context = {**(context or {}), **_auth_context(user)}
    # Fail closed when enforce() raises (deny + audit, not HTTP 500).
    audit_action = f"{obj.split(':', 1)[0]}:{act}" if ":" in obj else act
    audit_details = {"domain": domain}
    for owner_key in _OWNER_CONTEXT_KEYS:
        if owner_key in merged_context and merged_context[owner_key] is not None:
            audit_details[owner_key] = str(merged_context[owner_key])
    try:
        allowed = await authz.enforce(
            user_id=user.id,
            domain=domain,
            obj=obj,
            act=act,
            context=merged_context,
        )
    except Exception as exc:
        logger.exception("Authorization plugin raised during enforce; failing closed")
        await audit_decision(
            user_id=user.id,
            action=audit_action,
            obj=obj,
            result=_AUDIT_DENY,
            details={**audit_details, "error": str(exc)},
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Insufficient permissions to {act} on {obj}",
        ) from exc

    await audit_decision(
        user_id=user.id,
        action=audit_action,
        obj=obj,
        result=_AUDIT_ALLOW if allowed else _AUDIT_DENY,
        details=audit_details,
    )

    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Insufficient permissions to {act} on {obj}",
        )


def _resolve_casbin_domain(workspace_id: UUID | None, scope_id: UUID | None) -> str:
    """Resolve policy domain: project scope, then workspace, else ``*``."""
    if scope_id is not None:
        return f"project:{scope_id}"
    if workspace_id is not None:
        return f"workspace:{workspace_id}"
    return "*"


# Backward-compatible alias.
_resolve_flow_domain = _resolve_casbin_domain


async def _ensure_resource_permission(
    user: User | UserRead,
    *,
    resource_type: str,
    resource_id: UUID | str | None,
    owner_id: UUID | None,
    act_str: str,
    resolved_domain: str,
    extra_context: dict[str, Any],
) -> None:
    """Build object key, apply owner override, else delegate to ensure_permission."""
    obj = f"{resource_type}:{resource_id}" if resource_id else f"{resource_type}:*"

    if owner_id is not None and getattr(user, "id", None) == owner_id:
        await audit_decision(
            user_id=user.id,
            action=f"{resource_type}:{act_str}",
            obj=obj,
            result=_AUDIT_OWNER_OVERRIDE,
            details={"domain": resolved_domain},
        )
        return

    await ensure_permission(
        user,
        domain=resolved_domain,
        obj=obj,
        act=act_str,
        context=extra_context,
    )


async def ensure_flow_permission(
    user: User | UserRead,
    act: FlowAction | str,
    *,
    flow_id: UUID | None = None,
    flow_user_id: UUID | None = None,
    workspace_id: UUID | None = None,
    folder_id: UUID | None = None,
    domain: str | None = None,
) -> None:
    """Check flow permission (owner override, then plugin enforce)."""
    await _ensure_resource_permission(
        user,
        resource_type="flow",
        resource_id=flow_id,
        owner_id=flow_user_id,
        act_str=_coerce_action(act),
        resolved_domain=domain if domain is not None else _resolve_casbin_domain(workspace_id, folder_id),
        extra_context={
            "flow_user_id": flow_user_id,
            "workspace_id": workspace_id,
            "folder_id": folder_id,
        },
    )


async def ensure_deployment_permission(
    user: User | UserRead,
    act: DeploymentAction | str,
    *,
    deployment_id: UUID | None = None,
    deployment_user_id: UUID | None = None,
    workspace_id: UUID | None = None,
    project_id: UUID | None = None,
    domain: str | None = None,
) -> None:
    """Check deployment permission (owner override, then plugin enforce)."""
    await _ensure_resource_permission(
        user,
        resource_type="deployment",
        resource_id=deployment_id,
        owner_id=deployment_user_id,
        act_str=_coerce_action(act),
        resolved_domain=domain if domain is not None else _resolve_casbin_domain(workspace_id, project_id),
        extra_context={
            "deployment_user_id": deployment_user_id,
            "workspace_id": workspace_id,
            "project_id": project_id,
        },
    )


async def ensure_project_permission(
    user: User | UserRead,
    act: ProjectAction | str,
    *,
    project_id: UUID | None = None,
    project_user_id: UUID | None = None,
    workspace_id: UUID | None = None,
    domain: str | None = None,
) -> None:
    """Check project (folder) permission (owner override, then plugin enforce)."""
    await _ensure_resource_permission(
        user,
        resource_type="project",
        resource_id=project_id,
        owner_id=project_user_id,
        act_str=_coerce_action(act),
        resolved_domain=domain if domain is not None else _resolve_casbin_domain(workspace_id, None),
        extra_context={
            "project_user_id": project_user_id,
            "workspace_id": workspace_id,
        },
    )


async def ensure_knowledge_base_permission(
    user: User | UserRead,
    act: KnowledgeBaseAction | str,
    *,
    kb_id: UUID | None = None,
    kb_user_id: UUID | None = None,
    kb_name: str | None = None,
    workspace_id: UUID | None = None,
    project_id: UUID | None = None,
    domain: str | None = None,
) -> None:
    """Check knowledge-base permission (owner override, then plugin enforce)."""
    await _ensure_resource_permission(
        user,
        resource_type="knowledge_base",
        resource_id=kb_id,
        owner_id=kb_user_id,
        act_str=_coerce_action(act),
        resolved_domain=domain if domain is not None else _resolve_casbin_domain(workspace_id, project_id),
        extra_context={
            "knowledge_base_user_id": kb_user_id,
            "kb_id": kb_id,
            "kb_name": kb_name,
            "workspace_id": workspace_id,
            "project_id": project_id,
        },
    )


async def ensure_variable_permission(
    user: User | UserRead,
    act: VariableAction | str,
    *,
    variable_id: UUID | None = None,
    variable_user_id: UUID | None = None,
    workspace_id: UUID | None = None,
    domain: str | None = None,
) -> None:
    """Check variable permission (owner override, then plugin enforce)."""
    await _ensure_resource_permission(
        user,
        resource_type="variable",
        resource_id=variable_id,
        owner_id=variable_user_id,
        act_str=_coerce_action(act),
        resolved_domain=domain if domain is not None else _resolve_casbin_domain(workspace_id, None),
        extra_context={
            "variable_user_id": variable_user_id,
            "workspace_id": workspace_id,
        },
    )


async def ensure_file_permission(
    user: User | UserRead,
    act: FileAction | str,
    *,
    file_id: UUID | None = None,
    file_user_id: UUID | None = None,
    workspace_id: UUID | None = None,
    domain: str | None = None,
) -> None:
    """Check file permission (owner override, then plugin enforce)."""
    await _ensure_resource_permission(
        user,
        resource_type="file",
        resource_id=file_id,
        owner_id=file_user_id,
        act_str=_coerce_action(act),
        resolved_domain=domain if domain is not None else _resolve_casbin_domain(workspace_id, None),
        extra_context={
            "file_user_id": file_user_id,
            "workspace_id": workspace_id,
        },
    )


async def ensure_share_permission(
    user: User | UserRead,
    act: ShareAction | str,
    *,
    share_id: UUID | None = None,
    share_user_id: UUID | None = None,
    domain: str | None = None,
) -> None:
    """Check share-row permission (owner override, then plugin enforce)."""
    await _ensure_resource_permission(
        user,
        resource_type="share",
        resource_id=share_id,
        owner_id=share_user_id,
        act_str=_coerce_action(act),
        resolved_domain=domain if domain is not None else "*",
        extra_context={
            "share_user_id": share_user_id,
        },
    )


async def filter_visible_resources(
    user: User | UserRead,
    *,
    resource_type: str,
    candidates: list[T],
    key: Callable[[T], UUID] | None = None,
    domain: str = "*",
    domain_extractor: Callable[[T], str] | None = None,
    owner_extractor: Callable[[T], UUID | None] | None = None,
    act: FlowAction | str = FlowAction.READ,
) -> list[T]:
    """Return candidates the user may read (no-op when AUTHZ_ENABLED is false)."""
    settings = get_settings_service()
    if not settings.auth_settings.AUTHZ_ENABLED or not candidates:
        return candidates

    extractor = key if key is not None else _default_resource_id_getter
    authz = get_authorization_service()
    act_str = _coerce_action(act)
    user_id = getattr(user, "id", None)

    # Owned rows skip batch_enforce (matches direct-read owner override).
    owned_indices: set[int] = set()
    enforce_indices: list[int] = []
    enforce_items: list[T] = []
    for index, item in enumerate(candidates):
        if owner_extractor is not None and user_id is not None and owner_extractor(item) == user_id:
            owned_indices.add(index)
        else:
            enforce_indices.append(index)
            enforce_items.append(item)

    decisions: list[bool] = [False] * len(candidates)
    for index in owned_indices:
        decisions[index] = True

    if enforce_items:
        if domain_extractor is None:
            # Single-domain batch_enforce.
            requests = [(f"{resource_type}:{extractor(item)}", act_str) for item in enforce_items]
            results = await authz.batch_enforce(
                user_id=user_id,
                domain=domain,
                requests=requests,
                context=_auth_context(user),
            )
            for original_index, allowed in zip(enforce_indices, results, strict=True):
                decisions[original_index] = allowed
        else:
            # One batch_enforce per resolved domain.
            buckets: dict[str, list[tuple[int, T]]] = {}
            for original_index, item in zip(enforce_indices, enforce_items, strict=True):
                buckets.setdefault(domain_extractor(item), []).append((original_index, item))

            auth_context = _auth_context(user)
            for resolved_domain, bucket in buckets.items():
                bucket_requests = [(f"{resource_type}:{extractor(item)}", act_str) for _, item in bucket]
                bucket_results = await authz.batch_enforce(
                    user_id=user_id,
                    domain=resolved_domain,
                    requests=bucket_requests,
                    context=auth_context,
                )
                for (original_index, _), allowed in zip(bucket, bucket_results, strict=True):
                    decisions[original_index] = allowed

    return [item for item, allowed in zip(candidates, decisions, strict=True) if allowed]


def _default_resource_id_getter(item: Any) -> UUID:
    """Default key extractor used by filter_visible_resources."""
    return item.id


def permission_denied_to_http(exc: InsufficientPermissionsError) -> HTTPException:
    """Translate an InsufficientPermissionsError into a 403 HTTPException."""
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=exc.message)
