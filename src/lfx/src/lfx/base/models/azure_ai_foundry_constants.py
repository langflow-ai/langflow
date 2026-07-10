"""Azure AI Foundry model catalog primitives.

Foundry deployments are user-specific (the ``model`` parameter must match the
deployment name in the portal), so this is a small seed list shown before
credentials are configured. Once a provider is set up, users enable the
deployments they actually have.
"""

from .model_metadata import create_model_metadata

AZURE_AI_FOUNDRY_MODELS_DETAILED = [
    create_model_metadata(
        provider="Azure AI Foundry",
        name="gpt-4o",
        icon="Azure",
        tool_calling=True,
        default=True,
    ),
    create_model_metadata(
        provider="Azure AI Foundry",
        name="gpt-4o-mini",
        icon="Azure",
        tool_calling=True,
    ),
    create_model_metadata(
        provider="Azure AI Foundry",
        name="gpt-4.1",
        icon="Azure",
        tool_calling=True,
    ),
    create_model_metadata(
        provider="Azure AI Foundry",
        name="o3-mini",
        icon="Azure",
        tool_calling=True,
        reasoning=True,
    ),
    create_model_metadata(
        provider="Azure AI Foundry",
        name="Mistral-Large-3",
        icon="Azure",
        tool_calling=True,
    ),
]
