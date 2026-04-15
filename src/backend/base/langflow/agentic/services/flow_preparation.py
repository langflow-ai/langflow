"""Flow data preparation and model injection."""

import json
from pathlib import Path

from lfx.base.models.model_metadata import MODEL_PROVIDER_METADATA, get_provider_param_mapping

import lfx

# Relative path embedded in the bundled LangflowAssistant.json flow for the
# Directory component that scans built-in lfx components. It only resolves
# correctly when the process CWD is the monorepo root, which is never the
# case for a packaged install (Langflow Desktop, `pip install langflow`,
# Docker, etc.). inject_lfx_components_path rewrites it to an absolute path
# derived from the installed lfx package at runtime.
LFX_COMPONENTS_PATH_SENTINEL = "./src/lfx/src/lfx/components/"


def get_provider_config(provider: str) -> dict | None:
    """Return provider metadata for backward compatibility with existing callers/tests."""
    return MODEL_PROVIDER_METADATA.get(provider)


def inject_model_into_flow(
    flow_data: dict,
    provider: str,
    model_name: str,
    api_key_var: str | None = None,
    provider_vars: dict[str, str] | None = None,
) -> dict:
    """Inject model configuration into the flow's Agent component.

    Args:
        flow_data: The flow JSON as a dict
        provider: The provider name (e.g., "OpenAI", "Anthropic")
        model_name: The model name (e.g., "gpt-4o", "claude-sonnet-4-5-20250929")
        api_key_var: Optional API key variable name. If not provided, uses provider's default.
        provider_vars: Optional dict of resolved provider variables (e.g., WATSONX_URL, WATSONX_PROJECT_ID).

    Returns:
        Modified flow data with the model configuration injected

    Raises:
        ValueError: If provider is unknown
    """
    provider_config = get_provider_config(provider)
    if provider_config is None:
        msg = f"Unknown provider: {provider}"
        raise ValueError(msg)
    param_mapping = get_provider_param_mapping(provider)

    # Use provided api_key_var or default from config
    api_key_var = api_key_var or provider_config.get("variable_name")

    metadata = {
        "api_key_param": param_mapping.get("api_key_param", provider_config.get("api_key_param", "api_key")),
        "context_length": 128000,
        "model_class": param_mapping.get("model_class", provider_config.get("model_class", "ChatOpenAI")),
        "model_name_param": param_mapping.get("model_name_param", provider_config.get("model_name_param", "model")),
    }

    # Add extra params from param mapping (url_param, project_id_param, base_url_param)
    for extra_param in ("url_param", "project_id_param", "base_url_param"):
        if extra_param in param_mapping:
            metadata[extra_param] = param_mapping[extra_param]
        elif extra_param in provider_config:
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

    # Resolve provider-specific template fields to inject into Agent nodes
    provider_fields: dict[str, str] = {}
    pv = provider_vars or {}

    if api_key_var:
        provider_fields["api_key"] = api_key_var

    if provider in {"IBM WatsonX", "IBM watsonx.ai"}:
        if pv.get("WATSONX_URL"):
            provider_fields["base_url_ibm_watsonx"] = pv["WATSONX_URL"]
        if pv.get("WATSONX_PROJECT_ID"):
            provider_fields["project_id"] = pv["WATSONX_PROJECT_ID"]
    elif provider == "Ollama":
        if pv.get("OLLAMA_BASE_URL"):
            provider_fields["base_url_ollama"] = pv["OLLAMA_BASE_URL"]

    # Inject into all Agent nodes
    for node in flow_data.get("data", {}).get("nodes", []):
        node_data = node.get("data", {})
        if node_data.get("type") == "Agent":
            template = node_data.get("node", {}).get("template", {})
            if "model" in template:
                template["model"]["value"] = model_value
            # Inject provider-specific fields (API key, URLs, project IDs)
            for field_name, field_value in provider_fields.items():
                if field_name in template:
                    template[field_name]["value"] = field_value

    return flow_data


def inject_lfx_components_path(flow_data: dict) -> dict:
    """Rewrite Directory nodes targeting bundled lfx components to an absolute path.

    The bundled LangflowAssistant flow hardcodes a relative path that only
    resolves from the monorepo root. In any packaged install the process CWD
    is different and the Directory component raises "Path ... must exist and
    be a directory.", causing the Langflow Assistant to fail with
    "An internal error occurred while executing the flow." on first use.

    This function walks the flow nodes and, for each Directory node whose
    `path` value equals LFX_COMPONENTS_PATH_SENTINEL, replaces it with the
    absolute path derived from the installed lfx package.
    """
    absolute_path = str(Path(lfx.__file__).parent / "components")

    for node in flow_data.get("data", {}).get("nodes", []):
        node_data = node.get("data", {})
        if node_data.get("type") != "Directory":
            continue
        path_field = node_data.get("node", {}).get("template", {}).get("path")
        if path_field and path_field.get("value") == LFX_COMPONENTS_PATH_SENTINEL:
            path_field["value"] = absolute_path

    return flow_data


def load_and_prepare_flow(
    flow_path: Path,
    provider: str | None,
    model_name: str | None,
    api_key_var: str | None,
    provider_vars: dict[str, str] | None = None,
) -> str:
    """Load flow file and prepare JSON with model injection."""
    flow_data = json.loads(flow_path.read_text())

    if provider and model_name:
        flow_data = inject_model_into_flow(flow_data, provider, model_name, api_key_var, provider_vars)

    flow_data = inject_lfx_components_path(flow_data)

    return json.dumps(flow_data)
