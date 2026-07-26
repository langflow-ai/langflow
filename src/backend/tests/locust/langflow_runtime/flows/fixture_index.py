"""Author flows/fixture_index.json from built fixture paths.

Constructs the committed index (ids, hashes, bindings, dataset selectors)
during ``build_fixtures`` runs. Consumers read ``fixture_index.json`` via
``validate_fixtures`` and ``tests/locust/tests/integration/fixture_access``.
"""

from __future__ import annotations

import json
from copy import deepcopy
from typing import TYPE_CHECKING, Any

from tests.locust.langflow_runtime.flows.defaults import (
    COMPONENTS_DIR,
    DATA_REL,
    DEFAULT_CHAT_INPUT,
    DEFAULT_CPU_DURATION_MS,
    DEFAULT_CPU_ITERATIONS,
    DEFAULT_DISK_IO_SIZE_BYTES,
    DEFAULT_KB_DOC_PREFIX,
    DEFAULT_KB_NAME,
    DEFAULT_KB_QUERY,
    DEFAULT_MULTIPROC_COUNT,
    DEFAULT_MULTIPROC_DURATION_MS,
    DEFAULT_MULTIPROC_WORKING_SET_BYTES,
    DEFAULT_OUTBOUND_MODEL,
    DEFAULT_OUTBOUND_PROMPT,
    DEFAULT_OUTBOUND_PROVIDER,
    DEFAULT_PASSTHROUGH_INPUT,
    DEFAULT_PAYLOAD_FILENAME,
    DEFAULT_QUEUE_INPUT,
    DEFAULT_QUEUE_SLEEP_MS,
    DEFAULT_WEBHOOK_PAYLOAD,
    FIXTURE_INDEX_VERSION,
    FLOWS_DIR,
    HITL_LIFECYCLE_RULE,
    STARTERS_1_6_0_REL,
)
from tests.locust.langflow_runtime.hashing import component_source_hashes, embedded_isolator_hashes, sha256_file

if TYPE_CHECKING:
    from pathlib import Path


def _node_types(payload: dict[str, Any]) -> list[str]:
    return sorted({node.get("data", {}).get("type", "") for node in payload.get("data", {}).get("nodes", [])})


