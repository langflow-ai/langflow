"""Shared dependencies for the agentic API.

Kept in a leaf module (only fastapi + lfx settings) so both the route definitions
(langflow.agentic.api.router) and the router-include site (langflow.api.router) can import it
without a circular import.
"""

from fastapi import HTTPException, status
from lfx.services.deps import get_settings_service


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
