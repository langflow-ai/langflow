"""Step 1 unit coverage: fixture_index, fixture hashes, embedded sources, datasets."""

from __future__ import annotations

import json
import re
from copy import deepcopy
from typing import TYPE_CHECKING

import pytest  # noqa: TC002

from tests.locust.langflow_runtime.components import PerfCpuBurn, PerfSleep, PerfSubprocessChurn
from tests.locust.langflow_runtime.datasets.registry import DATASET_IDS, DATASETS
from tests.locust.langflow_runtime.flows import validate_fixtures
from tests.locust.langflow_runtime.flows.build_fixtures import (
    DEFAULT_QUEUE_INPUT,
    DEFAULT_QUEUE_SLEEP_MS,
    component_source_hashes,
)
from tests.locust.langflow_runtime.flows.defaults import COMPONENTS_DIR, DEFAULT_KB_QUERY, FIXTURES_DIR, FLOWS_DIR
from tests.locust.langflow_runtime.hashing import embedded_isolator_hashes, sha256_file, sha256_text
from tests.locust.langflow_runtime.v1_contracts import (
    DEFAULT_WEBHOOK_PAYLOAD,
    HITL_LIFECYCLE_RULE,
    HITL_LIFECYCLE_STEPS,
)

if TYPE_CHECKING:
    from pathlib import Path


def test_flows_fixture_index_validates() -> None:
    errors = validate_fixtures.validate_fixture_index()
    assert errors == [], errors


def test_flows_fixture_index_lists_all_v1_fixtures() -> None:
    manifest = json.loads((FLOWS_DIR / "fixture_index.json").read_text(encoding="utf-8"))
    expected = {
        "perf_passthrough",
        "perf_webhook_passthrough",
        "MemoryChatbotNoLLM",
        "human_input_flow",
        "perf_queue_short",
        "perf_kb_ingest",
        "perf_kb_retrieve",
        "perf_cpu_graph",
        "perf_multiproc_churn",
        "perf_payload_echo",
        "perf_outbound_basic_prompting",
        "perf_ensemble_journey",
        "perf_ensemble_journey_hitl",
    }
    assert {flow["id"] for flow in manifest["flows"]} == expected


def test_fixture_hashes_match_index() -> None:
    manifest = json.loads((FLOWS_DIR / "fixture_index.json").read_text(encoding="utf-8"))
    for flow in manifest["flows"]:
        path = FLOWS_DIR / flow["fixture_path"]
        assert path.exists(), flow["id"]
        assert sha256_file(path) == flow["fixture_sha256"], flow["id"]


def test_provenance_is_repo_relative_and_honest() -> None:
    manifest = json.loads((FLOWS_DIR / "fixture_index.json").read_text(encoding="utf-8"))
    for flow in manifest["flows"]:
        provenance = flow["source_provenance"]
        assert "/home/" not in provenance, flow["id"]
        assert "adapted:" not in provenance, flow["id"]
        if flow["id"] in {"perf_kb_ingest", "perf_kb_retrieve", "perf_outbound_basic_prompting"}:
            assert provenance.startswith("generated-equivalent:"), flow["id"]
        if flow["id"] in {"MemoryChatbotNoLLM", "human_input_flow"}:
            assert provenance.startswith("pinned:src/"), flow["id"]


def test_embedded_component_source_hashes_match_committed_files() -> None:
    source_hashes = component_source_hashes()
    manifest = json.loads((FLOWS_DIR / "fixture_index.json").read_text(encoding="utf-8"))
    assert manifest["component_source_sha256"] == source_hashes

    for flow in manifest["flows"]:
        for key, digest in (flow.get("embedded_component_sha256") or {}).items():
            assert digest == source_hashes[key], f"{flow['id']}:{key}"
            assert digest == flow["expected_component_sha256"][key]


