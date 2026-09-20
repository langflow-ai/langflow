"""Pure helpers for binding trusted model-provider policy scope."""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

from lfx.services.model_provider_policy import (
    reset_current_model_provider_policy_context,
    set_current_model_provider_policy_context,
)

if TYPE_CHECKING:
    from collections.abc import Iterator
    from uuid import UUID

    from langflow.services.database.models.flow.model import Flow, FlowRead

ProviderPolicyAttributes = dict[str, Any]


def provider_policy_attributes_for_flow(
    flow: Flow | FlowRead,
    *,
    is_superuser: bool,
    required: bool = False,
) -> ProviderPolicyAttributes:
    """Build policy attributes only from a flow row loaded by the server."""
    attributes: ProviderPolicyAttributes = {"is_superuser": is_superuser}
    project_id = getattr(flow, "folder_id", None)
    workspace_id = getattr(flow, "workspace_id", None)
    if project_id is not None:
        attributes["project_id"] = project_id
    if workspace_id is not None:
        attributes["workspace_id"] = workspace_id
    if required:
        attributes["provider_scope_required"] = True
    return attributes


@contextmanager
def scoped_model_provider_policy_for_flow(
    flow: Flow | FlowRead | None,
    *,
    user_id: UUID | str | None,
    is_superuser: bool,
) -> Iterator[None]:
    """Bind a required stored-flow scope for graph construction and execution.

    ``None`` deliberately binds a *required but unresolved* scope. The
    Enterprise policy service rejects that context before a provider can read
    credentials or initialize a client, so an internal runtime caller that
    forgets to pass its server-loaded flow fails closed instead of silently
    falling back to a global grant.
    """
    attributes: ProviderPolicyAttributes = {
        "is_superuser": is_superuser,
        "provider_scope_required": True,
    }
    if flow is not None:
        attributes = provider_policy_attributes_for_flow(
            flow,
            is_superuser=is_superuser,
            required=True,
        )
    token = set_current_model_provider_policy_context(
        user_id=user_id,
        attributes=attributes,
    )
    try:
        yield
    finally:
        reset_current_model_provider_policy_context(token)


__all__ = [
    "ProviderPolicyAttributes",
    "provider_policy_attributes_for_flow",
    "scoped_model_provider_policy_for_flow",
]
