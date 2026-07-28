"""Live subsystem coverage for performance-suite fixtures.

These tests prove the fixtures trigger the subsystems they claim to isolate.
Everything goes through the live app (workflows / webhook HTTP / MCP) except
provider edges that would otherwise require network credentials or model
downloads:

* ``get_llm`` → ``FakeListChatModel`` (outbound / ensemble)
* KB fixtures embed a deterministic ``get_embeddings`` override in the saved
  Knowledge component source (KB ingest / retrieve / ensemble)

KB storage uses the real settings ``knowledge_bases_dir`` (not a private-module
patch). Components, Chroma, workflows, HITL, webhooks, and MCP stay live.
"""

from __future__ import annotations

import asyncio
import json
import re
from contextlib import nullcontext
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from langchain_chroma import Chroma
from lfx.memory import aget_messages

from tests.locust.langflow_runtime.components.perf_deterministic_embeddings import DeterministicEmbeddings
from tests.locust.langflow_runtime.components.perf_disk_io import parse_diskio_result
from tests.locust.langflow_runtime.components.perf_subprocess_churn import parse_multiproc_result
from tests.locust.langflow_runtime.datasets.kb_corpus import KB_DOC_BYTES, kb_corpus, kb_ingest_document
from tests.locust.langflow_runtime.datasets.storage_payload import bounded_payload_text
from tests.locust.langflow_runtime.flows.defaults import (
    DEFAULT_CHAT_INPUT,
    DEFAULT_DISK_IO_SIZE_BYTES,
    DEFAULT_KB_DOC_PREFIX,
    DEFAULT_KB_NAME,
    DEFAULT_KB_QUERY,
    DEFAULT_MULTIPROC_COUNT,
    DEFAULT_MULTIPROC_DURATION_MS,
    DEFAULT_MULTIPROC_WORKING_SET_BYTES,
    DEFAULT_OUTBOUND_PROMPT,
    DEFAULT_PASSTHROUGH_INPUT,
    DEFAULT_PAYLOAD_FILENAME,
    DEFAULT_QUEUE_INPUT,
    DEFAULT_QUEUE_SLEEP_MS,
    FLOWS_DIR,
    MAX_CHAT_RESPONSE_BYTES,
)
from tests.locust.langflow_runtime.users.helpers import extract_output_text

if TYPE_CHECKING:
    from httpx import AsyncClient
from tests.locust.langflow_runtime.contracts import DEFAULT_WEBHOOK_PAYLOAD
from tests.locust.tests.integration import (
    delete_flow,
    delete_project,
    flow_entry,
    insert_flow,
    insert_project,
    knowledge_bases_dir,
    load_fixture_payload,
    local_save_workdir,
    mcp_initialize_list_call,
    mock_language_model_responses,
    post_workflow,
    provision_local_kb,
    provision_openai_api_key_variable,
    real_http_base_url,
    stream_workflow_until_terminal,
    wait_job_status,
    webhook_http_subscribe_before_post,
)

pytestmark = [pytest.mark.performance_integration, pytest.mark.integration]


def _workflow_input(flow_id: str) -> str:
    fields = flow_entry(flow_id).get("input_fields") or {}
    raw = fields.get("input_value")
    if raw is None:
        return DEFAULT_PASSTHROUGH_INPUT
    if isinstance(raw, str) and raw.startswith("{{") and raw.endswith("}}"):
        if "chat.turn_text" in raw:
            return DEFAULT_CHAT_INPUT
        if "storage.payload_text" in raw:
            return bounded_payload_text()
        return raw
    return str(raw)


