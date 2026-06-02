"""Watsonx Orchestrate deployment adapter package.

Keep package-level exports lazy: both ``service.py`` and ``types.py`` import
optional IBM SDK modules. This prevents imports of SDK-independent modules,
such as ``payloads.py``, from requiring the ``ibm-watsonx-clients`` extra.
"""

__all__ = ["WatsonxOrchestrateDeploymentService", "WxOCredentials"]


def __getattr__(name: str):
    if name == "WatsonxOrchestrateDeploymentService":
        from langflow.services.adapters.deployment.watsonx_orchestrate.service import (
            WatsonxOrchestrateDeploymentService,
        )

        return WatsonxOrchestrateDeploymentService
    if name == "WxOCredentials":
        from langflow.services.adapters.deployment.watsonx_orchestrate.types import WxOCredentials

        return WxOCredentials
    raise AttributeError(name)
