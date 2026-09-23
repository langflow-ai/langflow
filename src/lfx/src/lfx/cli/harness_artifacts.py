"""Mount a verified Harness candidate on the existing standalone workflow host."""

from importlib.metadata import PackageNotFoundError, version

from packaging.requirements import Requirement

from lfx.projects.runtime_artifacts import read_candidate


def preflight_candidate(candidate, *, no_env_fallback=False):
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
    unsupported = requirements["capabilities"] + requirements["services"] + requirements["files"]
    if unsupported:
        msg = "Standalone candidate host cannot provision these requirements: " + ", ".join(unsupported)
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


def candidate_graph(candidate, *, no_env_fallback=False):
    from lfx.graph import Graph

    preflight_candidate(candidate, no_env_fallback=no_env_fallback)
    identity = candidate.manifest["entrypoints"][0]
    entrypoint = None
    # Prepare every definition before making the entrypoint available. Missing
    # component imports in a private tool must not first fail after an LLM call.
    for source in candidate.definitions.values():
        graph = Graph.from_payload(source["data"], flow_id=source["id"], flow_name=source["name"])
        candidate.bind(graph)
        graph.prepare()
        if source["id"] == identity:
            entrypoint = graph
    if entrypoint is None:
        msg = "The candidate entrypoint is missing."
        raise ValueError(msg)
    return entrypoint


def mount_candidate(registry, content: bytes, *, expected_digest: str | None = None, relative_path="<candidate>"):
    """Only the declared entrypoint is discoverable; nested flows stay private.

    Candidate mounts are immutable startup configuration, not mutable uploaded
    flow-store entries. Every worker loads the same archive via STARTUP_PATHS.
    """
    from lfx.cli.serve_app import FlowMeta

    candidate = read_candidate(content, expected_digest=expected_digest)
    graph = candidate_graph(candidate, no_env_fallback=registry.no_env_fallback)
    meta = FlowMeta(
        id=str(graph.flow_id),
        relative_path=relative_path,
        title=graph.flow_name,
        description=f"Harness candidate sha256:{candidate.digest}",
    )
    registry.add(graph, meta)
    return candidate
