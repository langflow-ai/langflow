"""Register the Watsonx Orchestrate deployment adapter.

Importing this module requires the optional IBM SDK dependencies because
the service module loads them.
"""

from lfx.services.adapters.registry import register_adapter
from lfx.services.adapters.schema import AdapterType

from langflow.services.adapters.deployment.watsonx_orchestrate.constants import (
    WATSONX_ORCHESTRATE_DEPLOYMENT_ADAPTER_KEY,
)
from langflow.services.adapters.deployment.watsonx_orchestrate.service import WatsonxOrchestrateDeploymentService

register_adapter(
    AdapterType.DEPLOYMENT,
    WATSONX_ORCHESTRATE_DEPLOYMENT_ADAPTER_KEY,
)(WatsonxOrchestrateDeploymentService)
