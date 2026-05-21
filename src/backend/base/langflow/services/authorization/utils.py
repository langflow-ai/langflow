"""Authorization helpers for API routes.

Phase 1 contract (this PR)
---------------------------

Route guards (``ensure_flow_permission``, ``ensure_deployment_permission``,
``ensure_project_permission``) sit on top of fetch helpers that still scope
queries by ``current_user.id`` — see ``_read_flow`` in ``flows_helpers.py``,
``get_flow_for_api_key_user`` in ``endpoints.py``, ``get_deployment`` in
``deployment.crud``, and the owner-scoped folder reads in ``projects.py``.

That means an enterprise plugin which would otherwise grant a non-owner
shared / read / write / execute access to a flow, folder, or deployment
**still returns 404 at the fetch layer before** ``ensure_*_permission`` can
authorize the request. Cross-user enforcement therefore lands in Phase 3
alongside ``authz_share`` CRUD APIs and the share-aware fetch helpers that
load by id first and convert plugin denies to 404 to preserve UUID-privacy.

In Phase 1 the OSS pass-through allows all and the owner-scoped fetch is the
only effective gate; in Phase 2 (this PR) the guards exist, are wired, and
emit audit rows, but cross-user access is not yet reachable. See PR #13153
description and the Phase 3 prerequisite captured in the planning notes.
"""

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

# Audit result strings — kept here so callers and tests share the vocabulary.
_AUDIT_ALLOW = "allow"
_AUDIT_DENY = "deny"
_AUDIT_OWNER_OVERRIDE = "owner_override"

# Context keys that name the resource owner — used by audit-detail extraction.
_OWNER_CONTEXT_KEYS = (
    "flow_user_id",
    "deployment_user_id",
    "project_user_id",
    "knowledge_base_user_id",
    "variable_user_id",
    "file_user_id",
    "share_user_id",
)

# Action enum types we coerce to their string value.
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


# In-flight audit tasks. Keeping a strong reference prevents the event loop
# from garbage-collecting a pending task before it writes — and gives
# ``drain_pending_audit_writes`` (called on shutdown) something to await.
# A bare ``asyncio.create_task`` without this reference can be dropped by
# the GC mid-write and silently lose the audit row.
_pending_audit_tasks: set[asyncio.Task[None]] = set()


async def drain_pending_audit_writes(timeout: float = 5.0) -> None:
    """Wait for any in-flight audit-write tasks to complete.

    Called on application shutdown so audit rows scheduled mid-request still
    land in the DB before the event loop closes. Returns silently after
    ``timeout`` even if some tasks are still pending — audit must never block
    shutdown indefinitely.
    """
    pending = {task for task in _pending_audit_tasks if not task.done()}
    if not pending:
        return
    done, still_pending = await asyncio.wait(pending, timeout=timeout)
    if still_pending:
        logger.warning("drain_pending_audit_writes timed out with %d pending tasks", len(still_pending))
    # Surface task exceptions in logs but never raise — audit must not block shutdown.
    for task in done:
        exc = task.exception() if not task.cancelled() else None
        if exc is not None:
            logger.warning("Audit task raised during drain: %s", exc)


async def audit_decision(
    *,
    user_id: UUID | None,
    action: str,
    obj: str,
    result: str,
    details: dict[str, Any] | None = None,
) -> None:
    """Write an AuthzAuditLog row, fire-and-forget.

    Schedules an asyncio task and returns immediately. Failures inside the task
    are logged but never propagate to the caller so audit writes can never
    block a real API response. The task reference is held in
    ``_pending_audit_tasks`` until completion so the event loop cannot GC it
    mid-write; ``drain_pending_audit_writes`` awaits this set on shutdown so
    pending rows are not lost.
    """
    settings = get_settings_service()
    auth_settings = settings.auth_settings
    # Audit is independent of enforcement: an operator can keep audit on
    # while AUTHZ_ENABLED=false to observe traffic before flipping the
    # flag. Previously this short-circuited on AUTHZ_ENABLED too, which
    # meant share CRUD writes (which the OSS floor allows in default mode)
    # produced no audit trail at all.
    if not getattr(auth_settings, "AUTHZ_AUDIT_ENABLED", True):
        return

    resource_type, resource_id = _split_obj(obj)

    async def _write() -> None:
        try:
            from langflow.services.database.models.auth import AuthzAuditLog
            from langflow.services.deps import session_scope

            async with session_scope() as session:
                session.add(
                    AuthzAuditLog(
                        user_id=user_id,
                        action=action,
                        resource_type=resource_type,
                        resource_id=resource_id,
                        result=result,
                        details=details,
                    )
                )
        except Exception:  # noqa: BLE001 — audit must never raise into the request path
            logger.exception("Failed to write AuthzAuditLog row")

    task = asyncio.create_task(_write())
    _pending_audit_tasks.add(task)
    task.add_done_callback(_pending_audit_tasks.discard)


