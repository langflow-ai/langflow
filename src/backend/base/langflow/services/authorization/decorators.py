"""Declarative permission enforcement for non-route async call paths."""

from __future__ import annotations

import functools
import inspect
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any, TypeVar

from fastapi import HTTPException, status

from langflow.services.authorization.actions import (
    DeploymentAction,
    FileAction,
    FlowAction,
    KnowledgeBaseAction,
    ProjectAction,
    ShareAction,
    VariableAction,
)
from langflow.services.authorization.guards import (
    _RESOURCE_SPECS,
    ensure_deployment_permission,
    ensure_file_permission,
    ensure_flow_permission,
    ensure_knowledge_base_permission,
    ensure_project_permission,
    ensure_share_permission,
    ensure_variable_permission,
)

if TYPE_CHECKING:
    from langflow.services.database.models.user.model import User, UserRead

_Action = (
    DeploymentAction
    | FlowAction
    | ProjectAction
    | KnowledgeBaseAction
    | VariableAction
    | FileAction
    | ShareAction
    | str
)

_ENSURE_BY_SPEC: dict[str, Callable[..., Awaitable[None]]] = {
    "flow": ensure_flow_permission,
    "deployment": ensure_deployment_permission,
    "project": ensure_project_permission,
    "knowledge_base": ensure_knowledge_base_permission,
    "variable": ensure_variable_permission,
    "file": ensure_file_permission,
    "share": ensure_share_permission,
}

# Map registry specs to ORM attribute names used when ``resource_param`` is set.
_ORM_ATTR_BY_SPEC_KW: dict[str, dict[str, str]] = {
    "flow": {
        "flow_id": "id",
        "flow_user_id": "user_id",
        "workspace_id": "workspace_id",
        "folder_id": "folder_id",
    },
    "deployment": {
        "deployment_id": "id",
        "deployment_user_id": "user_id",
        "workspace_id": "workspace_id",
        "project_id": "project_id",
    },
    "project": {
        "project_id": "id",
        "project_user_id": "user_id",
        "workspace_id": "workspace_id",
    },
    "knowledge_base": {
        "kb_id": "id",
        "kb_user_id": "user_id",
        "workspace_id": "workspace_id",
        "project_id": "project_id",
        "kb_name": "name",
    },
    "variable": {
        "variable_id": "id",
        "variable_user_id": "user_id",
        "workspace_id": "workspace_id",
    },
    "file": {
        "file_id": "id",
        "file_user_id": "user_id",
        "workspace_id": "workspace_id",
    },
    "share": {
        "share_id": "id",
        "share_user_id": "user_id",
    },
}

_F = TypeVar("_F", bound=Callable[..., Awaitable[Any]])


def _action_value(act: _Action) -> str:
    """Return the string value for enum-like and raw-string actions."""
    return str(getattr(act, "value", act))


def _requires_resource_id(act: _Action) -> bool:
    """Return True when the action targets an existing resource."""
    return _action_value(act) != "create"


def _raise_missing_resource_id(func_name: str, spec_key: str, id_kw: str) -> None:
    msg = f"@requires_resource_permission: '{func_name}' requires a non-null '{id_kw}' for {spec_key} permission"
    raise ValueError(msg)


def _kwargs_from_resource(spec_key: str, resource: Any) -> dict[str, Any]:
    """Build ensure_* kwargs from a loaded ORM row."""
    spec = _RESOURCE_SPECS[spec_key]
    attr_map = _ORM_ATTR_BY_SPEC_KW[spec_key]
    out: dict[str, Any] = {}
    if spec.id_kw in attr_map:
        out[spec.id_kw] = getattr(resource, attr_map[spec.id_kw], None)
    if spec.owner_kw in attr_map:
        out[spec.owner_kw] = getattr(resource, attr_map[spec.owner_kw], None)
    if spec.workspace_kw and spec.workspace_kw in attr_map:
        out[spec.workspace_kw] = getattr(resource, attr_map[spec.workspace_kw], None)
    if spec.scope_kw and spec.scope_kw in attr_map:
        out[spec.scope_kw] = getattr(resource, attr_map[spec.scope_kw], None)
    for extra in spec.extra_context_kws:
        if extra in attr_map:
            out[extra] = getattr(resource, attr_map[extra], None)
    return out


