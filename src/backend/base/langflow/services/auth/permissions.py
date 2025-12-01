"""Permission checking utilities for flow operations."""

import logging
from typing import TYPE_CHECKING
from fastapi import Request

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from langflow.services.database.models.user.model import User
    from langflow.services.database.models.flow.model import Flow


def get_user_roles_from_request(request: Request) -> list[str]:
    """Extract Keycloak roles from request context.

    Roles are stored in request.state.user (LangflowUser object)
    which is set by AuthMiddleware.

    Args:
        request: FastAPI Request object

    Returns:
        List of role names from resource_access.account.roles
        Returns empty list if roles not available
    """
    if hasattr(request, "state") and hasattr(request.state, "user"):
        genesis_user = request.state.user

        if hasattr(genesis_user, "roles"):
            roles = genesis_user.roles or []
            return roles

    return []


def has_manage_account_role(roles: list[str]) -> bool:
    """Check if user has 'manage-account' role.

    Args:
        roles: List of role names

    Returns:
        True if "manage-account" in roles, False otherwise
    """
    return "manage-account" in roles


def has_marketplace_admin_role(roles: list[str]) -> bool:
    """Check if user has 'Marketplace Admin' role.

    Args:
        roles: List of role names

    Returns:
        True if "Marketplace Admin" in roles, False otherwise
    """
    return "Marketplace Admin" in roles


def can_edit_flow(
    current_user: "User",
    flow: "Flow",
    user_roles: list[str] = None
) -> bool:
    """Check if user can edit a specific flow.

    Permission logic:
    1. Flow owner (flow.user_id == user.id) → ALLOW
    2. Superuser (user.is_superuser == True) → ALLOW
    3. User has "manage-account" role → ALLOW
    4. User has "Marketplace Admin" role → ALLOW
    5. Otherwise → DENY

    Args:
        current_user: Current authenticated user
        flow: Flow to check permissions for
        user_roles: Optional list of user roles from JWT

    Returns:
        True if user can edit the flow, False otherwise
    """
    # 1. Owner check
    if flow.user_id == current_user.id:
        return True

    # 2. Superuser check
    if current_user.is_superuser:
        return True

    # 3. Role check - user has "manage-account" role
    if user_roles and has_manage_account_role(user_roles):
        return True

    # 4. Role check - user has "Marketplace Admin" role
    if user_roles and has_marketplace_admin_role(user_roles):
        return True

    # 5. Deny by default
    return False


def can_delete_flow(
    current_user: "User",
    flow: "Flow",
    user_roles: list[str] = None
) -> bool:
    """Check if user can delete a specific flow.

    Uses same logic as can_edit_flow.

    Args:
        current_user: Current authenticated user
        flow: Flow to check permissions for
        user_roles: Optional list of user roles from JWT

    Returns:
        True if user can delete the flow, False otherwise
    """
    return can_edit_flow(current_user, flow, user_roles)


def can_view_flow(
    current_user: "User",
    flow: "Flow",
    user_roles: list[str] = None
) -> bool:
    """Check if user can view a specific flow.

    Uses same logic as can_edit_flow - if you can edit, you can view.

    Permission logic:
    1. Flow owner (flow.user_id == user.id) → ALLOW
    2. Superuser (user.is_superuser == True) → ALLOW
    3. User has "manage-account" role → ALLOW
    4. User has "Marketplace Admin" role → ALLOW
    5. Otherwise → DENY

    Args:
        current_user: Current authenticated user
        flow: Flow to check permissions for
        user_roles: Optional list of user roles from JWT

    Returns:
        True if user can view the flow, False otherwise
    """
    return can_edit_flow(current_user, flow, user_roles)
