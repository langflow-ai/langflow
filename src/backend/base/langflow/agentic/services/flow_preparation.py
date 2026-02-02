"""Flow data preparation and model injection."""

import json
from pathlib import Path

from lfx.base.models.unified_models import get_provider_config


def inject_model_into_flow(
    flow_data: dict,
    provider: str,
    model_name: str,
    api_key_var: str | None = None,
) -> dict:
    """Inject model configuration into the flow's Agent component.

    Args:
        flow_data: The flow JSON as a dict
        provider: The provider name (e.g., "OpenAI", "Anthropic")
        model_name: The model name (e.g., "gpt-4o", "claude-sonnet-4-5-20250929")
        api_key_var: Optional API key variable name. If not provided, uses provider's default.

    Returns:
        Modified flow data with the model configuration injected

    Raises:
        ValueError: If provider is unknown
    """
    provider_config = get_provider_config(provider)

    # Use provided api_key_var or default from config
    api_key_var = api_key_var or provider_config["variable_name"]

    metadata = {
        "api_key_param": provider_config["api_key_param"],
        "context_length": 128000,
        "model_class": provider_config["model_class"],
        "model_name_param": provider_config["model_name_param"],
    }

    # Add extra params from provider config (url_param, project_id_param, base_url_param)
    for extra_param in ("url_param", "project_id_param", "base_url_param"):
        if extra_param in provider_config:
            metadata[extra_param] = provider_config[extra_param]

    model_value = [
        {
            "category": provider,
            "icon": provider_config["icon"],
            "metadata": metadata,
            "name": model_name,
            "provider": provider,
        }
    ]

    # Inject into all Agent nodes
    for node in flow_data.get("data", {}).get("nodes", []):
        node_data = node.get("data", {})
        if node_data.get("type") == "Agent":
            template = node_data.get("node", {}).get("template", {})
            if "model" in template:
                template["model"]["value"] = model_value
            # Note: Do NOT set api_key here. The Agent component will automatically
            # look up the API key from the user's global variables using get_api_key_for_provider()
            # when the api_key field is empty/falsy.

    return flow_data


def load_and_prepare_flow(
    flow_path: Path,
    provider: str | None,
    model_name: str | None,
    api_key_var: str | None,
) -> str:
    """Load flow file and prepare JSON with model injection."""
    flow_data = json.loads(flow_path.read_text())

    if provider and model_name:
        flow_data = inject_model_into_flow(flow_data, provider, model_name, api_key_var)

    return json.dumps(flow_data)
