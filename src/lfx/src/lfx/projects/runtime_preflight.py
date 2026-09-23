"""Shared runtime and resource checks for Harness candidate hosts."""

from importlib.metadata import PackageNotFoundError, version

from packaging.requirements import Requirement


def preflight_candidate(candidate, *, no_env_fallback=False, capabilities=()):
    """Fail before loading component code if this host cannot satisfy the candidate."""
    from lfx.base.models.model_metadata import get_provider_param_mapping
    from lfx.base.models.unified_models.class_registry import get_model_class
    from lfx.integrations.models import ConnectionRef
    from lfx.utils.env_var_security import safe_getenv
    from lfx.utils.flow_validation import validate_flow_for_current_settings

    manifest = candidate.manifest
    runtime = manifest["runtime"]
    if set(runtime) != {"lfx", "packages"} or runtime["lfx"] != version("lfx"):
        msg = "Candidate requires a different LFX runtime version. Build a compatible runtime before mounting."
        raise ValueError(msg)
    requirements = manifest["requirements"]
    unsupported = (
        sorted(set(requirements["capabilities"]) - set(capabilities)) + requirements["services"] + requirements["files"]
    )
    if unsupported:
        msg = "Candidate host cannot provision these requirements: " + ", ".join(unsupported)
        raise ValueError(msg)
    for specifier in runtime["packages"]:
        required = Requirement(specifier)
        try:
            installed = version(required.name)
        except PackageNotFoundError:
            installed = None
        if not installed or installed not in required.specifier:
            msg = f"Candidate requires runtime package: {specifier}"
            raise ValueError(msg)
    variables = set(requirements["variables"])
    for provider in requirements["providers"]:
        mapping = get_provider_param_mapping(provider)
        if not mapping.get("model_class"):
            msg = f"Candidate model provider is unavailable: {provider}"
            raise ValueError(msg)
        try:
            get_model_class(mapping["model_class"])
        except ImportError as exc:
            msg = f"Candidate provider package is unavailable: {provider}. {exc}"
            raise ValueError(msg) from exc
    for handle in requirements["connections"]:
        variables.add(ConnectionRef.parse(handle).env_key())
    missing = sorted(name for name in variables if no_env_fallback or not safe_getenv(name))
    if missing:
        msg = "Missing destination variables/connections: " + ", ".join(missing)
        raise ValueError(msg)
    for definition in candidate.definitions.values():
        validate_flow_for_current_settings(definition["data"])