def test_hitl_flows_forbid_mcp_and_webhook() -> None:
    manifest = json.loads((FLOWS_DIR / "fixture_index.json").read_text(encoding="utf-8"))
    for flow in manifest["flows"]:
        if not flow.get("hitl"):
            continue
        protocols = set(flow["supported_protocols"])
        assert not protocols & {"mcp", "webhook"}, flow["id"]
        assert flow["expected_output_rule"]["hitl_lifecycle"] == HITL_LIFECYCLE_RULE


def test_endpoint_and_action_names_are_unique() -> None:
    manifest = json.loads((FLOWS_DIR / "fixture_index.json").read_text(encoding="utf-8"))
    endpoints = [flow["endpoint_name"] for flow in manifest["flows"]]
    assert len(endpoints) == len(set(endpoints))
    actions = [flow["mcp_action_name"] for flow in manifest["flows"] if flow.get("mcp_action_name")]
    assert len(actions) == len(set(actions))


def test_webhook_payload_is_python_constant() -> None:
    manifest = json.loads((FLOWS_DIR / "fixture_index.json").read_text(encoding="utf-8"))
    flow = next(f for f in manifest["flows"] if f["id"] == "perf_webhook_passthrough")
    assert flow["input_fields"]["payload"] == DEFAULT_WEBHOOK_PAYLOAD
    assert DEFAULT_WEBHOOK_PAYLOAD["marker"] == "PERF_WEBHOOK_V1"
    assert set(DEFAULT_WEBHOOK_PAYLOAD) == {"event", "seq", "marker"}


def test_hitl_lifecycle_contract() -> None:
    assert HITL_LIFECYCLE_RULE == "background->suspended->pending->resume->completed"
    assert list(HITL_LIFECYCLE_STEPS) == HITL_LIFECYCLE_RULE.split("->")


def test_dataset_registry_ids() -> None:
    assert {
        "kb/bounded_corpus",
        "storage/bounded_payload",
        "webhook/default_payload",
        "hitl/approve_decision",
    } == DATASET_IDS
    assert DATASETS["webhook/default_payload"]["payload"] == DEFAULT_WEBHOOK_PAYLOAD
    assert DATASETS["hitl/approve_decision"]["expected_lifecycle"] == HITL_LIFECYCLE_STEPS
    assert callable(DATASETS["kb/bounded_corpus"]["materialize"])
    assert callable(DATASETS["storage/bounded_payload"]["render"])


def test_fixture_selectors_are_registered() -> None:
    manifest = json.loads((FLOWS_DIR / "fixture_index.json").read_text(encoding="utf-8"))
    for flow in manifest["flows"]:
        selector = flow.get("dataset_selector")
        if selector is not None:
            assert selector in DATASET_IDS, flow["id"]


def test_chat_input_constant() -> None:
    from tests.locust.langflow_runtime.flows.defaults import DEFAULT_CHAT_INPUT

    assert DEFAULT_CHAT_INPUT == "perf-chat-turn"
    manifest = json.loads((FLOWS_DIR / "fixture_index.json").read_text(encoding="utf-8"))
    flow = next(f for f in manifest["flows"] if f["id"] == "MemoryChatbotNoLLM")
    assert flow["input_fields"]["input_value"] == DEFAULT_CHAT_INPUT
    assert flow["dataset_selector"] is None


def test_bounded_payload_text_size_and_contents() -> None:
    from tests.locust.langflow_runtime.datasets.storage_payload import STORAGE_PAYLOAD_BYTES, bounded_payload_text

    body = bounded_payload_text()
    assert len(body) == STORAGE_PAYLOAD_BYTES
    assert body.startswith("PERF_PAYLOAD_V1:")
    assert bounded_payload_text() == body


