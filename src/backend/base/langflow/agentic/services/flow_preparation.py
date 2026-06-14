"""Flow data preparation and model injection."""

import copy
import json
import logging
from pathlib import Path

from lfx.base.models.model_metadata import MODEL_PROVIDER_METADATA, get_provider_param_mapping

import lfx
from langflow.agentic.helpers.assistant_workspace import resolve_assistant_fs_root

# Relative path embedded in the bundled LangflowAssistant.json flow for the
# Directory component that scans built-in lfx components. It only resolves
# correctly when the process CWD is the monorepo root, which is never the
# case for a packaged install (Langflow Desktop, `pip install langflow`,
# Docker, etc.). inject_lfx_components_path rewrites it to an absolute path
# derived from the installed lfx package at runtime.
LFX_COMPONENTS_PATH_SENTINEL = "./src/lfx/src/lfx/components/"

logger = logging.getLogger(__name__)


def get_provider_config(provider: str) -> dict | None:
    """Return provider metadata for backward compatibility with existing callers/tests."""
    return MODEL_PROVIDER_METADATA.get(provider)


def available_model_providers(global_variables: dict[str, str] | None) -> list[str]:
    """Return the model providers whose required API key is configured.

    Provider-agnostic and deterministic: for each provider in
    ``MODEL_PROVIDER_METADATA`` whose required secret variable
    (e.g. ``OPENAI_API_KEY``, ``ANTHROPIC_API_KEY``, ``GROQ_API_KEY``) has
    a non-empty value in ``global_variables`` (which the assistant builds
    from the environment), include it. Order preserved from the metadata
    so the caller can pick a stable default. No OpenAI bias — whatever the
    user actually has keys for.
    """
    gv = global_variables or {}
    providers: list[str] = []
    for provider, meta in MODEL_PROVIDER_METADATA.items():
        for var in meta.get("variables", []):
            if var.get("required") and var.get("is_secret"):
                key = var.get("variable_key")
                if key and (gv.get(key) or "").strip():
                    providers.append(provider)
                break
    return providers


