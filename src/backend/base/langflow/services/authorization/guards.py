"""Permission-enforcement guards for guarded API routes."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from fastapi import HTTPException, status
from lfx.log.logger import logger

from langflow.services.auth.context import (
    current_auth_context_for_audit,
    current_auth_context_for_authz,
    current_auth_is_api_key,
)
from langflow.services.authorization import audit as _audit
from langflow.services.authorization.access_ceiling import (
    external_access_allows,
    get_current_external_access_context,
)
from langflow.services.authorization.actions import (
    DeploymentAction,
    FileAction,
    FlowAction,
    KnowledgeBaseAction,
    ProjectAction,
    ProviderAccountAction,
    ShareAction,
    VariableAction,
    VoiceAction,
)
from langflow.services.deps import get_authorization_service, get_settings_service

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

    from langflow.services.database.models.user.model import User, UserRead

# Action enums coerced to string values.
_ACTION_ENUMS = (
    FlowAction,
    DeploymentAction,
    ProjectAction,
    KnowledgeBaseAction,
    VariableAction,
    FileAction,
    ShareAction,
    ProviderAccountAction,
    VoiceAction,
)

# Resource-owner keys included in audit details (kept in one place so a new
# resource type does not need to hand-update ``ensure_permission``).
_OWNER_CONTEXT_KEYS = (
    "flow_user_id",
    "deployment_user_id",
    "project_user_id",
    "knowledge_base_user_id",
    "variable_user_id",
    "file_user_id",
    "share_user_id",
    "provider_account_user_id",
    "voice_user_id",
)

# Default 403 detail. UUID-leaking detail strings are opt-in via ``detail=...``
# on ``ensure_permission`` so the secure default is the easy path. See review
# item I2 on PR #13153.
_DEFAULT_DENY_DETAIL = "Permission denied"


def _auth_context(user: User | UserRead) -> dict[str, Any]:
    """Build the base context dict passed to authorization enforce calls."""
    return {
        **current_auth_context_for_authz(),
        "is_superuser": getattr(user, "is_superuser", False),
    }


def _auth_audit_details() -> dict[str, str]:
    """Build JSON-friendly auth context for audit details."""
    return current_auth_context_for_audit()


async def _api_key_scopes_require_plugin_enforcement() -> bool:
    """Return True when owner override must not hide API-key caveats."""
    if not current_auth_is_api_key():
        return False

    settings = get_settings_service()
    if not settings.auth_settings.AUTHZ_ENABLED:
        return False

    authz = get_authorization_service()
    supports_api_key_scopes = getattr(authz, "supports_api_key_scopes", None)
    if supports_api_key_scopes is None:
        return False
    try:
        return bool(await supports_api_key_scopes())
    except Exception:  # noqa: BLE001
        logger.exception("Authorization plugin failed API-key scope capability check; preserving owner override")
        return False


async def should_apply_owner_override() -> bool:
    """Return True when Langflow should apply the built-in owner override."""
    return not await _api_key_scopes_require_plugin_enforcement()


def _coerce_action(
    act: DeploymentAction
    | FlowAction
    | ProjectAction
    | KnowledgeBaseAction
    | VariableAction
    | FileAction
    | ShareAction
    | ProviderAccountAction
    | VoiceAction
    | str,
) -> str:
    """Return the string value of an action enum or pass through a raw string."""
    if isinstance(act, _ACTION_ENUMS):
        return act.value
    return act


def _resolve_authz_domain(workspace_id: UUID | None, scope_id: UUID | None) -> str:
    """Resolve policy domain: project scope, then workspace, else ``*``."""
    if scope_id is not None:
        return f"project:{scope_id}"
    if workspace_id is not None:
        return f"workspace:{workspace_id}"
    return "*"


# Backward-compatible alias.
_resolve_flow_domain = _resolve_authz_domain


async def ensure_permission(
    user: User | UserRead,
    *,
    domain: str,
    obj: str,
    act: str,
    context: dict[str, Any] | None = None,
    detail: str | None = None,
) -> None:
    """Raise HTTP 403 when the user may not perform the action (audited).

    ``detail`` overrides the default non-disclosing 403 message. Callers that
    have already verified the resource exists for the requester (e.g. routes
    operating on user-owned data) may pass a richer string. The default is
    intentionally generic so a missing ``deny_to_404`` wrap cannot leak the
    resource UUID — see review item I2 on PR #13153.
    """
    # Caller context first; user auth fields cannot be overwritten.
    merged_context = {**(context or {}), **_auth_context(user)}
    audit_action = f"{obj.split(':', 1)[0]}:{act}" if ":" in obj else act
    audit_details: dict[str, Any] = {"domain": domain, **_auth_audit_details()}
    for owner_key in _OWNER_CONTEXT_KEYS:
        if owner_key in merged_context and merged_context[owner_key] is not None:
            audit_details[owner_key] = str(merged_context[owner_key])

    settings = get_settings_service()
    if not settings.auth_settings.AUTHZ_ENABLED:
        # Auditing is independently configurable so operators can observe the
        # allow-by-disabled-enforcement path before turning RBAC on.
        await _audit.audit_decision(
            user_id=user.id,
            action=audit_action,
            obj=obj,
            result=_audit.AUDIT_ALLOW,
            details=audit_details,
        )
        return

    authz = get_authorization_service()
    # Fail closed when enforce() raises (deny + audit, not HTTP 500).
    deny_detail = detail if detail is not None else _DEFAULT_DENY_DETAIL
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
        await _audit.audit_decision(
            user_id=user.id,
            action=audit_action,
            obj=obj,
            result=_audit.AUDIT_DENY,
            details={**audit_details, "error": str(exc)},
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=deny_detail,
        ) from exc

    await _audit.audit_decision(
        user_id=user.id,
        action=audit_action,
        obj=obj,
        result=_audit.AUDIT_ALLOW if allowed else _audit.AUDIT_DENY,
        details=audit_details,
    )

    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=deny_detail,
        )


async def _ensure_resource_permission(
    user: User | UserRead,
    *,
    resource_type: str,
    resource_id: UUID | str | None,
    owner_id: UUID | None,
    owner_override_allowed: bool,
    act_str: str,
    resolved_domain: str,
    extra_context: dict[str, Any],
) -> None:
    """Build object key, apply owner override, else delegate to ensure_permission."""
    obj = f"{resource_type}:{resource_id}" if resource_id else f"{resource_type}:*"

    external_context = get_current_external_access_context()
    if external_context is not None and not external_access_allows(act_str, external_context):
        await _audit.audit_decision(
            user_id=user.id,
            action=f"{resource_type}:{act_str}",
            obj=obj,
            result=_audit.AUDIT_DENY,
            details={
                "domain": resolved_domain,
                "external_auth_provider": external_context.provider,
                "external_access_level": external_context.level,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="External credentials do not allow this action",
        )

    if (
        owner_override_allowed
        and owner_id is not None
        and getattr(user, "id", None) == owner_id
        and await should_apply_owner_override()
    ):
        await _audit.audit_decision(
            user_id=user.id,
            action=f"{resource_type}:{act_str}",
            obj=obj,
            result=_audit.AUDIT_OWNER_OVERRIDE,
            details={"domain": resolved_domain, **_auth_audit_details()},
        )
        return

    await ensure_permission(
        user,
        domain=resolved_domain,
        obj=obj,
        act=act_str,
        context=extra_context,
    )


# --------------------------------------------------------------------------- #
# Resource registry — collapses the ensure_*_permission family into one path.
# See review item I1 on PR #13153.
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class _ResourceSpec:
    """Static metadata for one resource type's ``ensure_*_permission`` helper."""

    resource_type: str  # Object slug prefix, e.g. "flow"
    owner_kw: str  # Public kwarg carrying the owner id, e.g. "flow_user_id"
    id_kw: str  # Public kwarg carrying the resource id, e.g. "flow_id"
    # Public kwarg the resolver consults for the *outer* domain bucket
    # (workspace). ``None`` means the helper does not accept a workspace scope.
    workspace_kw: str | None
    # Public kwarg the resolver consults for the *inner* domain bucket
    # (project/folder). ``None`` means the helper does not accept this scope.
    scope_kw: str | None
    # Extra kwargs forwarded verbatim into ``extra_context`` (no domain effect).
    extra_context_kws: tuple[str, ...] = ()
    # CREATE normally has no existing resource owner, so caller-supplied owner
    # ids must not trigger the owner override. Resource families whose CREATE
    # action targets an existing owned resource may opt in explicitly.
    owner_override_on_create: bool = False