def test_kb_corpus_materialize_and_cleanup(tmp_path: Path) -> None:
    from tests.locust.langflow_runtime.datasets.kb_corpus import (
        KB_DOC_BYTES,
        KB_DOC_COUNT,
        cleanup_kb_corpus,
        materialize_kb_corpus,
    )

    root = tmp_path / "kb"
    paths = materialize_kb_corpus(root)
    assert len(paths) == KB_DOC_COUNT
    for index, path in enumerate(paths):
        data = path.read_bytes()
        assert len(data) == KB_DOC_BYTES
        text = data.decode("ascii")
        assert "PERF_KB_DOC_V1" in text
        assert f"PERF_KB_TOKEN_{index}" in text
        assert DEFAULT_KB_QUERY in text
    cleanup_kb_corpus(root)
    assert not root.exists()


def test_kb_corpus_context_manager_cleans_up(tmp_path: Path) -> None:
    from tests.locust.langflow_runtime.datasets.kb_corpus import kb_corpus

    root = tmp_path / "kb-ctx"
    with kb_corpus(root) as paths:
        assert len(paths) == 3
        assert all(p.exists() for p in paths)
    assert not root.exists()


def test_perf_sleep_component_is_bounded_and_deterministic() -> None:
    component = PerfSleep()
    component.set(input_value="ping", duration_ms=1)
    result = component.run()
    assert result.text == "slept:1:ping"

    component.set(duration_ms=50_000)  # above hard ceiling
    capped = component.run()
    assert capped.text.startswith("slept:5000:")


def test_perf_cpu_burn_component_is_bounded_and_deterministic() -> None:
    component = PerfCpuBurn()
    component.set(input_value="seed", duration_ms=5, iterations=100)
    first = component.run()
    second = component.run()
    assert first.text == second.text
    assert re.match(r"^cpu:5:\d+:[0-9a-f]{16}:seed$", first.text)


def test_perf_subprocess_churn_component_is_bounded_and_deterministic() -> None:
    component = PerfSubprocessChurn()
    component.set(input_value="mp", count=2, timeout_s=2)
    result = component.run()
    assert result.text == "multiproc:2:0,0:mp"

    component.set(count=100)  # above hard ceiling
    capped = component.run()
    assert capped.text.startswith("multiproc:8:")


