"""Shared dependencies for the agentic API.

Kept separate from the route definitions so the router-include site can
import the feature gate without a circular import.
"""

from fastapi import HTTPException, status
from lfx.services.deps import get_settings_service
from lfx.utils.flow_validation import admin_only_build_required

from langflow.api.utils.core import CurrentActiveUser

ASSISTANT_ADMIN_ONLY_DETAIL = "The Langflow Assistant is restricted to administrators on this server."


def require_agentic_experience() -> None:
    """Backend gate for the agentic assistant's code-generating/executing endpoints.

    SECURITY: the assistant generates and EXECUTES component code in-process
    (langflow.agentic.helpers.validation.validate_component_runtime and the user-components
    overlay). ``agentic_experience`` is on by default (the Assistant is Langflow's entry-point
    experience); this gate 404s the codegen endpoints when an operator opts out with
    LANGFLOW_AGENTIC_EXPERIENCE=false, matching the per-endpoint precedent in
    api/v1/endpoints.py. Execution entry points are additionally guarded by
    ``allow_custom_components``. The read-only ``/agentic/check-config`` probe is intentionally
    NOT gated so non-agentic deployments can still query provider configuration.
    """
    if not get_settings_service().settings.agentic_experience:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="This endpoint is not available")


def enforce_agentic_component_admin(*, is_superuser: bool) -> None:
    """Apply the shared custom-component policy before assistant execution."""
    if admin_only_build_required(is_superuser=is_superuser):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=ASSISTANT_ADMIN_ONLY_DETAIL)


def require_agentic_component_admin(current_user: CurrentActiveUser) -> None:
    """HTTP dependency for assistant routes that can execute component code."""
    enforce_agentic_component_admin(is_superuser=current_user.is_superuser)