_RESOURCE_SPECS: dict[str, _ResourceSpec] = {
    "flow": _ResourceSpec(
        resource_type="flow",
        owner_kw="flow_user_id",
        id_kw="flow_id",
        workspace_kw="workspace_id",
        scope_kw="folder_id",
    ),
    "deployment": _ResourceSpec(
        resource_type="deployment",
        owner_kw="deployment_user_id",
        id_kw="deployment_id",
        workspace_kw="workspace_id",
        scope_kw="project_id",
    ),
    "project": _ResourceSpec(
        resource_type="project",
        owner_kw="project_user_id",
        id_kw="project_id",
        workspace_kw="workspace_id",
        scope_kw=None,
    ),
    "knowledge_base": _ResourceSpec(
        resource_type="knowledge_base",
        owner_kw="kb_user_id",
        id_kw="kb_id",
        workspace_kw="workspace_id",
        scope_kw="project_id",
        extra_context_kws=("kb_name",),
    ),
    "variable": _ResourceSpec(
        resource_type="variable",
        owner_kw="variable_user_id",
        id_kw="variable_id",
        workspace_kw="workspace_id",
        scope_kw=None,
    ),
    "file": _ResourceSpec(
        resource_type="file",
        owner_kw="file_user_id",
        id_kw="file_id",
        workspace_kw="workspace_id",
        scope_kw=None,
    ),
    "share": _ResourceSpec(
        resource_type="share",
        owner_kw="share_user_id",
        id_kw="share_id",
        workspace_kw=None,
        scope_kw=None,
        # Creating a share authorizes against the already-existing target
        # resource owner, not the prospective share-row owner.
        owner_override_on_create=True,
    ),
    "provider_account": _ResourceSpec(
        resource_type="provider_account",
        owner_kw="provider_account_user_id",
        id_kw="provider_account_id",
        workspace_kw=None,
        scope_kw=None,
        # A newly-created provider account always belongs to the caller.
        owner_override_on_create=True,
    ),
    "voice": _ResourceSpec(
        resource_type="voice",
        owner_kw="voice_user_id",
        id_kw="voice_id",
        workspace_kw=None,
        scope_kw=None,
    ),
}