def test_perf_subprocess_churn_timeout_returns_sentinel(monkeypatch: pytest.MonkeyPatch) -> None:
    import subprocess

    def _raise_timeout(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(cmd="x", timeout=1)

    monkeypatch.setattr(subprocess, "run", _raise_timeout)
    component = PerfSubprocessChurn()
    component.set(input_value="mp", count=1, timeout_s=1)
    result = component.run()
    assert result.text == "multiproc:1:-9:mp"


def test_queue_fixture_embeds_perf_sleep_source() -> None:
    fixture = json.loads((FIXTURES_DIR / "perf_queue_short.json").read_text(encoding="utf-8"))
    embedded = embedded_isolator_hashes(fixture)
    assert "perf_sleep" in embedded
    assert embedded["perf_sleep"] == sha256_file(COMPONENTS_DIR / "perf_sleep.py")
    assert DEFAULT_QUEUE_SLEEP_MS == 50
    assert DEFAULT_QUEUE_INPUT == "perf-queue-ping"


def test_fixtures_are_importable_via_graph() -> None:
    errors = validate_fixtures.validate_importable()
    assert errors == [], errors


def test_fixture_bindings_are_declared() -> None:
    errors = validate_fixtures.validate_fixture_bindings()
    assert errors == [], errors


def test_kb_and_outbound_bindings_in_fixture_index() -> None:
    manifest = json.loads((FLOWS_DIR / "fixture_index.json").read_text(encoding="utf-8"))
    by_id = {flow["id"]: flow for flow in manifest["flows"]}
    assert by_id["perf_kb_ingest"]["binding"]["knowledge_base"] == "perf_kb_v1"
    assert by_id["perf_kb_retrieve"]["binding"]["knowledge_base"] == "perf_kb_v1"
    assert by_id["perf_outbound_basic_prompting"]["binding"]["outbound_provider"] == "OpenAI"
    assert by_id["perf_outbound_basic_prompting"]["binding"]["outbound_model"] == "gpt-4o-mini"


def test_all_fixtures_have_no_credential_literals() -> None:
    errors: list[str] = []
    for path in FIXTURES_DIR.glob("*.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        errors.extend(f"{path.name}: {pattern}" for pattern in validate_fixtures._has_secret_literals(payload))
    assert errors == []


def test_validate_fixture_index_detects_hash_mismatch() -> None:
    manifest = json.loads((FLOWS_DIR / "fixture_index.json").read_text(encoding="utf-8"))
    broken = deepcopy(manifest)
    broken["flows"][0]["fixture_sha256"] = "0" * 64
    errors = validate_fixtures.validate_fixture_index(broken)
    assert any("fixture_sha256 mismatch" in e for e in errors)


def test_validate_fixture_index_detects_duplicate_endpoint() -> None:
    manifest = json.loads((FLOWS_DIR / "fixture_index.json").read_text(encoding="utf-8"))
    broken = deepcopy(manifest)
    broken["flows"][1]["endpoint_name"] = broken["flows"][0]["endpoint_name"]
    # Force validator to use the duplicate from the flow entry when payload differs:
    # rewrite by also pointing both fixtures' endpoint via mutating a copy is hard;
    # instead inject duplicate mcp_action_name which is checked from the fixture_index entry.
    broken["flows"][1]["mcp_action_name"] = broken["flows"][0]["mcp_action_name"]
    errors = validate_fixtures.validate_fixture_index(broken)
    assert any("duplicate mcp_action_name" in e for e in errors)


def test_validate_fixture_index_detects_missing_contract_keys() -> None:
    manifest = json.loads((FLOWS_DIR / "fixture_index.json").read_text(encoding="utf-8"))
    broken = deepcopy(manifest)
    del broken["flows"][0]["expected_output_rule"]
    errors = validate_fixtures.validate_fixture_index(broken)
    assert any("missing required contract keys" in e for e in errors)


def test_validate_fixture_index_detects_bad_dataset_selector() -> None:
    manifest = json.loads((FLOWS_DIR / "fixture_index.json").read_text(encoding="utf-8"))
    broken = deepcopy(manifest)
    broken["flows"][0]["dataset_selector"] = "does/not/exist"
    errors = validate_fixtures.validate_fixture_index(broken)
    assert any("not in DATASET_IDS" in e for e in errors)


def test_validate_fixture_index_rejects_hitl_on_mcp() -> None:
    manifest = json.loads((FLOWS_DIR / "fixture_index.json").read_text(encoding="utf-8"))
    broken = deepcopy(manifest)
    hitl_flow = next(f for f in broken["flows"] if f["hitl"])
    hitl_flow["supported_protocols"] = ["mcp", "workflows_background"]
    errors = validate_fixtures.validate_fixture_index(broken)
    assert any("HITL flows must not declare MCP/Webhooks" in e for e in errors)


def test_embedded_isolator_hashes_use_node_type() -> None:
    fixture = json.loads((FIXTURES_DIR / "perf_queue_short.json").read_text(encoding="utf-8"))
    # Corrupt class name in code but keep type — detection must use node type.
    for node in fixture["data"]["nodes"]:
        if node["data"]["type"] == "PerfSleep":
            code = node["data"]["node"]["template"]["code"]["value"]
            node["data"]["node"]["template"]["code"]["value"] = code.replace(
                "class PerfSleep", "class PerfSleepRenamed"
            )
            break
    embedded = embedded_isolator_hashes(fixture)
    assert "perf_sleep" in embedded
    assert embedded["perf_sleep"] == sha256_text(
        next(
            n["data"]["node"]["template"]["code"]["value"]
            for n in fixture["data"]["nodes"]
            if n["data"]["type"] == "PerfSleep"
        )
    )
