"""Azure AI Foundry model catalog primitives.

Foundry's ``model`` parameter must match the **deployment name** in the portal
(user-chosen, e.g. ``gpt-5-mini``), not a catalog model id. The OpenAI-
compatible ``/models`` route returns the regional catalog and is not a
deployment list, so Langflow keeps this small seed of common names and lets
users add their real deployment names as free-text in Model Providers.
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