async def _ensure_typed(
    user: User | UserRead,
    *,
    spec_key: str,
    act_str: str,
    kwargs: dict[str, Any],
    domain_override: str | None,
) -> None:
    """Shared body for ``ensure_*_permission`` helpers.

    ``kwargs`` is the keyword-argument dict the caller passed to the public
    helper. The registry tells us which key carries the id, the owner, and the
    domain components; everything else flows into ``extra_context`` verbatim.
    """
    spec = _RESOURCE_SPECS[spec_key]

    resource_id = kwargs.get(spec.id_kw)
    owner_id = kwargs.get(spec.owner_kw)
    workspace_id = kwargs.get(spec.workspace_kw) if spec.workspace_kw else None
    scope_id = kwargs.get(spec.scope_kw) if spec.scope_kw else None

    if domain_override is not None:
        resolved_domain = domain_override
    elif spec.workspace_kw is None and spec.scope_kw is None:
        # Shares have no domain bucket.
        resolved_domain = "*"
    else:
        resolved_domain = _resolve_authz_domain(workspace_id, scope_id)

    # ``extra_context`` mirrors the legacy clone shape so audit rows and
    # plugin matchers continue to see the same key names. We forward every
    # kwarg the helper declares except ``domain`` (already resolved).
    extra_context: dict[str, Any] = {}
    if spec.workspace_kw is not None:
        extra_context[spec.workspace_kw] = workspace_id
    if spec.scope_kw is not None:
        extra_context[spec.scope_kw] = scope_id
    extra_context[spec.owner_kw] = owner_id
    if spec_key == "knowledge_base":
        # KB also forwards the resource id under its public name for plugins
        # that scope policy by kb_id directly (mirrors the legacy clone).
        extra_context[spec.id_kw] = resource_id
    for key in spec.extra_context_kws:
        extra_context[key] = kwargs.get(key)

    await _ensure_resource_permission(
        user,
        resource_type=spec.resource_type,
        resource_id=resource_id,
        owner_id=owner_id,
        owner_override_allowed=act_str != "create" or spec.owner_override_on_create,
        act_str=act_str,
        resolved_domain=resolved_domain,
        extra_context=extra_context,
    )


