"""Deterministic embedding stub and Natural stubbed offline contracts."""

from __future__ import annotations

import json

from tests.locust.langflow_runtime.components.perf_deterministic_embeddings import DeterministicEmbeddings
from tests.locust.langflow_runtime.flows.defaults import FIXTURES_DIR


def test_deterministic_embeddings_are_stable() -> None:
    emb = DeterministicEmbeddings(8)
    assert emb.embed_query("PERF_KB_QUERY_KNOWN") == emb.embed_query("PERF_KB_QUERY_KNOWN")
    assert emb.embed_documents(["a", "b"])[0] == emb.embed_query("a")


def test_stubbed_rag_fixture_patches_get_embeddings() -> None:
    path = FIXTURES_DIR / "natural_vector_store_rag__external_stubbed.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    knowledge_codes = []
    for node in payload["data"]["nodes"]:
        if (node.get("data") or {}).get("type") == "Knowledge":
            code = node["data"]["node"]["template"]["code"]["value"]
            knowledge_codes.append(code)
    assert knowledge_codes
    assert any("perf suite stub: deterministic embeddings" in code for code in knowledge_codes)


def test_stubbed_basic_prompting_embeds_mock_language_model() -> None:
    path = FIXTURES_DIR / "natural_basic_prompting__external_stubbed.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    codes = [
        node["data"]["node"]["template"]["code"]["value"]
        for node in payload["data"]["nodes"]
        if (node.get("data") or {}).get("type") == "LanguageModelComponent"
    ]
    assert codes
    assert any("Stub Language Model for Natural suite stubbed runs." in code for code in codes)
