"""Mount a verified Harness candidate on the existing standalone workflow host."""

from lfx.projects.runtime_artifacts import read_candidate
from lfx.projects.runtime_preflight import preflight_candidate


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
