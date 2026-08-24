"""Unit tests for MB/KB dependency resolution in the project-artifact builder.

Covers the feature's core (`_collect_dependency_refs`, `_resolve_dependencies`) and the
C1 defense-in-depth secret scrub (`_scrub_backend_config`). These are targeted unit tests
against the private helpers so they don't have to thread the full `build_project_artifact`
mock sequence.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from langflow.services.deployment_artifacts.builder import (
    _collect_dependency_refs,
    _resolve_dependencies,
    _scrub_backend_config,
)

# Fake, non-functional fixture values (not real credentials): one variable-NAME pointer
# that must survive scrubbing, and one raw secret that must be stripped.
_KEY_VAR_NAME = "CHROMA_API_KEY"  # pragma: allowlist secret
_RAW_SECRET = "sk-RAWLEAK"  # noqa: S105  # pragma: allowlist secret


def _exec_result(rows):
    result = MagicMock()
    result.all.return_value = rows
    return result


# --- C1: backend_config secret scrub -----------------------------------------


def test_scrub_backend_config_keeps_routing_and_variable_name_pointers():
    cfg = {"mode": "cloud", "api_key_variable": _KEY_VAR_NAME, "tenant_variable": "CHROMA_TENANT"}
    # variable-NAME pointers + routing are non-secret and must survive verbatim
    assert _scrub_backend_config(cfg) == cfg


@pytest.mark.parametrize(
    "secret_key",
    ["api_key", "apikey", "password", "auth_token", "connection_string", "db_secret", "private_key"],
)
def test_scrub_backend_config_strips_inlined_raw_secret(secret_key):
    scrubbed = _scrub_backend_config({"mode": "cloud", secret_key: _RAW_SECRET})
    assert scrubbed == {"mode": "cloud"}
    assert _RAW_SECRET not in json.dumps(scrubbed)


def test_scrub_backend_config_handles_non_dict():
    assert _scrub_backend_config(None) == {}
    assert _scrub_backend_config("not-a-dict") == {}


# --- reference collection -----------------------------------------------------


def test_collect_dependency_refs_reads_kb_mb_and_inline_kb():
    payload = {
        "data": {
            "nodes": [
                {"data": {"node": {"template": {"knowledge_base": {"value": "testKb"}}}}},
                {"data": {"node": {"template": {"memory_base": {"value": "testMb"}}}}},
                {"data": {"node": {"template": {"new_kb_name": {"value": "inlineKb"}}}}},
                {"data": {"node": {"template": {"unrelated": {"value": "ignore-me"}}}}},
            ]
        }
    }
    mb_names, kb_names = _collect_dependency_refs(payload)
    assert mb_names == {"testMb"}
    assert kb_names == {"testKb", "inlineKb"}


def test_collect_dependency_refs_tolerates_malformed_payload():
    assert _collect_dependency_refs({}) == (set(), set())
    assert _collect_dependency_refs({"data": {"nodes": [None, {}, {"data": None}]}}) == (set(), set())


# --- full resolution (shape + backing-KB dedup + secret strip) ----------------


@pytest.mark.asyncio
async def test_resolve_dependencies_shapes_specs_and_strips_secret():
    owner_id = uuid4()
    flow_id = uuid4()

    mb = SimpleNamespace(
        name="testMb",
        kb_name="testmb_backing",
        flow_id=flow_id,
        embedding_model="nomic-embed-text",
        threshold=1,
        auto_capture=True,
        preprocessing=False,
        preproc_model=None,
        preproc_instructions=None,
        preproc_kill_phrase=None,
    )
    backing_kb = SimpleNamespace(name="testmb_backing", backend_type="postgres", backend_config={})
    kb = SimpleNamespace(
        name="testKb",
        backend_type="chroma",
        # a raw api_key inlined next to the legitimate variable-name pointer
        backend_config={"mode": "cloud", "api_key_variable": _KEY_VAR_NAME, "api_key": _RAW_SECRET},
        model_selection={"provider": "Ollama", "name": "nomic-embed-text"},
        column_config=[{"column_name": "text", "vectorize": True, "identifier": True}],
    )

    session = AsyncMock()
    # exec order in _resolve_dependencies: MemoryBase -> backing KB -> KB
    session.exec.side_effect = [_exec_result([mb]), _exec_result([backing_kb]), _exec_result([kb])]

    snapshot = SimpleNamespace(
        payload={
            "data": {
                "nodes": [
                    {"data": {"node": {"template": {"knowledge_base": {"value": "testKb"}}}}},
                    {"data": {"node": {"template": {"memory_base": {"value": "testMb"}}}}},
                ]
            }
        }
    )

    deps = await _resolve_dependencies(session, owner_id=owner_id, snapshots=(snapshot,))

    # MB is shaped and its backend is read from the backing KB
    assert [m["name"] for m in deps["memoryBases"]] == ["testMb"]
    assert deps["memoryBases"][0]["backendType"] == "postgres"
    assert deps["memoryBases"][0]["flowId"] == str(flow_id)
    # backing KB is NOT emitted as its own KB
    assert [k["name"] for k in deps["knowledgeBases"]] == ["testKb"]

    kb_item = deps["knowledgeBases"][0]
    assert kb_item["backendType"] == "chroma"
    assert kb_item["embeddingProvider"] == "Ollama"
    # C1: raw secret stripped; routing + variable-name pointer preserved
    assert kb_item["backendConfig"] == {"mode": "cloud", "api_key_variable": _KEY_VAR_NAME}
    assert _RAW_SECRET not in json.dumps(deps)


@pytest.mark.asyncio
async def test_resolve_dependencies_empty_when_no_refs_and_hits_no_db():
    session = AsyncMock()
    snapshot = SimpleNamespace(payload={"data": {"nodes": []}})
    deps = await _resolve_dependencies(session, owner_id=uuid4(), snapshots=(snapshot,))
    assert deps == {}
    session.exec.assert_not_awaited()