async def ensure_permission(
    user: User | UserRead,
    *,
    domain: str,
    obj: str,
    act: str,
    context: dict[str, Any] | None = None,
) -> None:
    """Raise HTTP 403 if the user is not allowed to perform the action.

    Writes an audit row on both allow and deny paths.
    """
    settings = get_settings_service()
    if not settings.auth_settings.AUTHZ_ENABLED:
        return

    authz = get_authorization_service()
    # User-derived auth fields (e.g. is_superuser) must remain authoritative; caller
    # context is merged first so it cannot overwrite them.
    merged_context = {**(context or {}), **_auth_context(user)}
    # Fail-closed contract: if the plugin's ``enforce`` raises (Casbin DB
    # down, policy parse error, etc.), we treat the request as denied and
    # log an explicit error-audit row. Returning False from ``enforce`` is
    # the plugin's documented way to deny; raising should not silently
    # become an HTTP 500 that bypasses both the deny path and the audit log.
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
    """Pick the most specific Casbin domain for a resource check.

    ``scope_id`` is the folder/project id for flows and deployments, or ``None``
    when the resource itself is the project (the project helper passes ``None``
    so the domain falls back to workspace).

    Precedence (inner → outer):
      1. ``project:{scope_id}`` when set,
      2. ``workspace:{workspace_id}`` when only a workspace is set,
      3. ``"*"`` when neither is set.

    Enterprise Casbin policies link the two via ``g2`` (e.g.
    ``g2, project:xyz, workspace:abc``) so that when the enforcer checks
    against the **project** domain, both project-scoped and workspace-scoped
    role grants match (workspace grants flow down to projects via g2).
    Passing the workspace domain when a project is known would make
    project-scoped grants invisible because g2 is directional — children
    inherit from parents, not the other way round. ``workspace_id`` is also
    forwarded in the enforce context for plugins that prefer ABAC-style
    matchers.
    """
    if scope_id is not None:
        return f"project:{scope_id}"
    if workspace_id is not None:
        return f"workspace:{workspace_id}"
    return "*"


