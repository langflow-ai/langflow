"""Unit tests for MB/KB dependency resolution in the project-artifact builder.

Covers the feature's core (`_collect_dependency_refs`, `_resolve_dependencies`) and the
C1 defense-in-depth secret scrub (`_scrub_backend_config`). These are targeted unit tests
against the private helpers so they don't have to thread the full `build_project_artifact`
mock sequence.
"""

from __future__ import annotations

import io
import json
import zipfile
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from langflow.services.deployment_artifacts.builder import (
    ProjectArtifactError,
    ProjectArtifactLimits,
    _build_archive,
    _collect_dependency_refs,
    _FlowSnapshot,
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


def test_scrub_backend_config_drops_unknown_nested_values():
    cfg = {
        "mode": "cloud",
        "cloud_host": "api.trychroma.com",
        "metadata": {"auth": {"token": _RAW_SECRET}},
        "notes": ["safe-looking", {"password": _RAW_SECRET}],
    }

    scrubbed = _scrub_backend_config(cfg)

    assert scrubbed == {"mode": "cloud", "cloud_host": "api.trychroma.com"}
    assert _RAW_SECRET not in json.dumps(scrubbed)


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
        id=uuid4(),
        user_id=owner_id,
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
    backing_kb = SimpleNamespace(
        id=uuid4(),
        user_id=owner_id,
        name="testmb_backing",
        backend_type="postgres",
        backend_config={},
    )
    kb = SimpleNamespace(
        id=uuid4(),
        user_id=owner_id,
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
        owner_id=owner_id,
        payload={
            "data": {
                "nodes": [
                    {"data": {"node": {"template": {"knowledge_base": {"value": "testKb"}}}}},
                    {"data": {"node": {"template": {"memory_base": {"value": "testMb"}}}}},
                ]
            }
        },
    )

    user = SimpleNamespace(id=owner_id)
    with patch(
        "langflow.services.deployment_artifacts.builder.ensure_knowledge_base_permission",
        new_callable=AsyncMock,
    ) as authorize:
        deps = await _resolve_dependencies(
            session,
            user=user,
            owner_id=owner_id,
            workspace_id=uuid4(),
            project_id=uuid4(),
            snapshots=(snapshot,),
        )

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
    assert authorize.await_count == 2
    authorized_ids = {call.kwargs["kb_id"] for call in authorize.await_args_list}
    assert authorized_ids == {mb.id, kb.id}


@pytest.mark.asyncio
async def test_resolve_dependencies_empty_when_no_refs_and_hits_no_db():
    session = AsyncMock()
    snapshot = SimpleNamespace(payload={"data": {"nodes": []}})
    owner_id = uuid4()
    deps = await _resolve_dependencies(
        session,
        user=SimpleNamespace(id=owner_id),
        owner_id=owner_id,
        workspace_id=uuid4(),
        project_id=uuid4(),
        snapshots=(snapshot,),
    )
    assert deps == {}
    session.exec.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("dependency_type", ["knowledge_base", "memory_base"])
async def test_resolve_dependencies_fails_when_a_reference_is_missing(dependency_type):
    owner_id = uuid4()
    field_name = "knowledge_base" if dependency_type == "knowledge_base" else "memory_base"
    snapshot = SimpleNamespace(
        owner_id=owner_id,
        payload={
            "data": {
                "nodes": [{"data": {"node": {"template": {field_name: {"value": "missing"}}}}}],
            }
        },
    )
    session = AsyncMock()
    session.exec.return_value = _exec_result([])

    with pytest.raises(ProjectArtifactError, match=r"referenced .* not found"):
        await _resolve_dependencies(
            session,
            user=SimpleNamespace(id=owner_id),
            owner_id=owner_id,
            workspace_id=uuid4(),
            project_id=uuid4(),
            snapshots=(snapshot,),
        )


@pytest.mark.asyncio
async def test_resolve_dependencies_fails_when_memory_base_backing_kb_is_missing():
    owner_id = uuid4()
    mb = SimpleNamespace(
        id=uuid4(),
        user_id=owner_id,
        name="testMb",
        kb_name="missing_backing",
    )
    session = AsyncMock()
    session.exec.side_effect = [_exec_result([mb]), _exec_result([])]
    snapshot = SimpleNamespace(
        owner_id=owner_id,
        payload={
            "data": {
                "nodes": [{"data": {"node": {"template": {"memory_base": {"value": "testMb"}}}}}],
            }
        },
    )

    with pytest.raises(ProjectArtifactError, match="backing Knowledge Base was not found"):
        await _resolve_dependencies(
            session,
            user=SimpleNamespace(id=owner_id),
            owner_id=owner_id,
            workspace_id=uuid4(),
            project_id=uuid4(),
            snapshots=(snapshot,),
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("dependency_type", ["knowledge_base", "memory_base"])
async def test_resolve_dependencies_rejects_local_chroma(dependency_type):
    owner_id = uuid4()
    kb = SimpleNamespace(
        id=uuid4(),
        user_id=owner_id,
        name="localKb" if dependency_type == "knowledge_base" else "memory_backing",
        backend_type="chroma",
        backend_config={},
        model_selection={"provider": "OpenAI", "name": "text-embedding-3-small"},
        column_config=[],
    )
    if dependency_type == "knowledge_base":
        rows = [_exec_result([kb])]
        field_name = "knowledge_base"
        reference_name = "localKb"
    else:
        mb = SimpleNamespace(
            id=uuid4(),
            user_id=owner_id,
            name="testMb",
            kb_name="memory_backing",
            flow_id=uuid4(),
            embedding_model="text-embedding-3-small",
            threshold=1,
            auto_capture=True,
            preprocessing=False,
            preproc_model=None,
            preproc_instructions=None,
            preproc_kill_phrase=None,
        )
        rows = [_exec_result([mb]), _exec_result([kb])]
        field_name = "memory_base"
        reference_name = "testMb"
    session = AsyncMock()
    session.exec.side_effect = rows
    snapshot = SimpleNamespace(
        owner_id=owner_id,
        payload={
            "data": {
                "nodes": [{"data": {"node": {"template": {field_name: {"value": reference_name}}}}}],
            }
        },
    )

    with (
        patch(
            "langflow.services.deployment_artifacts.builder.ensure_knowledge_base_permission",
            new_callable=AsyncMock,
        ),
        pytest.raises(ProjectArtifactError, match="local Chroma"),
    ):
        await _resolve_dependencies(
            session,
            user=SimpleNamespace(id=owner_id),
            owner_id=owner_id,
            workspace_id=uuid4(),
            project_id=uuid4(),
            snapshots=(snapshot,),
        )


@pytest.mark.asyncio
async def test_resolve_dependencies_rejects_conflicting_same_name_across_flow_owners():
    first_owner = uuid4()
    second_owner = uuid4()
    rows = [
        SimpleNamespace(
            id=uuid4(),
            user_id=first_owner,
            name="sharedName",
            backend_type="postgres",
            backend_config={},
            model_selection={"provider": "OpenAI", "name": "model-a"},
            column_config=[],
        ),
        SimpleNamespace(
            id=uuid4(),
            user_id=second_owner,
            name="sharedName",
            backend_type="postgres",
            backend_config={},
            model_selection={"provider": "OpenAI", "name": "model-b"},
            column_config=[],
        ),
    ]
    session = AsyncMock()
    session.exec.return_value = _exec_result(rows)
    snapshots = tuple(
        SimpleNamespace(
            owner_id=owner_id,
            payload={
                "data": {
                    "nodes": [{"data": {"node": {"template": {"knowledge_base": {"value": "sharedName"}}}}}],
                }
            },
        )
        for owner_id in (first_owner, second_owner)
    )

    with (
        patch(
            "langflow.services.deployment_artifacts.builder.ensure_knowledge_base_permission",
            new_callable=AsyncMock,
        ),
        pytest.raises(ProjectArtifactError, match="ambiguous across flow owners"),
    ):
        await _resolve_dependencies(
            session,
            user=SimpleNamespace(id=first_owner),
            owner_id=first_owner,
            workspace_id=uuid4(),
            project_id=uuid4(),
            snapshots=snapshots,
        )


@pytest.mark.asyncio
async def test_resolve_dependencies_ignores_unreferenced_cross_product_rows():
    first_owner = uuid4()
    second_owner = uuid4()

    def kb(owner_id, name, model):
        return SimpleNamespace(
            id=uuid4(),
            user_id=owner_id,
            name=name,
            backend_type="postgres",
            backend_config={},
            model_selection={"provider": "OpenAI", "name": model},
            column_config=[],
        )

    session = AsyncMock()
    session.exec.return_value = _exec_result(
        [
            kb(first_owner, "firstKb", "model-a"),
            kb(second_owner, "secondKb", "model-b"),
            # Matches the query's owner/name sets but was not referenced by
            # this owner's flow and must not be packaged.
            kb(first_owner, "secondKb", "wrong-model"),
        ]
    )
    snapshots = (
        SimpleNamespace(
            owner_id=first_owner,
            payload={"data": {"nodes": [{"data": {"node": {"template": {"knowledge_base": {"value": "firstKb"}}}}}]}},
        ),
        SimpleNamespace(
            owner_id=second_owner,
            payload={"data": {"nodes": [{"data": {"node": {"template": {"knowledge_base": {"value": "secondKb"}}}}}]}},
        ),
    )

    with patch(
        "langflow.services.deployment_artifacts.builder.ensure_knowledge_base_permission",
        new_callable=AsyncMock,
    ) as authorize:
        dependencies = await _resolve_dependencies(
            session,
            user=SimpleNamespace(id=first_owner),
            owner_id=first_owner,
            workspace_id=uuid4(),
            project_id=uuid4(),
            snapshots=snapshots,
        )

    assert [item["name"] for item in dependencies["knowledgeBases"]] == ["firstKb", "secondKb"]
    assert authorize.await_count == 2


def test_build_archive_emits_dependencies_in_a_v3_manifest():
    project_id = uuid4()
    snapshot = _FlowSnapshot(
        flow_id=uuid4(),
        name="Flow",
        payload={"data": {"nodes": [], "edges": []}},
    )
    dependencies = {"knowledgeBases": [{"name": "testKb", "backendType": "postgres"}]}

    artifact = _build_archive(
        project_id=project_id,
        project_name="Project",
        snapshots=(snapshot,),
        limits=ProjectArtifactLimits(),
        dependencies=dependencies,
    )

    with zipfile.ZipFile(io.BytesIO(artifact.content)) as archive:
        manifest = json.loads(archive.read("manifest.json"))
    assert manifest["schema_version"] == 3
    assert manifest["dependencies"] == dependencies
    assert artifact.dependencies == dependencies