def flow_specs() -> list[dict[str, Any]]:
    return [
        {
            "id": "perf_passthrough",
            "fixture": "perf_passthrough.json",
            "stress_category": "protocol_calibration",
            "source_provenance": "generated:ChatInput->ChatOutput(should_store_message=false)",
            "supported_protocols": ["mcp", "workflows_sync", "workflows_stream", "workflows_background"],
            "supported_modes": ["sync", "stream", "background"],
            "input_fields": {"input_value": DEFAULT_PASSTHROUGH_INPUT},
            "expected_output_rule": {"contains": DEFAULT_PASSTHROUGH_INPUT},
            "mcp_action_name": "perf_passthrough",
            "required_environment_features": [],
            "dataset_selector": None,
            "webhook_copy_count": 0,
            "hitl": False,
            "stores_chat_history": False,
        },
        {
            "id": "perf_webhook_passthrough",
            "fixture": "perf_webhook_passthrough.json",
            "stress_category": "webhook",
            "source_provenance": "generated:Webhook->ChatOutput",
            "supported_protocols": ["webhook"],
            "supported_modes": ["webhook"],
            "input_fields": {"payload": DEFAULT_WEBHOOK_PAYLOAD},
            "expected_output_rule": {"webhook_n_accept_n_complete": True},
            "mcp_action_name": None,
            "required_environment_features": ["webhook_sse"],
            "dataset_selector": "webhook/default_payload",
            "webhook_copy_count": 1,
            "hitl": False,
            "stores_chat_history": False,
        },
        {
            "id": "MemoryChatbotNoLLM",
            "fixture": "MemoryChatbotNoLLM.json",
            "stress_category": "chat_db",
            "source_provenance": f"pinned:{DATA_REL}/MemoryChatbotNoLLM.json",
            "supported_protocols": ["mcp", "workflows_sync", "workflows_stream", "workflows_background"],
            "supported_modes": ["sync", "stream", "background"],
            "input_fields": {"input_value": DEFAULT_CHAT_INPUT},
            "expected_output_rule": {"chat_message_persisted": True},
            "mcp_action_name": "MemoryChatbotNoLLM",
            "required_environment_features": ["message_store"],
            "dataset_selector": None,
            "webhook_copy_count": 0,
            "hitl": False,
            "stores_chat_history": True,
        },
        {
            "id": "human_input_flow",
            "fixture": "human_input_flow.json",
            "stress_category": "hitl",
            "source_provenance": f"pinned:{DATA_REL}/human_input_flow.json",
            "supported_protocols": ["workflows_background"],
            "supported_modes": ["background"],
            "input_fields": {"prompt": "{{hitl.prompt}}"},
            "expected_output_rule": {"hitl_lifecycle": HITL_LIFECYCLE_RULE},
            "mcp_action_name": None,
            "required_environment_features": ["workflows_background", "hitl"],
            "dataset_selector": "hitl/approve_decision",
            "webhook_copy_count": 0,
            "hitl": True,
            "stores_chat_history": False,
        },
        {
            "id": "perf_queue_short",
            "fixture": "perf_queue_short.json",
            "stress_category": "queue",
            "source_provenance": "generated:ChatInput->PerfSleep->ChatOutput",
            "supported_protocols": ["workflows_background"],
            "supported_modes": ["background"],
            "input_fields": {"input_value": DEFAULT_QUEUE_INPUT, "duration_ms": DEFAULT_QUEUE_SLEEP_MS},
            "expected_output_rule": {"matches_regex": rf"^slept:{DEFAULT_QUEUE_SLEEP_MS}:{DEFAULT_QUEUE_INPUT}$"},
            "mcp_action_name": "perf_queue_short",
            "required_environment_features": ["workflows_background"],
            "dataset_selector": None,
            "webhook_copy_count": 0,
            "hitl": False,
            "stores_chat_history": False,
            "embedded_components": ["perf_sleep"],
        },
        {
            "id": "perf_kb_ingest",
            "fixture": "perf_kb_ingest.json",
            "stress_category": "kb_ingest",
            "source_provenance": (
                f"generated-equivalent:{STARTERS_1_6_0_REL}/Knowledge Ingestion.json "
                "(URL->TextInput deterministic document)"
            ),
            "supported_protocols": ["mcp", "workflows_sync", "workflows_stream", "workflows_background"],
            "supported_modes": ["sync", "stream", "background"],
            "input_fields": {"input_value": f"{DEFAULT_KB_DOC_PREFIX}"},
            "expected_output_rule": {"kb_ingest_terminal": True, "contains": DEFAULT_KB_DOC_PREFIX},
            "mcp_action_name": "perf_kb_ingest",
            "required_environment_features": ["knowledge_base", "embeddings"],
            "dataset_selector": "kb/bounded_corpus",
            "binding": {"knowledge_base": DEFAULT_KB_NAME},
            "webhook_copy_count": 0,
            "hitl": False,
            "stores_chat_history": False,
        },
        {
            "id": "perf_kb_retrieve",
            "fixture": "perf_kb_retrieve.json",
            "stress_category": "kb_retrieve",
            "source_provenance": f"generated-equivalent:{STARTERS_1_6_0_REL}/Knowledge Retrieval.json",
            "supported_protocols": ["mcp", "workflows_sync", "workflows_stream", "workflows_background"],
            "supported_modes": ["sync", "stream", "background"],
            "input_fields": {"input_value": DEFAULT_KB_QUERY},
            "expected_output_rule": {"known_query": DEFAULT_KB_QUERY, "retrieval_hits_min": 1},
            "mcp_action_name": "perf_kb_retrieve",
            "required_environment_features": ["knowledge_base", "embeddings"],
            "dataset_selector": "kb/bounded_corpus",
            "binding": {"knowledge_base": DEFAULT_KB_NAME},
            "webhook_copy_count": 0,
            "hitl": False,
            "stores_chat_history": False,
        },
        {
            "id": "perf_cpu_graph",
            "fixture": "perf_cpu_graph.json",
            "stress_category": "cpu_graph",
            "source_provenance": "generated:ChatInput->PerfCpuBurnx2(fan-out)->Pass->ChatOutput",
            "supported_protocols": ["mcp", "workflows_sync", "workflows_stream", "workflows_background"],
            "supported_modes": ["sync", "stream", "background"],
            "input_fields": {
                "input_value": "perf-cpu",
                "duration_ms": DEFAULT_CPU_DURATION_MS,
                "iterations": DEFAULT_CPU_ITERATIONS,
            },
            "expected_output_rule": {"matches_regex": r"^cpu:\d+:\d+:[0-9a-f]{16}:perf-cpu$"},
            "mcp_action_name": "perf_cpu_graph",
            "required_environment_features": [],
            "dataset_selector": None,
            "webhook_copy_count": 0,
            "hitl": False,
            "stores_chat_history": False,
            "embedded_components": ["perf_cpu_burn"],
        },
        {
            "id": "perf_multiproc_churn",
            "fixture": "perf_multiproc_churn.json",
            "stress_category": "multiproc",
            "source_provenance": "generated:ChatInput->PerfSubprocessChurn->ChatOutput",
            "supported_protocols": ["mcp", "workflows_sync", "workflows_stream", "workflows_background"],
            "supported_modes": ["sync", "stream", "background"],
            "input_fields": {
                "input_value": "perf-multiproc",
                "count": DEFAULT_MULTIPROC_COUNT,
                "duration_ms": DEFAULT_MULTIPROC_DURATION_MS,
                "working_set_bytes": DEFAULT_MULTIPROC_WORKING_SET_BYTES,
            },
            "expected_output_rule": {
                "matches_regex": (
                    rf"^multiproc:{DEFAULT_MULTIPROC_COUNT}:0(,0)*:\d+:\d+:\d+:\d+:\d+:perf-multiproc"
                    r"(?:\|child:[^|]+)+$"
                )
            },
            "mcp_action_name": "perf_multiproc_churn",
            "required_environment_features": [],
            "dataset_selector": None,
            "webhook_copy_count": 0,
            "hitl": False,
            "stores_chat_history": False,
            "embedded_components": ["perf_subprocess_churn"],
        },
        {
            "id": "perf_disk_io",
            "fixture": "perf_disk_io.json",
            "stress_category": "disk_io",
            "source_provenance": "generated:ChatInput->PerfDiskIo->ChatOutput",
            "supported_protocols": ["mcp", "workflows_sync", "workflows_stream", "workflows_background"],
            "supported_modes": ["sync", "stream", "background"],
            "input_fields": {
                "input_value": "perf-disk",
                "size_bytes": DEFAULT_DISK_IO_SIZE_BYTES,
            },
            "expected_output_rule": {
                "matches_regex": (
                    r"^diskio:size=\d+:written=\d+:read=\d+:cksum_ok=1:write_ms=\d+:fsync_ms=\d+:"
                    r"read_ms=\d+:advise=[01]:rchar=\d+:wchar=\d+:read_bytes=\d+:write_bytes=\d+:"
                    r"cached_read=[01]:seed=perf-disk$"
                )
            },
            "mcp_action_name": "perf_disk_io",
            "required_environment_features": [],
            "dataset_selector": None,
            "webhook_copy_count": 0,
            "hitl": False,
            "stores_chat_history": False,
            "embedded_components": ["perf_disk_io"],
        },
        {
            "id": "perf_payload_echo",
            "fixture": "perf_payload_echo.json",
            "stress_category": "ram_storage",
            "source_provenance": "generated:ChatInput->SaveToFile->ChatOutput",
            "supported_protocols": ["mcp", "workflows_sync", "workflows_stream", "workflows_background"],
            "supported_modes": ["sync", "stream", "background"],
            "input_fields": {"input_value": "{{storage.payload_text}}", "file_name": DEFAULT_PAYLOAD_FILENAME},
            "expected_output_rule": {"save_to_file": True, "filename_contains": DEFAULT_PAYLOAD_FILENAME},
            "mcp_action_name": "perf_payload_echo",
            "required_environment_features": ["storage"],
            "dataset_selector": "storage/bounded_payload",
            "webhook_copy_count": 0,
            "hitl": False,
            "stores_chat_history": False,
        },
        {
            "id": "perf_outbound_basic_prompting",
            "fixture": "perf_outbound_basic_prompting.json",
            "stress_category": "outbound",
            "source_provenance": (
                f"generated-equivalent:{STARTERS_1_6_0_REL}/Basic Prompting.json (deterministic prompt)"
            ),
            "supported_protocols": ["mcp", "workflows_sync", "workflows_stream", "workflows_background"],
            "supported_modes": ["sync", "stream", "background"],
            "input_fields": {"input_value": DEFAULT_OUTBOUND_PROMPT},
            "expected_output_rule": {"contains": "perf-outbound-ok"},
            "mcp_action_name": "perf_outbound_basic_prompting",
            "required_environment_features": ["llm_provider"],
            "dataset_selector": None,
            "binding": {
                "outbound_provider": DEFAULT_OUTBOUND_PROVIDER,
                "outbound_model": DEFAULT_OUTBOUND_MODEL,
            },
            "webhook_copy_count": 0,
            "hitl": False,
            "stores_chat_history": False,
        },
        {
            "id": "perf_ensemble_journey",
            "fixture": "perf_ensemble_journey.json",
            "stress_category": "ensemble_flow",
            "source_provenance": "generated:multiproc->disk->cpu->kb_ingest->save->kb_retrieve->memory->outbound->ChatOutput",
            "supported_protocols": [
                "mcp",
                "workflows_sync",
                "workflows_stream",
                "workflows_background",
                "webhook",
            ],
            "supported_modes": ["sync", "stream", "background", "webhook"],
            "input_fields": {"input_value": "perf-ensemble-journey"},
            "expected_output_rule": {"ensemble_terminal": True},
            "mcp_action_name": "perf_ensemble_journey",
            "required_environment_features": ["knowledge_base", "embeddings", "storage", "llm_provider"],
            "dataset_selector": "kb/bounded_corpus",
            "binding": {
                "knowledge_base": DEFAULT_KB_NAME,
                "outbound_provider": DEFAULT_OUTBOUND_PROVIDER,
                "outbound_model": DEFAULT_OUTBOUND_MODEL,
            },
            "webhook_copy_count": 1,
            "hitl": False,
            "stores_chat_history": True,
            "embedded_components": ["perf_cpu_burn", "perf_disk_io", "perf_subprocess_churn"],
        },
        {
            "id": "perf_ensemble_journey_hitl",
            "fixture": "perf_ensemble_journey_hitl.json",
            "stress_category": "ensemble_flow_hitl",
            "source_provenance": "generated:perf_ensemble_journey+HumanInput(Approve)",
            "supported_protocols": ["workflows_background"],
            "supported_modes": ["background"],
            "input_fields": {"input_value": "perf-ensemble-journey"},
            "expected_output_rule": {
                "hitl_lifecycle": HITL_LIFECYCLE_RULE,
                "ensemble_terminal": True,
            },
            "mcp_action_name": None,
            "required_environment_features": [
                "workflows_background",
                "hitl",
                "knowledge_base",
                "embeddings",
                "storage",
                "llm_provider",
            ],
            "dataset_selector": "hitl/approve_decision",
            "binding": {
                "knowledge_base": DEFAULT_KB_NAME,
                "outbound_provider": DEFAULT_OUTBOUND_PROVIDER,
                "outbound_model": DEFAULT_OUTBOUND_MODEL,
            },
            "webhook_copy_count": 0,
            "hitl": True,
            "stores_chat_history": True,
            "embedded_components": ["perf_cpu_burn", "perf_disk_io", "perf_subprocess_churn"],
        },
    ]


def build_fixture_index(fixture_paths: dict[str, Path]) -> Path:
    hashes = component_source_hashes(COMPONENTS_DIR)
    entries: list[dict[str, Any]] = []

    for spec in flow_specs():
        path = fixture_paths[spec["fixture"]]
        payload = json.loads(path.read_text(encoding="utf-8"))
        entry = deepcopy(spec)
        entry["fixture_path"] = f"fixtures/{spec['fixture']}"
        entry["fixture_sha256"] = sha256_file(path)
        entry["endpoint_name"] = payload.get("endpoint_name")
        entry["node_types"] = _node_types(payload)
        embedded = embedded_isolator_hashes(payload)
        entry["embedded_component_sha256"] = {
            key: embedded[key] for key in entry.get("embedded_components", []) if key in embedded
        }
        entry["expected_component_sha256"] = {key: hashes[key] for key in entry.get("embedded_components", [])}
        entries.append(entry)

    index = {
        "version": FIXTURE_INDEX_VERSION,
        "description": "Complete V1 performance-suite flow contract inventory.",
        "component_source_sha256": hashes,
        "flows": entries,
    }
    index_path = FLOWS_DIR / "fixture_index.json"
    index_path.write_text(json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return index_path