def requires_resource_permission(
    spec_key: str,
    act: _Action,
    *,
    user_param: str = "user",
    resource_param: str | None = None,
    forbidden_as_not_found: bool = False,
    not_found_template: str = "Resource not found",
) -> Callable[[_F], _F]:
    """Enforce a resource permission before the decorated async function runs.

    When ``resource_param`` is set, permission kwargs are taken from that ORM
    object (e.g. a loaded ``Flow``). Otherwise the decorated function must
    expose parameters matching the registry's public kwarg names
    (``flow_id``, ``flow_user_id``, ...).

    ``forbidden_as_not_found`` maps HTTP 403 to ``ValueError`` for helpers
    that historically surfaced denials as "not found" (e.g. ``load_flow``).
    """
    if spec_key not in _RESOURCE_SPECS:
        msg = f"Unknown resource spec: {spec_key}"
        raise ValueError(msg)

    ensure_fn = _ENSURE_BY_SPEC[spec_key]

    def decorator(func: _F) -> _F:
        sig = inspect.signature(func)

        if user_param not in sig.parameters:
            msg = (
                f"@requires_resource_permission: '{func.__name__}' must have "
                f"a '{user_param}' parameter (got {list(sig.parameters)})"
            )
            raise TypeError(msg)
        if resource_param is not None and resource_param not in sig.parameters:
            msg = (
                f"@requires_resource_permission: '{func.__name__}' must have "
                f"a '{resource_param}' parameter when resource_param is set"
            )
            raise TypeError(msg)
        spec = _RESOURCE_SPECS[spec_key]
        if resource_param is None and _requires_resource_id(act) and spec.id_kw not in sig.parameters:
            msg = (
                f"@requires_resource_permission: '{func.__name__}' must have "
                f"a '{spec.id_kw}' parameter for {spec_key} permission"
            )
            raise TypeError(msg)

        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            bound = sig.bind(*args, **kwargs)
            bound.apply_defaults()
            arguments = bound.arguments

            user: User | UserRead = arguments[user_param]
            if resource_param is not None:
                perm_kwargs = _kwargs_from_resource(spec_key, arguments[resource_param])
            else:
                perm_kwargs = {}
                for kw in (
                    spec.id_kw,
                    spec.owner_kw,
                    *(spec.extra_context_kws or ()),
                ):
                    if kw in arguments:
                        perm_kwargs[kw] = arguments[kw]
                if spec.workspace_kw and spec.workspace_kw in arguments:
                    perm_kwargs[spec.workspace_kw] = arguments[spec.workspace_kw]
                if spec.scope_kw and spec.scope_kw in arguments:
                    perm_kwargs[spec.scope_kw] = arguments[spec.scope_kw]

            if _requires_resource_id(act) and perm_kwargs.get(spec.id_kw) is None:
                _raise_missing_resource_id(func.__name__, spec_key, spec.id_kw)

            try:
                await ensure_fn(user, act, **perm_kwargs)
            except HTTPException as exc:
                if forbidden_as_not_found and exc.status_code == status.HTTP_403_FORBIDDEN:
                    raise ValueError(not_found_template) from exc
                raise
            return await func(*args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator


def requires_flow_permission(
    act: FlowAction | str,
    *,
    user_param: str = "user",
    flow_id_param: str = "flow_id",
    flow_user_id_param: str = "flow_user_id",
    flow_param: str | None = None,
    forbidden_as_not_found: bool = False,
    not_found_template: str = "Flow not found",
) -> Callable[[_F], _F]:
    """Flow-specific wrapper over :func:`requires_resource_permission`."""
    if flow_param is not None:
        return requires_resource_permission(
            "flow",
            act,
            user_param=user_param,
            resource_param=flow_param,
            forbidden_as_not_found=forbidden_as_not_found,
            not_found_template=not_found_template,
        )

    def decorator(func: _F) -> _F:
        sig = inspect.signature(func)
        if user_param not in sig.parameters:
            msg = (
                f"@requires_flow_permission: '{func.__name__}' must have "
                f"a '{user_param}' parameter (got {list(sig.parameters)})"
            )
            raise TypeError(msg)
        if _requires_resource_id(act) and flow_id_param not in sig.parameters:
            msg = (
                f"@requires_flow_permission: '{func.__name__}' must have "
                f"a '{flow_id_param}' parameter for flow permission"
            )
            raise TypeError(msg)

        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            bound = sig.bind(*args, **kwargs)
            bound.apply_defaults()
            arguments = bound.arguments
            perm_kwargs = {
                "flow_id": arguments.get(flow_id_param),
                "flow_user_id": arguments.get(flow_user_id_param),
                "workspace_id": arguments.get("workspace_id"),
                "folder_id": arguments.get("folder_id"),
            }
            if _requires_resource_id(act) and perm_kwargs["flow_id"] is None:
                _raise_missing_resource_id(func.__name__, "flow", "flow_id")
            try:
                await ensure_flow_permission(arguments[user_param], act, **perm_kwargs)
            except HTTPException as exc:
                if forbidden_as_not_found and exc.status_code == status.HTTP_403_FORBIDDEN:
                    raise ValueError(not_found_template) from exc
                raise
            return await func(*args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator
