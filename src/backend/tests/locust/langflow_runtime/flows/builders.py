"""Graph builders that write individual performance-suite flow fixtures.

Called only by ``build_fixtures.py`` when regenerating committed JSON under
``flows/fixtures/``. Not imported by Locust users or integration tests
directly — those load the pinned fixtures instead.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from lfx.components.files_and_knowledge.ingestion import KnowledgeIngestionComponent
from lfx.components.files_and_knowledge.retrieval import KnowledgeBaseComponent
from lfx.components.files_and_knowledge.save_file import SaveToFileComponent
from lfx.components.flow_controls.human_input import HumanInput
from lfx.components.flow_controls.pass_message import PassMessageComponent
from lfx.components.input_output import ChatInput, ChatOutput, TextInputComponent
from lfx.components.input_output.webhook import WebhookComponent
from lfx.components.models_and_agents.language_model import LanguageModelComponent
from lfx.components.models_and_agents.memory import MemoryComponent
from lfx.components.processing.converter import TypeConverterComponent
from lfx.components.processing.split_text import SplitTextComponent
from lfx.graph import Graph

from tests.locust.langflow_runtime.components import PerfCpuBurn, PerfDiskIo, PerfSleep, PerfSubprocessChurn
from tests.locust.langflow_runtime.flows.defaults import (
    DATA_DIR,
    DEFAULT_CPU_DURATION_MS,
    DEFAULT_CPU_ITERATIONS,
    DEFAULT_DISK_IO_SIZE_BYTES,
    DEFAULT_KB_DOC_PREFIX,
    DEFAULT_KB_NAME,
    DEFAULT_KB_QUERY,
    DEFAULT_MULTIPROC_COUNT,
    DEFAULT_MULTIPROC_DURATION_MS,
    DEFAULT_MULTIPROC_WORKING_SET_BYTES,
    DEFAULT_OUTBOUND_API_KEY_VAR,
    DEFAULT_OUTBOUND_MODEL,
    DEFAULT_OUTBOUND_PROMPT,
    DEFAULT_OUTBOUND_PROVIDER,
    DEFAULT_OUTBOUND_SYSTEM,
    DEFAULT_PASSTHROUGH_INPUT,
    DEFAULT_PAYLOAD_FILENAME,
    DEFAULT_QUEUE_INPUT,
    DEFAULT_QUEUE_SLEEP_MS,
    FIXTURES_DIR,
)

if TYPE_CHECKING:
    from pathlib import Path


def dump_graph(
    start,
    end,
    *,
    name: str,
    description: str,
    endpoint_name: str,
) -> dict[str, Any]:
    graph = Graph(start, end)
    payload = graph.dump(name=name, description=description, endpoint_name=endpoint_name)
    payload["name"] = name
    payload["description"] = description
    payload["endpoint_name"] = endpoint_name
    payload["is_component"] = False
    payload["tags"] = ["performance-suite"]
    return payload


def write_fixture(name: str, payload: dict[str, Any]) -> Path:
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    path = FIXTURES_DIR / name
    text = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    path.write_text(text, encoding="utf-8")
    return path


def _ensure_outbound_api_key_load_from_db(payload: dict[str, Any]) -> dict[str, Any]:
    """Keep api_key as a variable reference (no embedded secrets)."""
    for node in payload.get("data", {}).get("nodes", []):
        if node.get("data", {}).get("type") != "LanguageModelComponent":
            continue
        template = node["data"]["node"]["template"]
        api_key = template.get("api_key")
        if isinstance(api_key, dict):
            api_key["value"] = DEFAULT_OUTBOUND_API_KEY_VAR
            api_key["load_from_db"] = True
    return payload


def copy_pinned(source: Path, dest_name: str, *, name: str, description: str, endpoint_name: str) -> Path:
    payload = json.loads(source.read_text(encoding="utf-8"))
    payload["name"] = name
    payload["description"] = description
    payload["endpoint_name"] = endpoint_name
    payload["tags"] = sorted(set(payload.get("tags") or []) | {"performance-suite"})
    payload["is_component"] = False
    payload.pop("id", None)
    return write_fixture(dest_name, payload)


def build_passthrough() -> Path:
    chat_input = ChatInput()
    chat_input.set(should_store_message=False, input_value=DEFAULT_PASSTHROUGH_INPUT)
    chat_output = ChatOutput()
    chat_output.set(should_store_message=False, input_value=chat_input.message_response)
    return write_fixture(
        "perf_passthrough.json",
        dump_graph(
            chat_input,
            chat_output,
            name="perf_passthrough",
            description="Minimal no-LLM passthrough for MCP and Workflows protocol calibration.",
            endpoint_name="perf-passthrough",
        ),
    )


def build_webhook_passthrough() -> Path:
    webhook = WebhookComponent()
    chat_output = ChatOutput()
    chat_output.set(should_store_message=False, input_value=webhook.build_data)
    return write_fixture(
        "perf_webhook_passthrough.json",
        dump_graph(
            webhook,
            chat_output,
            name="perf_webhook_passthrough",
            description="Webhook-safe passthrough ending in ChatOutput for POST -> SSE completion.",
            endpoint_name="perf-webhook-passthrough",
        ),
    )


def build_queue_short() -> Path:
    chat_input = ChatInput()
    chat_input.set(should_store_message=False, input_value=DEFAULT_QUEUE_INPUT)
    sleep = PerfSleep()
    sleep.set(input_value=chat_input.message_response, duration_ms=DEFAULT_QUEUE_SLEEP_MS)
    chat_output = ChatOutput()
    chat_output.set(should_store_message=False, input_value=sleep.run)
    return write_fixture(
        "perf_queue_short.json",
        dump_graph(
            chat_input,
            chat_output,
            name="perf_queue_short",
            description="One bounded perf_sleep job for background acceptance, observation, and drain.",
            endpoint_name="perf-queue-short",
        ),
    )


def build_cpu_graph() -> Path:
    """Representative fan-out/depth: ChatInput fans to two burns that join before output."""
    chat_input = ChatInput()
    chat_input.set(should_store_message=False, input_value="perf-cpu")
    burn_a = PerfCpuBurn()
    burn_a.set(
        input_value=chat_input.message_response,
        duration_ms=DEFAULT_CPU_DURATION_MS,
        iterations=DEFAULT_CPU_ITERATIONS,
    )
    burn_b = PerfCpuBurn()
    burn_b.set(
        input_value=chat_input.message_response,
        duration_ms=DEFAULT_CPU_DURATION_MS,
        iterations=DEFAULT_CPU_ITERATIONS,
    )
    join = PassMessageComponent()
    join.set(input_message=burn_a.run, ignored_message=burn_b.run)
    chat_output = ChatOutput()
    chat_output.set(should_store_message=False, input_value=join.pass_message)
    return write_fixture(
        "perf_cpu_graph.json",
        dump_graph(
            chat_input,
            chat_output,
            name="perf_cpu_graph",
            description="Bounded in-process CPU burn in one representative fan-out/depth graph.",
            endpoint_name="perf-cpu-graph",
        ),
    )


def build_multiproc_churn() -> Path:
    chat_input = ChatInput()
    chat_input.set(should_store_message=False, input_value="perf-multiproc")
    churn = PerfSubprocessChurn()
    churn.set(
        input_value=chat_input.message_response,
        count=DEFAULT_MULTIPROC_COUNT,
        duration_ms=DEFAULT_MULTIPROC_DURATION_MS,
        working_set_bytes=DEFAULT_MULTIPROC_WORKING_SET_BYTES,
        timeout_s=5,
    )
    chat_output = ChatOutput()
    chat_output.set(should_store_message=False, input_value=churn.run)
    return write_fixture(
        "perf_multiproc_churn.json",
        dump_graph(
            chat_input,
            chat_output,
            name="perf_multiproc_churn",
            description=(
                "Bounded concurrent multiprocess context-switch pressure with memory-resident "
                "working sets (no Agent, KB, or provider work)."
            ),
            endpoint_name="perf-multiproc-churn",
        ),
    )


def build_disk_io() -> Path:
    chat_input = ChatInput()
    chat_input.set(should_store_message=False, input_value="perf-disk")
    disk = PerfDiskIo()
    disk.set(input_value=chat_input.message_response, size_bytes=DEFAULT_DISK_IO_SIZE_BYTES)
    chat_output = ChatOutput()
    chat_output.set(should_store_message=False, input_value=disk.run)
    return write_fixture(
        "perf_disk_io.json",
        dump_graph(
            chat_input,
            chat_output,
            name="perf_disk_io",
            description=(
                "Bounded mixed local disk I/O (write, fsync, advisory cold-read, verify). "
                "Distinct from SaveToFile/storage abstraction coverage."
            ),
            endpoint_name="perf-disk-io",
        ),
    )


def build_payload_echo() -> Path:
    chat_input = ChatInput()
    chat_input.set(should_store_message=False, input_value="perf-payload")
    save = SaveToFileComponent()
    save.set(input=chat_input.message_response, file_name=DEFAULT_PAYLOAD_FILENAME)
    chat_output = ChatOutput()
    chat_output.set(should_store_message=False, input_value=save.save_to_file)
    return write_fixture(
        "perf_payload_echo.json",
        dump_graph(
            chat_input,
            chat_output,
            name="perf_payload_echo",
            description="Bounded payload/allocation path with SaveToFile output for storage pressure.",
            endpoint_name="perf-payload-echo",
        ),
    )


def build_kb_ingest() -> Path:
    text_input = TextInputComponent()
    text_input.set(input_value=f"{DEFAULT_KB_DOC_PREFIX}\n\nDeterministic knowledge document for ingest.")
    split = SplitTextComponent()
    split.set(data_inputs=text_input.text_response, chunk_size=200, chunk_overlap=20)
    ingest = KnowledgeIngestionComponent()
    ingest.set(input_df=split.split_text, knowledge_base=DEFAULT_KB_NAME)
    return write_fixture(
        "perf_kb_ingest.json",
        dump_graph(
            text_input,
            ingest,
            name="perf_kb_ingest",
            description=(
                "Deterministic bounded document ingest "
                "(generated equivalent of LFX 1.6.0 Knowledge Ingestion; TextInput replaces URL)."
            ),
            endpoint_name="perf-kb-ingest",
        ),
    )


def build_kb_retrieve() -> Path:
    text_input = TextInputComponent()
    text_input.set(input_value=DEFAULT_KB_QUERY)
    retrieve = KnowledgeBaseComponent()
    retrieve.set(search_query=text_input.text_response, knowledge_base=DEFAULT_KB_NAME)
    chat_output = ChatOutput()
    chat_output.set(should_store_message=False, input_value=retrieve.retrieve_data)
    return write_fixture(
        "perf_kb_retrieve.json",
        dump_graph(
            text_input,
            chat_output,
            name="perf_kb_retrieve",
            description="Deterministic known-query retrieval from the provisioned KB.",
            endpoint_name="perf-kb-retrieve",
        ),
    )


def build_outbound_basic_prompting() -> Path:
    chat_input = ChatInput()
    chat_input.set(should_store_message=False, input_value=DEFAULT_OUTBOUND_PROMPT)
    language_model = LanguageModelComponent()
    language_model.set(
        input_value=chat_input.message_response,
        system_message=DEFAULT_OUTBOUND_SYSTEM,
        model=[{"name": DEFAULT_OUTBOUND_MODEL, "provider": DEFAULT_OUTBOUND_PROVIDER}],
        provider=DEFAULT_OUTBOUND_PROVIDER,
        model_name=DEFAULT_OUTBOUND_MODEL,
        api_key=DEFAULT_OUTBOUND_API_KEY_VAR,
    )
    chat_output = ChatOutput()
    chat_output.set(should_store_message=False, input_value=language_model.text_response)
    payload = dump_graph(
        chat_input,
        chat_output,
        name="perf_outbound_basic_prompting",
        description="One configured real-provider request with a deterministic prompt contract.",
        endpoint_name="perf-outbound-basic-prompting",
    )
    return write_fixture(
        "perf_outbound_basic_prompting.json",
        _ensure_outbound_api_key_load_from_db(payload),
    )


def _rewire_human_input_approve_edge(payload: dict[str, Any]) -> dict[str, Any]:
    """Ensure ChatOutput is fed by HumanInput's Approve branch (normal HITL path)."""
    nodes = payload["data"]["nodes"]
    human_id = next(n["id"] for n in nodes if n["data"]["type"] == "HumanInput")
    chat_output_id = next(n["id"] for n in nodes if n["data"]["type"] == "ChatOutput")
    edges = payload["data"]["edges"]
    kept = []
    for edge in edges:
        if edge.get("source") == human_id and edge.get("target") == chat_output_id:
            source_name = (edge.get("data") or {}).get("sourceHandle", {}).get("name")
            if source_name not in {None, "branch_approve"}:
                continue
        kept.append(edge)
    has_approve = any(
        e.get("source") == human_id
        and e.get("target") == chat_output_id
        and (e.get("data") or {}).get("sourceHandle", {}).get("name") == "branch_approve"
        for e in kept
    )
    if not has_approve:
        kept.append(
            {
                "data": {
                    "sourceHandle": {
                        "dataType": "HumanInput",
                        "id": human_id,
                        "name": "branch_approve",
                        "output_types": ["Message"],
                    },
                    "targetHandle": {
                        "fieldName": "input_value",
                        "id": chat_output_id,
                        "inputTypes": ["Data", "DataFrame", "Message"],
                        "type": "other",
                    },
                },
                "source": human_id,
                "target": chat_output_id,
            }
        )
    payload["data"]["edges"] = kept
    return payload