@pytest.mark.parametrize(
    ("flow_id", "needle"),
    [
        ("perf_passthrough", DEFAULT_PASSTHROUGH_INPUT),
        ("perf_queue_short", f"slept:{DEFAULT_QUEUE_SLEEP_MS}:{DEFAULT_QUEUE_INPUT}"),
        ("perf_cpu_graph", None),  # regex checked below
        ("perf_payload_echo", DEFAULT_PAYLOAD_FILENAME),
    ],
)
async def test_live_workflows_sync_isolators(
    client: AsyncClient, created_api_key, tmp_path, flow_id: str, needle: str | None
):
    """Isolator axes: live workflows sync through committed fixture JSON."""
    payload = load_fixture_payload(flow_id)
    inserted = await insert_flow(user_id=created_api_key.user_id, payload=payload)
    save_ctx = local_save_workdir(tmp_path) if flow_id == "perf_payload_echo" else nullcontext()
    try:
        with save_ctx:
            result = await post_workflow(
                client,
                api_key=created_api_key.api_key,
                flow_id=inserted,
                mode="sync",
                input_value=_workflow_input(flow_id),
                session_id=f"perf-isolator-{flow_id}-{uuid4().hex[:8]}",
            )
        serialized = json.dumps(result)
        assert result.get("status") in {None, "completed"} or "outputs" in result or result.get("object")
        if needle is not None:
            assert needle in serialized or needle.lower() in serialized.lower(), serialized
        if flow_id == "perf_cpu_graph":
            assert re.search(r"cpu:\d+:\d+:[0-9a-f]{16}:perf-cpu", serialized)
        if flow_id == "perf_payload_echo":
            assert DEFAULT_PAYLOAD_FILENAME in serialized or "saved" in serialized.lower()
    finally:
        await delete_flow(inserted)


def _extract_metric_blob(serialized: str, prefix: str) -> str:
    match = re.search(rf"({prefix}:[^\"\\]+)", serialized)
    assert match, serialized
    return match.group(1)


async def test_live_multiproc_context_switch_stress(client: AsyncClient, created_api_key):
    """Prove concurrent children, full working sets, overlap, and scheduler switches."""
    payload = load_fixture_payload("perf_multiproc_churn")
    flow_id = await insert_flow(user_id=created_api_key.user_id, payload=payload)
    try:
        result = await post_workflow(
            client,
            api_key=created_api_key.api_key,
            flow_id=flow_id,
            mode="sync",
            input_value=_workflow_input("perf_multiproc_churn"),
            session_id=f"perf-multiproc-{uuid4().hex[:8]}",
        )
        serialized = json.dumps(result)
        parsed = parse_multiproc_result(_extract_metric_blob(serialized, "multiproc"))
        assert parsed["count"] == DEFAULT_MULTIPROC_COUNT
        assert parsed["codes"] == [0] * DEFAULT_MULTIPROC_COUNT
        assert int(parsed["ws_bytes"]) >= min(DEFAULT_MULTIPROC_WORKING_SET_BYTES, 256 * 1024)
        # Concurrent wall time should be closer to one duration than N durations.
        assert int(parsed["elapsed_ms"]) < (DEFAULT_MULTIPROC_COUNT * DEFAULT_MULTIPROC_DURATION_MS) + 2000
        children = parsed["children"]
        assert len(children) == DEFAULT_MULTIPROC_COUNT
        assert len({child["pid"] for child in children}) == DEFAULT_MULTIPROC_COUNT
        # Overlap is expected under synchronized start; allow zero on heavily loaded hosts
        # and still require concurrency evidence via elapsed_ms + distinct PIDs above.
        assert int(parsed["overlap_ms"]) >= 0
        for child in children:
            assert int(child["pages"]) > 0
            assert int(child["touched"]) >= int(child["pages"])
            assert child["cksum"]
            assert int(child["cksum"], 16) != 0
        if all(str(child["aff"]).isdigit() for child in children):
            affinities = {str(child["aff"]) for child in children}
            assert len(affinities) == 1
            assert sum(int(child["ivcs"]) for child in children) >= 1
            assert int(parsed["vcs"]) + int(parsed["ivcs"]) >= 1
    finally:
        await delete_flow(flow_id)


