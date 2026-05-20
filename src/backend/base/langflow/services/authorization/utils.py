"""Authorization helpers for API routes."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, TypeVar
from uuid import UUID

from fastapi import HTTPException, status
from lfx.log.logger import logger

from langflow.services.authorization.actions import DeploymentAction, FlowAction
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


def _auth_context(user: User | UserRead) -> dict[str, Any]:
    """Build the base context dict passed to authorization enforce calls."""
    return {"is_superuser": getattr(user, "is_superuser", False)}


def _coerce_action(act: DeploymentAction | FlowAction | str) -> str:
    """Return the string value of an action enum or pass through a raw string."""
    if isinstance(act, (FlowAction, DeploymentAction)):
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
    block a real API response.
    """
    settings = get_settings_service()
    auth_settings = settings.auth_settings
    if not auth_settings.AUTHZ_ENABLED or not getattr(auth_settings, "AUTHZ_AUDIT_ENABLED", True):
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

    # Bare create_task is the langflow convention (see main.py:135, main.py:173).
    asyncio.create_task(_write())  # noqa: RUF006 — fire-and-forget audit task


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
    allowed = await authz.enforce(
        user_id=user.id,
        domain=domain,
        obj=obj,
        act=act,
        context=merged_context,
    )

    audit_details = {"domain": domain}
    for owner_key in ("flow_user_id", "deployment_user_id"):
        if owner_key in merged_context and merged_context[owner_key] is not None:
            audit_details[owner_key] = str(merged_context[owner_key])
    await audit_decision(
        user_id=user.id,
        action=f"{obj.split(':', 1)[0]}:{act}" if ":" in obj else act,
        obj=obj,
        result=_AUDIT_ALLOW if allowed else _AUDIT_DENY,
        details=audit_details,
    )

    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Insufficient permissions to {act} on {obj}",
        )


def _resolve_flow_domain(workspace_id: UUID | None, folder_id: UUID | None) -> str:
    """Pick the most specific Casbin domain for a flow check.

    Precedence (inner → outer):
      1. ``project:{folder_id}`` when a folder is set,
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
    if folder_id is not None:
        return f"project:{folder_id}"
    if workspace_id is not None:
        return f"workspace:{workspace_id}"
    return "*"


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
    delegates to :func:`ensure_permission` with the canonical Casbin tuple
    ``(user, domain, obj=flow:{id}|flow:*, act=<FlowAction>)`` where the domain
    follows the precedence in :func:`_resolve_flow_domain`. Both
    ``workspace_id`` and ``folder_id`` are forwarded in the context dict so the
    enterprise plugin can use whichever fits its policy model.
    """
    obj = f"flow:{flow_id}" if flow_id else "flow:*"
    act_str = _coerce_action(act)
    resolved_domain = domain if domain is not None else _resolve_flow_domain(workspace_id, folder_id)

    # Owner override: a flow owner can always operate on their own flow.
    if flow_user_id is not None and getattr(user, "id", None) == flow_user_id:
        settings = get_settings_service()
        if settings.auth_settings.AUTHZ_ENABLED:
            await audit_decision(
                user_id=user.id,
                action=f"flow:{act_str}",
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
        context={
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
    obj = f"deployment:{deployment_id}" if deployment_id else "deployment:*"
    act_str = _coerce_action(act)
    resolved_domain = domain if domain is not None else _resolve_flow_domain(workspace_id, project_id)

    if deployment_user_id is not None and getattr(user, "id", None) == deployment_user_id:
        settings = get_settings_service()
        if settings.auth_settings.AUTHZ_ENABLED:
            await audit_decision(
                user_id=user.id,
                action=f"deployment:{act_str}",
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
        context={
            "deployment_user_id": deployment_user_id,
            "workspace_id": workspace_id,
            "project_id": project_id,
        },
    )


async def filter_visible_resources(
    user: User | UserRead,
    *,
    resource_type: str,
    candidates: list[T],
    key: Callable[[T], UUID] | None = None,
    domain: str = "*",
    act: FlowAction | str = FlowAction.READ,
) -> list[T]:
    """Return the subset of `candidates` that the user is allowed to read.

    No-op when ``AUTHZ_ENABLED=false`` — returns the input list unchanged.
    Plumbing for list endpoints; the OSS pass-through always returns the full
    list, so calling this is safe to add ahead of enterprise plugin rollout.
    """
    settings = get_settings_service()
    if not settings.auth_settings.AUTHZ_ENABLED or not candidates:
        return candidates

    extractor = key if key is not None else _default_resource_id_getter
    authz = get_authorization_service()
    act_str = _coerce_action(act)
    requests = [(f"{resource_type}:{extractor(item)}", act_str) for item in candidates]
    results = await authz.batch_enforce(
        user_id=user.id,
        domain=domain,
        requests=requests,
        context=_auth_context(user),
    )
    return [item for item, allowed in zip(candidates, results, strict=True) if allowed]


def _default_resource_id_getter(item: Any) -> UUID:
    """Default key extractor used by filter_visible_resources."""
    return item.id


def permission_denied_to_http(exc: InsufficientPermissionsError) -> HTTPException:
    """Translate an InsufficientPermissionsError into a 403 HTTPException."""
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=exc.message)
