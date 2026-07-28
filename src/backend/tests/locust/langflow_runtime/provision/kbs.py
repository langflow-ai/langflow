"""Knowledge-base provisioning helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

from tests.locust.langflow_runtime.clients.workflows import WorkflowsClient
from tests.locust.langflow_runtime.datasets.kb_corpus import materialize_kb_corpus
from tests.locust.langflow_runtime.flows.defaults import DEFAULT_KB_NAME
from tests.locust.langflow_runtime.paths import corpus_dir
from tests.locust.langflow_runtime.provision.api import ProvisionHttp
from tests.locust.langflow_runtime.provision.state import register_resource

KB_SEED_FLOW_ID = "perf_kb_ingest"
# The KB API requires catalog-backed metadata when it creates the record. The
# saved perf Knowledge components replace get_embeddings at execution time, so
# this model is metadata only and is never loaded or called by stubbed KB runs.
KB_METADATA_PROVIDER = "HuggingFace"
KB_METADATA_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
KB_METADATA_SELECTION = {
    "name": KB_METADATA_MODEL,
    "provider": KB_METADATA_PROVIDER,
    "metadata": {
        "embedding_class": "HuggingFaceEmbeddings",
        "param_mapping": {"model_name": "model"},
    },
}


def corpus_root_for(env_id: str, *, state_dir: Path | None = None) -> Path:
    """Return the on-disk corpus root for ``env_id`` (outside the git checkout).

    ``state_dir`` is accepted for backward compatibility with tests that pass a
    temp directory; when set, corpus lives under ``{state_dir}/corpus/{env_id}``.
    """
    if state_dir is not None:
        return state_dir / "corpus" / env_id
    return corpus_dir(env_id)


def needs_kb(flow_ids: list[str], index_by_id: dict[str, dict[str, Any]]) -> bool:
    for fid in flow_ids:
        entry = index_by_id.get(fid) or {}
        binding = entry.get("binding") or {}
        features = entry.get("required_environment_features") or []
        if binding.get("knowledge_base") or "knowledge_base" in features:
            return True
    return False


def with_kb_seed_dependency(flow_ids: list[str], index_by_id: dict[str, dict[str, Any]]) -> list[str]:
    """Include the deterministic ingest flow whenever selected fixtures need a seeded KB."""
    resolved = list(flow_ids)
    if needs_kb(resolved, index_by_id) and KB_SEED_FLOW_ID not in resolved:
        if KB_SEED_FLOW_ID not in index_by_id:
            msg = f"KB seed fixture {KB_SEED_FLOW_ID!r} is missing from fixture_index"
            raise RuntimeError(msg)
        resolved.append(KB_SEED_FLOW_ID)
    return resolved


def provision_kb(
    http: ProvisionHttp,
    state: dict[str, Any],
    *,
    kb_name: str | None = None,
    materialize_corpus: bool = True,
) -> dict[str, Any]:
    """Create a real Chroma-backed KB record and prepare its deterministic seed corpus."""
    env_id = str(state["env_id"])
    resolved_name = kb_name or f"{DEFAULT_KB_NAME}_{env_id.replace('-', '_')}"
    created = http.create_knowledge_base(
        resolved_name,
        embedding_provider=KB_METADATA_PROVIDER,
        embedding_model=KB_METADATA_MODEL,
        model_selection=KB_METADATA_SELECTION,
    )
    state["kb"] = {
        "name": resolved_name,
        "embedding_mode": "deterministic",
        "embedding_provider": KB_METADATA_PROVIDER,
        "embedding_model": KB_METADATA_MODEL,
        "vector_store": "chroma",
        "already_exists": bool(created.get("already_exists")),
        "env_id": env_id,
    }
    register_resource(state, kind="kb", resource_id=resolved_name, name=resolved_name, env_id=env_id)
    if materialize_corpus:
        root = corpus_root_for(env_id)
        paths = materialize_kb_corpus(root)
        state["kb"].update(
            {
                "corpus_path": str(root),
                "document_count": len(paths),
                "status": "pending_flow_seed",
            }
        )
    return state["kb"]


def seed_kb_via_flow(http: ProvisionHttp, state: dict[str, Any]) -> dict[str, Any]:
    """Ingest the prepared corpus through real Knowledge/Chroma code with fake vectors only."""
    kb = state.get("kb") or {}
    flow = (state.get("flows") or {}).get(KB_SEED_FLOW_ID)
    api_key = state.get("api_key")
    corpus_path = kb.get("corpus_path")
    if not flow or not api_key or not corpus_path:
        msg = "KB seeding requires the perf_kb_ingest flow, suite API key, and materialized corpus"
        raise RuntimeError(msg)

    paths = sorted(Path(str(corpus_path)).glob("doc_*.txt"))
    if not paths:
        msg = f"KB seed corpus is empty: {corpus_path}"
        raise RuntimeError(msg)

    client = WorkflowsClient(
        api=http.api_client(api_key=str(api_key)),
        workload="kb_seed",
        flow_class="kb_ingest",
    )
    session_id = f"perf-kb-seed-{state['env_id']}-{uuid4().hex[:8]}"
    for path in paths:
        client.run_sync(
            flow_id=str(flow["flow_id"]),
            input_value=path.read_text(encoding="utf-8"),
            session_id=session_id,
        )

    kb_info = http.get_knowledge_base(str(kb["name"])) or {}
    status = str(kb_info.get("status") or "").lower()
    if status not in {"ready", "completed", "succeeded"}:
        msg = f"knowledge base {kb['name']!r} was not ready after deterministic flow seeding (status={status!r})"
        raise RuntimeError(msg)

    seed = {
        "seeded": True,
        "flow_id": str(flow["flow_id"]),
        "document_count": len(paths),
        "session_id": session_id,
    }
    kb["seed"] = seed
    kb["status"] = kb_info.get("status")
    state.setdefault("flags", {})["kb_seeded"] = True
    return seed