def inject_model_into_flow(
    flow_data: dict,
    provider: str,
    model_name: str,
    api_key_var: str | None = None,
    provider_vars: dict[str, str] | None = None,
    *,
    overwrite_existing_model: bool = True,
) -> dict:
    """Inject model configuration into the flow's Agent component.

    Args:
        flow_data: The flow JSON as a dict
        provider: The provider name (e.g., "OpenAI", "Anthropic")
        model_name: The model name (e.g., "gpt-4o", "claude-sonnet-4-5-20250929")
        api_key_var: Optional API key variable name. If not provided, uses provider's default.
        provider_vars: Optional dict of resolved provider variables (e.g., WATSONX_URL, WATSONX_PROJECT_ID).
        overwrite_existing_model: When True (default), the model value is set on every Agent —
            correct for template preparation and for filling agents that have no model. When
            False, an Agent that ALREADY has a model set keeps it (the user's/agent's explicit
            choice is never silently swapped). In that case the credential (api_key) is still
            injected, but ONLY when the existing model's provider matches ``provider`` — so a
            same-provider run authenticates without changing the chosen model; a cross-provider
            model is left fully untouched (we don't hold that provider's verified key here).

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
        if node_data.get("type") != "Agent":
            continue
        template = node_data.get("node", {}).get("template", {})

        if "model" not in template:
            # Silent skip here means the run later fails with an
            # opaque "No model selected" — leave a diagnostic with
            # the node id so the cause is traceable.
            logger.warning(
                "assistant.inject_model.agent_missing_model_field node_id=%s provider=%s",
                node.get("id", "<unknown>"),
                provider,
            )
            continue

        existing = template["model"].get("value")
        existing_entry = (
            existing[0] if isinstance(existing, list) and existing and isinstance(existing[0], dict) else {}
        )
        existing_name = existing_entry.get("name")
        existing_provider = existing_entry.get("provider")

        if not overwrite_existing_model and existing_name:
            # Preserve the user's/agent's explicit model — NEVER silently swap
            # it for our verified model. When it's the SAME provider, REBUILD a
            # COMPLETE value carrying the user's model NAME but the full,
            # well-formed metadata/icon (the value the agent set via
            # configure_component is often a bare ``{provider, name}`` with no
            # metadata, which can make the run fail to resolve the model). Also
            # top up the credential so the run authenticates. Cross-provider, we
            # don't hold that provider's verified key, so leave it untouched.
            if existing_provider == provider:
                template["model"]["value"] = [{**model_value[0], "name": existing_name}]
                for field_name, field_value in provider_fields.items():
                    if field_name in template:
                        template[field_name]["value"] = field_value
            continue

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


def inject_assistant_fs_root(flow_data: dict) -> dict:
    """Replace empty FileSystemTool.root_path with the resolved sandbox path.

    The shipped LangflowAssistant flow leaves FileSystemTool.root_path empty
    on purpose so the path can be resolved per-host at runtime (see
    helpers.assistant_workspace.resolve_assistant_fs_root). Hardcoding any
    value in the JSON would break portability across macOS, Linux, Windows
    and Docker.

    Only nodes whose root_path value is empty/whitespace are rewritten — an
    operator's explicit override is preserved.

    When ``resolve_assistant_fs_root`` returns ``None`` (PR #13031's per-user
    isolation module is present), this function is a no-op: any injected
    value would be misread as a relative sub_path under the user's namespace
    and break the per-user boundary. The component handles its own resolution.
    """
    resolved_path = resolve_assistant_fs_root()
    if resolved_path is None:
        return flow_data
    resolved = str(resolved_path)

    for node in flow_data.get("data", {}).get("nodes", []):
        node_data = node.get("data", {})
        if node_data.get("type") != "FileSystemTool":
            continue
        root_field = node_data.get("node", {}).get("template", {}).get("root_path")
        if not root_field:
            continue
        current = root_field.get("value", "")
        if isinstance(current, str) and current.strip():
            continue
        root_field["value"] = resolved

    return flow_data


# Parsed bundled-flow templates, keyed by path → ((mtime_ns, size),
# parsed dict). The raw template is stable per file; re-reading +
# json.loads on every request (and x4 on validation retries) was
# blocking the event loop. A genuine file change (mtime/size) re-parses.
_FLOW_TEMPLATE_CACHE: dict[str, tuple[tuple[int, int], dict]] = {}


def _load_flow_template(flow_path: Path) -> dict:
    """Return a fresh deep copy of the parsed flow (cached by path+stat)."""
    key = str(flow_path)
    try:
        stat = flow_path.stat()
        sig = (stat.st_mtime_ns, stat.st_size)
    except OSError:
        # Can't stat → don't cache; fall back to a direct read.
        return json.loads(flow_path.read_text(encoding="utf-8"))

    cached = _FLOW_TEMPLATE_CACHE.get(key)
    if cached is None or cached[0] != sig:
        parsed = json.loads(flow_path.read_text(encoding="utf-8"))
        _FLOW_TEMPLATE_CACHE[key] = (sig, parsed)
        cached = (sig, parsed)
    # Deep copy so per-request model injection never mutates the cache.
    return copy.deepcopy(cached[1])


def load_and_prepare_flow(
    flow_path: Path,
    provider: str | None,
    model_name: str | None,
    api_key_var: str | None,
    provider_vars: dict[str, str] | None = None,
) -> str:
    """Load flow file and prepare JSON with model injection."""
    flow_data = _load_flow_template(flow_path)

    if provider and model_name:
        flow_data = inject_model_into_flow(flow_data, provider, model_name, api_key_var, provider_vars)

    flow_data = inject_lfx_components_path(flow_data)
    flow_data = inject_assistant_fs_root(flow_data)

    return json.dumps(flow_data)