# Backward-compatible alias for callers/tests that imported the old name.
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
    """Shared core for the per-resource ``ensure_*_permission`` helpers.

    Builds the canonical ``{resource_type}:{id}|*`` object key, short-circuits
    on owner override (audited as ``owner_override``), and otherwise delegates
    to ``ensure_permission``. ``extra_context`` is forwarded verbatim — callers
    own the key names so each resource type's audit row stays self-describing.

    ``resource_id`` accepts either a UUID (flows, deployments, projects, files,
    variables) or a string slug (knowledge bases are name-keyed).
    """
    obj = f"{resource_type}:{resource_id}" if resource_id else f"{resource_type}:*"

    # Owner override: a resource owner can always operate on their own resource.
    if owner_id is not None and getattr(user, "id", None) == owner_id:
        # ``audit_decision`` is gated on ``AUTHZ_AUDIT_ENABLED`` internally;
        # we no longer suppress the call on ``AUTHZ_ENABLED=false`` so
        # operators observing pre-enforcement traffic see owner overrides too.
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
    """Check flow-scoped permission with workspace/project domain + owner override.

    The flow owner is always allowed (audited as ``owner_override``). Otherwise
    delegates through :func:`ensure_permission` with the canonical Casbin tuple
    ``(user, domain, obj=flow:{id}|flow:*, act=<FlowAction>)`` where the domain
    follows :func:`_resolve_casbin_domain`. Both ``workspace_id`` and
    ``folder_id`` are forwarded in the context dict so the enterprise plugin
    can use whichever fits its policy model.
    """
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
    """Check deployment-scoped permission with workspace/project domain + owner override.

    Deployments use ``project_id`` (folder row) for the Casbin project domain, same as
    flows use ``folder_id``. The deployment owner may always access their deployment.
    """
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
    """Check project-scoped permission with workspace domain + owner override.

    Projects are the OSS persistent name for folders. The Casbin object is
    ``project:{project_id}`` (or ``project:*`` for list/create). The domain
    resolves to ``workspace:{workspace_id}`` when set, otherwise ``*`` — the
    project itself is the resource, not the scope.
    """
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
    """Check knowledge-base-scoped permission with owner override.

    Knowledge bases are tracked by ``KnowledgeBaseRecord`` (UUID primary key,
    ``(user_id, name)`` unique). The Casbin object slug is
    ``knowledge_base:{kb_id}`` so it matches the ``authz_share.resource_id``
    column (UUID) without an extra translation. ``kb_name`` is forwarded in
    the audit context for human-readable debugging.

    For create-style checks (no KB row yet), pass ``kb_id=None``; the slug
    becomes ``knowledge_base:*``.
    """
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
    """Check variable-scoped permission with owner override."""
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
    """Check file-scoped permission (v2 user files) with owner override."""
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
    """Check authz_share-scoped permission with owner override.

    A share row is "owned" by the user who created it (``created_by``). The
    resource owner is therefore always allowed to administer their own
    shares; enterprise plugins decide everything else.
    """
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
    """Return the subset of `candidates` that the user is allowed to read.

    No-op when ``AUTHZ_ENABLED=false`` — returns the input list unchanged.
    Plumbing for list endpoints; the OSS pass-through always returns the full
    list, so calling this is safe to add ahead of enterprise plugin rollout.

    ``domain_extractor`` lets callers compute a per-candidate domain string
    (typically via :func:`_resolve_casbin_domain`). Without it, every request
    in the batch evaluates against the same ``domain``, which makes
    project-scoped policy grants invisible when candidates live in different
    workspaces or projects. With it, candidates are grouped by their resolved
    domain and the enforcer is called once per group, so each request is
    evaluated against the right Casbin tuple.

    ``owner_extractor`` returns the owner UUID for each candidate. Items
    owned by the calling user are force-included **without** consulting the
    enforcer, mirroring the owner-override short-circuit in
    :func:`_ensure_resource_permission`. Without this, an enterprise plugin
    that lacks an explicit owner policy would hide a caller's own rows from
    a list view even though the same caller can read each row directly via
    the single-resource guard — list and direct read would disagree, which
    is the symptom this parameter is here to prevent.

    The OSS pass-through ignores ``domain`` entirely and returns
    ``[True] * len(requests)`` for either path.
    """
    settings = get_settings_service()
    if not settings.auth_settings.AUTHZ_ENABLED or not candidates:
        return candidates

    extractor = key if key is not None else _default_resource_id_getter
    authz = get_authorization_service()
    act_str = _coerce_action(act)
    user_id = getattr(user, "id", None)

    # Owner-override partition. Items the caller owns skip the enforcer
    # entirely (matches the direct-read owner short-circuit).
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
        # Use the already-extracted ``user_id`` instead of re-reading
        # ``user.id`` here. The earlier owner-override partition used
        # ``getattr(user, "id", None)``, so consistency means a non-User
        # dependency (e.g. a thin context proxy) lands an explicit None
        # rather than an AttributeError at this call site.
        if domain_extractor is None:
            # Single-domain fast path. Preserves the original single-call shape.
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
            # Group candidates by their resolved domain so each batch_enforce
            # call evaluates against a single Casbin tuple. Preserves input
            # order on output by carrying the original index through the
            # per-domain bucket.
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
