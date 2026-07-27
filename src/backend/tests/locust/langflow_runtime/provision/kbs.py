"""Knowledge-base provisioning helpers."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from tests.locust.langflow_runtime.datasets.kb_corpus import materialize_kb_corpus
from tests.locust.langflow_runtime.flows.defaults import DEFAULT_KB_NAME
from tests.locust.langflow_runtime.paths import corpus_dir
from tests.locust.langflow_runtime.provision.api import ProvisionHttp
from tests.locust.langflow_runtime.provision.state import register_resource


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


def provision_kb(
    http: ProvisionHttp,
    state: dict[str, Any],
    *,
    kb_name: str | None = None,
    materialize_corpus: bool = True,
) -> dict[str, Any]:
    """Create KB record (idempotent on 409) and optionally materialize the corpus on disk."""
    env_id = str(state["env_id"])
    resolved_name = kb_name or f"{DEFAULT_KB_NAME}_{env_id.replace('-', '_')}"
    created = http.create_knowledge_base(resolved_name)
    if materialize_corpus:
        root = corpus_root_for(env_id)
        paths = materialize_kb_corpus(root)
        ingestion = http.ingest_knowledge_base(resolved_name, [str(path) for path in paths])
        deadline = time.monotonic() + 120.0
        kb_info: dict[str, Any] | None = None
        while time.monotonic() < deadline:
            kb_info = http.get_knowledge_base(resolved_name)
            status = str((kb_info or {}).get("status") or "").lower()
            if status in {"ready", "completed", "succeeded"}:
                break
            if status in {"failed", "cancelled", "timed_out"}:
                msg = f"knowledge base {resolved_name!r} ingestion ended with status {status!r}"
                raise RuntimeError(msg)
            time.sleep(0.5)
        else:
            msg = f"knowledge base {resolved_name!r} ingestion did not become ready within 120s"
            raise TimeoutError(msg)
        state["kb"] = {
            "name": resolved_name,
            "corpus_path": str(root),
            "document_count": len(paths),
            "ingestion": ingestion,
            "status": (kb_info or {}).get("status"),
            "already_exists": bool(created.get("already_exists")),
            "env_id": env_id,
        }
    else:
        state["kb"] = {
            "name": resolved_name,
            "already_exists": bool(created.get("already_exists")),
            "env_id": env_id,
        }
    # Always register so teardown can remove suite-tagged KBs for this env.
    register_resource(state, kind="kb", resource_id=resolved_name, name=resolved_name, env_id=env_id)
    return state["kb"]
