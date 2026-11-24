"""Schemas for the deployment_provider_account package.

Kept separate from ``model.py`` so that modules like ``utils.py`` can
import these types without pulling in SQLModel / SQLAlchemy and without
creating circular dependencies.
"""

from enum import Enum


class DeploymentProviderKey(str, Enum):
    """Deployment provider identifiers recognised by Langflow.

    Each member value must match the adapter registry key used by
    ``get_deployment_adapter(adapter_key)`` in LFX and the corresponding
    mapper registration in the Langflow mapper registry.
    """

    WATSONX_ORCHESTRATE = "watsonx-orchestrate"