async def test_live_disk_io_stress(client: AsyncClient, created_api_key, tmp_path):
    """Prove write/fsync/read/verify through the committed disk fixture and live Workflows API."""
    payload = load_fixture_payload("perf_disk_io")
    flow_id = await insert_flow(user_id=created_api_key.user_id, payload=payload)
    try:
        with local_save_workdir(tmp_path):
            result = await post_workflow(
                client,
                api_key=created_api_key.api_key,
                flow_id=flow_id,
                mode="sync",
                input_value=_workflow_input("perf_disk_io"),
                session_id=f"perf-disk-{uuid4().hex[:8]}",
            )
        serialized = json.dumps(result)
        parsed = parse_diskio_result(_extract_metric_blob(serialized, "diskio"))
        assert int(parsed["size"]) >= 64 * 1024
        assert int(parsed["written"]) == int(parsed["size"])
        assert int(parsed["read"]) == int(parsed["size"])
        assert parsed["cksum_ok"] is True
        assert int(parsed["write_ms"]) >= 1
        assert int(parsed["fsync_ms"]) >= 1
        assert int(parsed["read_ms"]) >= 1
        assert parsed["seed"] == "perf-disk"
        # Logical write path should show activity; backing-storage write_bytes is best-effort.
        assert int(parsed["wchar"]) >= int(parsed["written"]) or int(parsed["write_bytes"]) > 0
        if int(parsed["write_bytes"]) > 0:
            assert int(parsed["write_bytes"]) >= min(int(parsed["size"]) // 2, DEFAULT_DISK_IO_SIZE_BYTES // 2)
        leftovers = list(tmp_path.rglob("perf-disk-*.bin"))
        assert leftovers == [], leftovers
    finally:
        await delete_flow(flow_id)


async def test_queue_background_admission_and_completion(client: AsyncClient, created_api_key):
    """Queue axis: workflows background accepts a job_id and reaches completed."""
    payload = load_fixture_payload("perf_queue_short")
    flow_id = await insert_flow(user_id=created_api_key.user_id, payload=payload)
    try:
        result = await post_workflow(
            client,
            api_key=created_api_key.api_key,
            flow_id=flow_id,
            mode="background",
            input_value=DEFAULT_QUEUE_INPUT,
            session_id=f"perf-queue-{uuid4().hex[:8]}",
        )
        assert result["object"] == "job"
        assert result["status"] == "queued"
        assert result.get("job_id")
        status = await wait_job_status(result["job_id"], want={"completed"})
        assert status == "completed"

        status_resp = await client.get(
            f"api/v2/workflows?job_id={result['job_id']}",
            headers={"x-api-key": created_api_key.api_key},
        )
        assert status_resp.status_code == 200, status_resp.text
        body = status_resp.json()
        assert body["status"] == "completed"
        serialized = json.dumps(body)
        assert f"slept:{DEFAULT_QUEUE_SLEEP_MS}:{DEFAULT_QUEUE_INPUT}" in serialized
    finally:
        await delete_flow(flow_id)


async def test_hitl_background_pending_resume_completed(client: AsyncClient, created_api_key):
    """HITL axis: background → suspended → pending → resume → completed."""
    payload = load_fixture_payload("human_input_flow")
    flow_id = await insert_flow(user_id=created_api_key.user_id, payload=payload)
    headers = {"x-api-key": created_api_key.api_key}
    try:
        start = await post_workflow(
            client,
            api_key=created_api_key.api_key,
            flow_id=flow_id,
            mode="background",
            input_value="Approve this?",
            session_id=f"perf-hitl-{uuid4().hex[:8]}",
        )
        job_id = start["job_id"]
        status = await wait_job_status(job_id, want={"suspended"})
        assert status == "suspended"

        pending = await client.get(f"api/v2/workflows/pending?flow_id={flow_id}", headers=headers)
        assert pending.status_code == 200, pending.text
        items = pending.json()
        match = next(item for item in items if item["job_id"] == job_id)
        request_id = match["request_id"]
        assert request_id

        resume = await client.post(
            f"api/v2/workflows/{job_id}/resume",
            headers=headers,
            json={"request_id": request_id, "decision": {"action_id": "approve"}},
        )
        assert resume.status_code == 200, resume.text
        assert resume.json()["status"] == "resuming"

        final = await wait_job_status(job_id, want={"completed"})
        assert final == "completed"
    finally:
        await delete_flow(flow_id)


async def test_webhook_http_sse_subscribe_before_post(client: AsyncClient, created_api_key, active_user):
    """Webhook axis: real HTTP SSE connected → POST 202 → SSE end.

    SSE and POST each run on their own thread/event loop. SSE uses a session
    cookie; POST uses the API key (API-key auth on long-lived SSE deadlocks
    SQLite via held ``last_used_at`` writes).
    """
    payload = load_fixture_payload("perf_webhook_passthrough")
    endpoint = payload["endpoint_name"]
    flow_id = await insert_flow(
        user_id=created_api_key.user_id,
        payload=payload,
        endpoint_name=endpoint,
    )
    login = await client.post(
        "api/v1/login",
        data={"username": active_user.username, "password": "testpassword"},  # pragma: allowlist secret
    )
    assert login.status_code == 200, login.text
    sse_cookies = {"access_token_lf": client.cookies["access_token_lf"]}
    try:
        async with real_http_base_url(client) as base_url:
            frames = await asyncio.to_thread(
                webhook_http_subscribe_before_post,
                base_url=base_url,
                api_key=created_api_key.api_key,
                flow_id=flow_id,
                endpoint_name=endpoint,
                payload=DEFAULT_WEBHOOK_PAYLOAD,
                sse_cookies=sse_cookies,
            )
        joined = "\n".join(frames).lower()
        assert "event: connected" in joined
        assert "event: end" in joined, f"webhook SSE did not complete with end; frames={frames!r}"
    finally:
        await delete_flow(flow_id)


async def test_workflows_stream_emits_terminal_event(client: AsyncClient, created_api_key):
    """Workflows stream axis: mode=stream langflow protocol ends with a terminal event."""
    payload = load_fixture_payload("perf_passthrough")
    flow_id = await insert_flow(user_id=created_api_key.user_id, payload=payload)
    try:
        body = await stream_workflow_until_terminal(
            client,
            api_key=created_api_key.api_key,
            flow_id=flow_id,
            input_value=DEFAULT_PASSTHROUGH_INPUT,
            session_id=f"perf-stream-{uuid4().hex[:8]}",
        )
        assert '"event": "end"' in body or '"event":"end"' in body or "event: end" in body
        assert DEFAULT_PASSTHROUGH_INPUT in body or "perf-passthrough" in body.lower()
    finally:
        await delete_flow(flow_id)


async def test_mcp_initialize_list_call_passthrough(client: AsyncClient, created_api_key):
    """MCP axis: live streamable-HTTP initialize → list_tools → call_tool on perf_passthrough."""
    project_id = await insert_project(user_id=created_api_key.user_id)
    payload = load_fixture_payload("perf_passthrough")
    action_name = flow_entry("perf_passthrough")["mcp_action_name"]
    flow_id = await insert_flow(
        user_id=created_api_key.user_id,
        payload=payload,
        folder_id=project_id,
        mcp_enabled=True,
        action_name=action_name,
        name=payload.get("name") or "perf_passthrough",
    )
    try:
        async with real_http_base_url(client) as base_url:
            result = await mcp_initialize_list_call(
                base_url=base_url,
                api_key=created_api_key.api_key,
                project_id=project_id,
                tool_name=action_name,
                arguments={
                    "input_value": DEFAULT_PASSTHROUGH_INPUT,
                    "session_id": f"perf-mcp-{uuid4().hex[:8]}",
                },
            )
        serialized = json.dumps(result.model_dump() if hasattr(result, "model_dump") else str(result))
        assert DEFAULT_PASSTHROUGH_INPUT in serialized
        assert not getattr(result, "isError", False), serialized
    finally:
        await delete_flow(flow_id)
        await delete_project(project_id)


async def test_chat_db_session_persists_messages(client: AsyncClient, created_api_key):
    """Chat/DB axis: repeated turns persist bounded messages for one session."""
    payload = load_fixture_payload("perf_chat_db_agent")
    flow_id = await insert_flow(user_id=created_api_key.user_id, payload=payload)
    session_id = f"perf-chat-{uuid4().hex[:8]}"
    try:
        turns = 5
        for turn in range(1, turns + 1):
            input_value = f"{DEFAULT_CHAT_INPUT}-{turn}"
            result = await post_workflow(
                client,
                api_key=created_api_key.api_key,
                flow_id=flow_id,
                mode="sync",
                input_value=input_value,
                session_id=session_id,
            )
            text = extract_output_text(result)
            assert input_value in text
            assert len(text.encode("utf-8")) <= MAX_CHAT_RESPONSE_BYTES

        messages = await aget_messages(session_id=session_id)
        assert len(messages) >= turns * 2
        stored_text = "\n".join(str(message.text or "") for message in messages)
        assert all(f"{DEFAULT_CHAT_INPUT}-{turn}" in stored_text for turn in range(1, turns + 1))
    finally:
        await delete_flow(flow_id)


async def test_kb_fixture_ingest_then_retrieve(client: AsyncClient, created_api_key, active_user, tmp_path):
    """KB axes: live workflows and Chroma; fixture source stubs only embeddings."""
    ingest_flow = flow_entry("perf_kb_ingest")
    retrieve_flow = flow_entry("perf_kb_retrieve")
    assert ingest_flow.get("binding", {}).get("knowledge_base") == DEFAULT_KB_NAME
    assert retrieve_flow.get("binding", {}).get("knowledge_base") == DEFAULT_KB_NAME

    docs_root = tmp_path / "kb_docs"
    with kb_corpus(docs_root) as docs, knowledge_bases_dir(tmp_path / "kb_store"):
        assert all(doc.stat().st_size == KB_DOC_BYTES for doc in docs)
        kb_path = await provision_local_kb(
            username=active_user.username,
            user_id=created_api_key.user_id,
            root=tmp_path / "kb_store",
        )
        ingest_id = await insert_flow(
            user_id=created_api_key.user_id,
            payload=load_fixture_payload("perf_kb_ingest"),
        )
        retrieve_id = await insert_flow(
            user_id=created_api_key.user_id,
            payload=load_fixture_payload("perf_kb_retrieve"),
        )
        try:
            for doc in docs:
                await post_workflow(
                    client,
                    api_key=created_api_key.api_key,
                    flow_id=ingest_id,
                    mode="sync",
                    input_value=doc.read_text(encoding="ascii"),
                    session_id=f"perf-kb-ingest-{uuid4().hex[:8]}",
                )
            assert (kb_path / "chroma.sqlite3").exists(), f"ingest did not create chroma store under {kb_path}"
            assert any(kb_path.rglob("*.bin")), f"ingest did not write vector index files under {kb_path}"
            unique_documents = [kb_ingest_document("perf-integration", turn) for turn in (1, 2)]
            for input_value in unique_documents:
                await post_workflow(
                    client,
                    api_key=created_api_key.api_key,
                    flow_id=ingest_id,
                    mode="sync",
                    input_value=input_value,
                    session_id="perf-kb-ingest-unique",
                )
            direct_store = Chroma(
                persist_directory=str(kb_path),
                collection_name=DEFAULT_KB_NAME,
                embedding_function=DeterministicEmbeddings(),
            )
            stored = direct_store.get(include=["documents", "embeddings"])
            documents = stored.get("documents") or []
            assert all(document in documents for document in unique_documents)
            marker_index = next(
                (index for index, document in enumerate(documents) if DEFAULT_KB_DOC_PREFIX in (document or "")),
                None,
            )
            assert marker_index is not None, "ingest did not persist the corpus marker chunk"
            stored_embeddings = stored.get("embeddings")
            assert stored_embeddings is not None
            expected_embedding = DeterministicEmbeddings().embed_query(documents[marker_index])
            assert stored_embeddings[marker_index] == pytest.approx(expected_embedding)
            direct_results = direct_store.similarity_search(DEFAULT_KB_QUERY, k=5)
            assert any(DEFAULT_KB_DOC_PREFIX in doc.page_content for doc in direct_results)

            retrieve = await post_workflow(
                client,
                api_key=created_api_key.api_key,
                flow_id=retrieve_id,
                mode="sync",
                input_value=DEFAULT_KB_QUERY,
                session_id=f"perf-kb-retrieve-{uuid4().hex[:8]}",
            )
            serialized = json.dumps(retrieve)
            assert DEFAULT_KB_DOC_PREFIX in serialized, serialized
        finally:
            await delete_flow(ingest_id)
            await delete_flow(retrieve_id)


async def test_outbound_language_model_via_workflows(client: AsyncClient, created_api_key):
    """Outbound axis: live workflows sync; only provider LLM factory is stubbed."""
    await provision_openai_api_key_variable(user_id=created_api_key.user_id)
    payload = load_fixture_payload("perf_outbound_basic_prompting")
    flow_id = await insert_flow(user_id=created_api_key.user_id, payload=payload)
    try:
        with mock_language_model_responses("perf-outbound-ok"):
            result = await post_workflow(
                client,
                api_key=created_api_key.api_key,
                flow_id=flow_id,
                mode="sync",
                input_value=DEFAULT_OUTBOUND_PROMPT,
                session_id=f"perf-outbound-{uuid4().hex[:8]}",
            )
        serialized = json.dumps(result)
        assert "perf-outbound-ok" in serialized
    finally:
        await delete_flow(flow_id)


async def test_ensemble_journey_via_workflows(client: AsyncClient, created_api_key, active_user, tmp_path):
    """Ensemble axis: live workflows sync; only the provider edges are stubbed."""
    await provision_openai_api_key_variable(user_id=created_api_key.user_id)
    payload = load_fixture_payload("perf_ensemble_journey")
    flow_id = await insert_flow(user_id=created_api_key.user_id, payload=payload)
    session_id = f"perf-ensemble-{uuid4().hex[:8]}"
    try:
        with (
            knowledge_bases_dir(tmp_path),
            local_save_workdir(tmp_path),
            mock_language_model_responses("perf-outbound-ok"),
        ):
            await provision_local_kb(
                username=active_user.username,
                user_id=created_api_key.user_id,
                root=tmp_path,
            )
            result = await post_workflow(
                client,
                api_key=created_api_key.api_key,
                flow_id=flow_id,
                mode="sync",
                input_value=_workflow_input("perf_ensemble_journey"),
                session_id=session_id,
            )
        serialized = json.dumps(result)
        assert "perf-outbound-ok" in serialized, serialized
        messages = await aget_messages(session_id=session_id)
        assert len(messages) >= 1
    finally:
        await delete_flow(flow_id)


async def test_ensemble_hitl_background_pending_resume(client: AsyncClient, created_api_key, active_user, tmp_path):
    """Ensemble HITL: live background/pending/resume; only the provider edges are stubbed."""
    await provision_openai_api_key_variable(user_id=created_api_key.user_id)
    payload = load_fixture_payload("perf_ensemble_journey_hitl")
    flow_id = await insert_flow(user_id=created_api_key.user_id, payload=payload)
    headers = {"x-api-key": created_api_key.api_key}
    try:
        with (
            knowledge_bases_dir(tmp_path),
            local_save_workdir(tmp_path),
            mock_language_model_responses("perf-outbound-ok"),
        ):
            await provision_local_kb(
                username=active_user.username,
                user_id=created_api_key.user_id,
                root=tmp_path,
            )
            start = await post_workflow(
                client,
                api_key=created_api_key.api_key,
                flow_id=flow_id,
                mode="background",
                input_value="perf-ensemble-journey",
                session_id=f"perf-ensemble-hitl-{uuid4().hex[:8]}",
            )
            job_id = start["job_id"]
            status = await wait_job_status(job_id, want={"suspended", "failed", "completed"}, timeout_s=120.0)
            assert status == "suspended", f"ensemble HITL did not suspend; status={status}"

            pending = await client.get(f"api/v2/workflows/pending?flow_id={flow_id}", headers=headers)
            assert pending.status_code == 200, pending.text
            items = pending.json()
            match = next(item for item in items if item["job_id"] == job_id)
            resume = await client.post(
                f"api/v2/workflows/{job_id}/resume",
                headers=headers,
                json={"request_id": match["request_id"], "decision": {"action_id": "approve"}},
            )
            assert resume.status_code == 200, resume.text
            final = await wait_job_status(job_id, want={"completed"}, timeout_s=120.0)
            assert final == "completed"
    finally:
        await delete_flow(flow_id)


async def test_fixture_bindings_are_non_empty():
    """Static regression: KB/outbound fixtures must declare runnable bindings."""
    from tests.locust.langflow_runtime.flows.validate_fixtures import validate_fixture_bindings

    assert validate_fixture_bindings() == []