def build_ensemble_graph(*, hitl: bool) -> dict[str, Any]:
    """Sequential journey covering multiproc, disk, CPU, KB ingest/retrieve, storage, chat/db, outbound."""
    chat_input = ChatInput()
    chat_input.set(should_store_message=True, input_value="perf-ensemble-journey")

    multiproc = PerfSubprocessChurn()
    multiproc.set(
        input_value=chat_input.message_response,
        count=DEFAULT_MULTIPROC_COUNT,
        duration_ms=DEFAULT_MULTIPROC_DURATION_MS,
        working_set_bytes=DEFAULT_MULTIPROC_WORKING_SET_BYTES,
        timeout_s=5,
    )

    disk = PerfDiskIo()
    disk.set(input_value=multiproc.run, size_bytes=DEFAULT_DISK_IO_SIZE_BYTES)

    cpu = PerfCpuBurn()
    cpu.set(
        input_value=disk.run,
        duration_ms=DEFAULT_CPU_DURATION_MS,
        iterations=DEFAULT_CPU_ITERATIONS,
    )

    split = SplitTextComponent()
    split.set(data_inputs=cpu.run, chunk_size=200, chunk_overlap=20)

    ingest = KnowledgeIngestionComponent()
    ingest.set(input_df=split.split_text, knowledge_base=DEFAULT_KB_NAME)

    save = SaveToFileComponent()
    save.set(input=ingest.build_kb_info, file_name="perf_ensemble_storage")

    gate = PassMessageComponent()
    gate.set(input_message=chat_input.message_response, ignored_message=save.save_to_file)

    retrieve = KnowledgeBaseComponent()
    retrieve.set(search_query=gate.pass_message, knowledge_base=DEFAULT_KB_NAME)

    convert = TypeConverterComponent()
    convert.set(input_data=retrieve.retrieve_data)

    memory = MemoryComponent()
    memory.set(message=chat_input.message_response)

    language_model = LanguageModelComponent()
    language_model.set(
        input_value=convert.convert_to_message,
        system_message=memory.retrieve_messages_as_text,
        model=[{"name": DEFAULT_OUTBOUND_MODEL, "provider": DEFAULT_OUTBOUND_PROVIDER}],
        provider=DEFAULT_OUTBOUND_PROVIDER,
        model_name=DEFAULT_OUTBOUND_MODEL,
        api_key=DEFAULT_OUTBOUND_API_KEY_VAR,
    )

    chat_output = ChatOutput()
    chat_output.set(should_store_message=True)

    if hitl:
        human = HumanInput()
        human.set(prompt=language_model.text_response, decisions=["Approve", "Reject"])
        chat_output.set(input_value=human.route_branch)
        payload = dump_graph(
            chat_input,
            chat_output,
            name="perf_ensemble_journey_hitl",
            description="Ensemble journey plus HumanInput for Workflows background/pending/resume only.",
            endpoint_name="perf-ensemble-journey-hitl",
        )
        return _ensure_outbound_api_key_load_from_db(_rewire_human_input_approve_edge(payload))

    chat_output.set(input_value=language_model.text_response)
    payload = dump_graph(
        chat_input,
        chat_output,
        name="perf_ensemble_journey",
        description=(
            "Graph-side multiproc, disk I/O, CPU/graph, KB ingest/retrieve, payload/storage, "
            "chat/database, and outbound journey for MCP, Workflows, and Webhooks."
        ),
        endpoint_name="perf-ensemble-journey",
    )
    return _ensure_outbound_api_key_load_from_db(payload)