# --------------------------------------------------------------------------- #
# Public ``ensure_*_permission`` helpers — thin wrappers over ``_ensure_typed``.
# Kept individually typed so call sites get IDE / mypy help on which kwargs
# each resource accepts.
# --------------------------------------------------------------------------- #


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
    await _ensure_typed(
        user,
        spec_key="flow",
        act_str=_coerce_action(act),
        kwargs={
            "flow_id": flow_id,
            "flow_user_id": flow_user_id,
            "workspace_id": workspace_id,
            "folder_id": folder_id,
        },
        domain_override=domain,
    )


async def _audit_flow_decision_batch(
    *,
    user_id: UUID | None,
    act_str: str,
    domain: str,
    flow_results: Sequence[tuple[UUID, str]],
) -> None:
    """Audit one allow/deny/owner-override decision per flow id concurrently."""
    await asyncio.gather(
        *(
            _audit.audit_decision(
                user_id=user_id,
                action=f"flow:{act_str}",
                obj=f"flow:{flow_id}",
                result=result,
                details={"domain": domain, **_auth_audit_details()},
            )
            for flow_id, result in flow_results
        )
    )


async def ensure_flows_permission(
    user: User | UserRead,
    act: FlowAction | str,
    *,
    flow_ids: Sequence[UUID],
    flow_user_id: UUID | None = None,
    workspace_id: UUID | None = None,
    folder_id: UUID | None = None,
) -> None:
    """Authorize ``act`` on every flow id via batched plugin enforce.

    Mirrors :func:`ensure_flow_permission` semantics (external-access ceiling,
    owner override, domain resolution, audit) but issues one
    ``batch_enforce`` call instead of N individual ``enforce`` round-trips.
    ``flow_user_id`` / ``workspace_id`` / ``folder_id`` apply to the whole
    batch (same owner-namespace / domain for every id). Raises HTTP 403 if any
    flow is denied.
    """
    if not flow_ids:
        return

    act_str = _coerce_action(act)
    user_id = getattr(user, "id", None)
    resolved_domain = _resolve_authz_domain(workspace_id, folder_id)

    external_context = get_current_external_access_context()
    if external_context is not None and not external_access_allows(act_str, external_context):
        # Same fail-closed path as the single-flow guard; audit the ceiling deny
        # once rather than per flow.
        await _audit.audit_decision(
            user_id=user_id,
            action=f"flow:{act_str}",
            obj="flow:*",
            result=_audit.AUDIT_DENY,
            details={
                "domain": resolved_domain,
                "external_auth_provider": external_context.provider,
                "external_access_level": external_context.level,
                "flow_count": len(flow_ids),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="External credentials do not allow this action",
        )

    settings = get_settings_service()
    if not settings.auth_settings.AUTHZ_ENABLED:
        await _audit_flow_decision_batch(
            user_id=user_id,
            act_str=act_str,
            domain=resolved_domain,
            flow_results=[(flow_id, _audit.AUDIT_ALLOW) for flow_id in flow_ids],
        )
        return

    auth_context = _auth_context(user)
    owner_override_enabled = await should_apply_owner_override()
    if owner_override_enabled and user_id is not None and flow_user_id == user_id:
        await _audit_flow_decision_batch(
            user_id=user_id,
            act_str=act_str,
            domain=resolved_domain,
            flow_results=[(flow_id, _audit.AUDIT_OWNER_OVERRIDE) for flow_id in flow_ids],
        )
        return

    authz = get_authorization_service()
    requests = [(f"flow:{flow_id}", act_str) for flow_id in flow_ids]
    try:
        results = await authz.batch_enforce(
            user_id=user_id,
            domain=resolved_domain,
            requests=requests,
            context=auth_context,
        )
    except Exception as exc:
        logger.exception("Authorization plugin raised during batch_enforce; failing closed")
        await _audit.audit_decision(
            user_id=user_id,
            action=f"flow:{act_str}",
            obj="flow:*",
            result=_audit.AUDIT_DENY,
            details={"domain": resolved_domain, "error": str(exc), **_auth_audit_details()},
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=_DEFAULT_DENY_DETAIL,
        ) from exc

    if len(results) != len(flow_ids):
        logger.error(
            "Authorization plugin returned %d batch results for %d flow ids; failing closed",
            len(results),
            len(flow_ids),
        )
        await _audit.audit_decision(
            user_id=user_id,
            action=f"flow:{act_str}",
            obj="flow:*",
            result=_audit.AUDIT_DENY,
            details={
                "domain": resolved_domain,
                "error": "batch_enforce result count mismatch",
                "expected_results": len(flow_ids),
                "actual_results": len(results),
                **_auth_audit_details(),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=_DEFAULT_DENY_DETAIL,
        )

    await _audit_flow_decision_batch(
        user_id=user_id,
        act_str=act_str,
        domain=resolved_domain,
        flow_results=[
            (flow_id, _audit.AUDIT_ALLOW if allowed else _audit.AUDIT_DENY)
            for flow_id, allowed in zip(flow_ids, results, strict=True)
        ],
    )
    if not all(results):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=_DEFAULT_DENY_DETAIL,
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
    await _ensure_typed(
        user,
        spec_key="deployment",
        act_str=_coerce_action(act),
        kwargs={
            "deployment_id": deployment_id,
            "deployment_user_id": deployment_user_id,
            "workspace_id": workspace_id,
            "project_id": project_id,
        },
        domain_override=domain,
    )


async def ensure_provider_account_permission(
    user: User | UserRead,
    act: ProviderAccountAction | str,
    *,
    provider_account_id: UUID | None = None,
    provider_account_user_id: UUID | None = None,
    domain: str | None = None,
) -> None:
    """Check provider-account permission without exposing credential metadata."""
    await _ensure_typed(
        user,
        spec_key="provider_account",
        act_str=_coerce_action(act),
        kwargs={
            "provider_account_id": provider_account_id,
            "provider_account_user_id": provider_account_user_id,
        },
        domain_override=domain,
    )


async def ensure_voice_permission(
    user: User | UserRead,
    act: VoiceAction | str,
    *,
    voice_id: UUID | None = None,
    voice_user_id: UUID | None = None,
    domain: str | None = None,
) -> None:
    """Check credential-backed voice permission."""
    await _ensure_typed(
        user,
        spec_key="voice",
        act_str=_coerce_action(act),
        kwargs={
            "voice_id": voice_id,
            "voice_user_id": voice_user_id,
        },
        domain_override=domain,
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
    await _ensure_typed(
        user,
        spec_key="project",
        act_str=_coerce_action(act),
        kwargs={
            "project_id": project_id,
            "project_user_id": project_user_id,
            "workspace_id": workspace_id,
        },
        domain_override=domain,
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
    await _ensure_typed(
        user,
        spec_key="knowledge_base",
        act_str=_coerce_action(act),
        kwargs={
            "kb_id": kb_id,
            "kb_user_id": kb_user_id,
            "kb_name": kb_name,
            "workspace_id": workspace_id,
            "project_id": project_id,
        },
        domain_override=domain,
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
    await _ensure_typed(
        user,
        spec_key="variable",
        act_str=_coerce_action(act),
        kwargs={
            "variable_id": variable_id,
            "variable_user_id": variable_user_id,
            "workspace_id": workspace_id,
        },
        domain_override=domain,
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
    await _ensure_typed(
        user,
        spec_key="file",
        act_str=_coerce_action(act),
        kwargs={
            "file_id": file_id,
            "file_user_id": file_user_id,
            "workspace_id": workspace_id,
        },
        domain_override=domain,
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
    await _ensure_typed(
        user,
        spec_key="share",
        act_str=_coerce_action(act),
        kwargs={
            "share_id": share_id,
            "share_user_id": share_user_id,
        },
        domain_override=domain,
    )
