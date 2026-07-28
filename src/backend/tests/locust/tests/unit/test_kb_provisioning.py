"""Unit tests for performance-suite knowledge-base provisioning."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import httpx
import pytest

from tests.locust.langflow_runtime.datasets.kb_corpus import kb_ingest_document
from tests.locust.langflow_runtime.flows.defaults import DEFAULT_KB_DOC_PREFIX, FIXTURES_DIR
from tests.locust.langflow_runtime.provision import kbs
from tests.locust.langflow_runtime.provision.api import ProvisionHttp


@pytest.mark.parametrize(
    ("fixture_name", "expected_modes"),
    [
        ("perf_kb_ingest.json", {"Ingest"}),
        ("perf_kb_retrieve.json", {"Retrieve"}),
        ("perf_ensemble_journey.json", {"Ingest", "Retrieve"}),
        ("perf_ensemble_journey_hitl.json", {"Ingest", "Retrieve"}),
    ],
)
def test_kb_fixtures_keep_real_knowledge_and_stub_only_embeddings(fixture_name: str, expected_modes: set[str]) -> None:
    payload = json.loads((FIXTURES_DIR / fixture_name).read_text(encoding="utf-8"))
    knowledge_nodes = [node for node in payload["data"]["nodes"] if node["data"].get("type") == "Knowledge"]

    assert {node["data"]["node"]["template"]["mode"]["value"] for node in knowledge_nodes} == expected_modes
    for node in knowledge_nodes:
        source = node["data"]["node"]["template"]["code"]["value"]
        assert "PERF_MOCK_EMBEDDING" in source
        assert "create_backend(" in source
        assert "similarity_search(" in source

    legacy_types = {"KnowledgeIngestion", "KnowledgeBase"}
    assert not legacy_types & {node["data"].get("type") for node in payload["data"]["nodes"]}


def test_create_knowledge_base_uses_catalog_metadata_for_the_mocked_edge() -> None:
    observed: dict[str, Any] = {}

    def handle(request: httpx.Request) -> httpx.Response:
        observed.update(json.loads(request.content))
        return httpx.Response(201, json={"name": "perf-kb"})

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        http = ProvisionHttp("http://example.test", client=client)
        http.create_knowledge_base(
            "perf-kb",
            embedding_provider=kbs.KB_METADATA_PROVIDER,
            embedding_model=kbs.KB_METADATA_MODEL,
            model_selection=kbs.KB_METADATA_SELECTION,
        )

    assert observed["backend_type"] == "chroma"
    assert observed["embedding_provider"] == "HuggingFace"
    assert observed["embedding_model"] == "sentence-transformers/all-MiniLM-L6-v2"
    assert observed["model_selection"]["metadata"]["embedding_class"] == "HuggingFaceEmbeddings"


def test_provision_kb_registers_real_chroma_record_without_backend_model_ingestion(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    corpus_path = tmp_path / "document.txt"
    corpus_path.write_text("synthetic corpus", encoding="utf-8")
    monkeypatch.setattr(kbs, "corpus_root_for", lambda _env_id: tmp_path)
    monkeypatch.setattr(kbs, "materialize_kb_corpus", lambda _root: [corpus_path])

    class FakeHttp:
        def create_knowledge_base(self, *_args: Any, **kwargs: Any) -> dict[str, Any]:
            assert kwargs == {
                "embedding_provider": kbs.KB_METADATA_PROVIDER,
                "embedding_model": kbs.KB_METADATA_MODEL,
                "model_selection": kbs.KB_METADATA_SELECTION,
            }
            return {"name": "perf_kb_perf_unit"}

    state: dict[str, Any] = {"env_id": "perf-unit", "resources": [], "teardown_order": []}
    result = kbs.provision_kb(cast("ProvisionHttp", FakeHttp()), state)

    assert result["embedding_mode"] == "deterministic"
    assert result["vector_store"] == "chroma"
    assert result["status"] == "pending_flow_seed"
    assert state["teardown_order"] == ["kb:perf_kb_perf_unit"]
    assert state["resources"] == [
        {
            "kind": "kb",
            "id": "perf_kb_perf_unit",
            "name": "perf_kb_perf_unit",
            "env_id": "perf-unit",
        }
    ]


def test_kb_selection_adds_the_seed_flow_dependency() -> None:
    index = {
        "perf_kb_ingest": {"required_environment_features": ["knowledge_base"]},
        "perf_kb_retrieve": {"required_environment_features": ["knowledge_base"]},
        "perf_passthrough": {"required_environment_features": []},
    }
    assert kbs.with_kb_seed_dependency(["perf_kb_retrieve"], index) == [
        "perf_kb_retrieve",
        "perf_kb_ingest",
    ]
    assert kbs.with_kb_seed_dependency(["perf_passthrough"], index) == ["perf_passthrough"]


def test_kb_ingest_documents_are_unique_per_turn_and_keep_the_marker() -> None:
    first = kb_ingest_document("perf-user-1", 1)
    second = kb_ingest_document("perf-user-1", 2)

    assert first != second
    assert DEFAULT_KB_DOC_PREFIX in first
    assert "session=perf-user-1" in first


def test_seed_kb_runs_real_ingest_flow_for_each_document(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    for index in range(2):
        (tmp_path / f"doc_{index:02d}.txt").write_text(f"document-{index}", encoding="utf-8")

    calls: list[dict[str, str]] = []

    class FakeWorkflowsClient:
        def __init__(self, **_kwargs: Any) -> None:
            pass

        def run_sync(self, **kwargs: str) -> dict[str, Any]:
            calls.append(kwargs)
            return {"outputs": []}

    class FakeHttp:
        def api_client(self, *, api_key: str):
            assert api_key == "suite-key"  # pragma: allowlist secret
            return object()

        def get_knowledge_base(self, name: str) -> dict[str, Any]:
            assert name == "perf_kb_perf_unit"
            return {"name": name, "status": "ready"}

    monkeypatch.setattr(kbs, "WorkflowsClient", FakeWorkflowsClient)
    state: dict[str, Any] = {
        "env_id": "perf-unit",
        "api_key": "suite-key",  # pragma: allowlist secret
        "kb": {"name": "perf_kb_perf_unit", "corpus_path": str(tmp_path)},
        "flows": {"perf_kb_ingest": {"flow_id": "flow-1"}},
    }

    result = kbs.seed_kb_via_flow(cast("ProvisionHttp", FakeHttp()), state)

    assert [call["input_value"] for call in calls] == ["document-0", "document-1"]
    assert all(call["flow_id"] == "flow-1" for call in calls)
    assert result["document_count"] == 2
    assert state["flags"]["kb_seeded"] is True
    assert state["kb"]["status"] == "ready"