def build_ensemble_journey() -> Path:
    return write_fixture("perf_ensemble_journey.json", build_ensemble_graph(hitl=False))


def build_ensemble_journey_hitl() -> Path:
    return write_fixture("perf_ensemble_journey_hitl.json", build_ensemble_graph(hitl=True))


def copy_memory_chatbot() -> Path:
    return copy_pinned(
        DATA_DIR / "MemoryChatbotNoLLM.json",
        "MemoryChatbotNoLLM.json",
        name="MemoryChatbotNoLLM",
        description="Pinned chat/history persistence flow for chat/database stress.",
        endpoint_name="perf-memory-chatbot-no-llm",
    )


def copy_human_input_flow() -> Path:
    return copy_pinned(
        DATA_DIR / "human_input_flow.json",
        "human_input_flow.json",
        name="human_input_flow",
        description="Pinned HITL suspend/pending/resume flow; Workflows background only.",
        endpoint_name="perf-human-input",
    )


def build_natural_fixtures() -> dict[str, Path]:
    """Build Natural suite fixtures (5 shapes x stubbed|live) from pinned starters.

    Stubbed variants keep starter topology (Agent, MemoryBase, Knowledge, File,
    Parser, URL, WebSearch, Prompt) and replace only vendor edges (LLM, web/URL
    HTTP, embedding provider). Live variants bind the configured provider.
    """
    from tests.locust.langflow_runtime.flows.natural_adapt import adapt_natural_starter

    paths: dict[str, Path] = {}
    for shape in (
        "basic_prompting",
        "simple_agent",
        "memory_chatbot",
        "vector_store_rag",
        "file_parser_agent",
    ):
        for stubbed, mode in ((True, "stubbed"), (False, "live")):
            fid = f"natural_{shape}__external_{mode}"
            payload = adapt_natural_starter(shape, stubbed=stubbed)
            paths[f"{fid}.json"] = write_fixture(f"{fid}.json", payload)
    return paths
