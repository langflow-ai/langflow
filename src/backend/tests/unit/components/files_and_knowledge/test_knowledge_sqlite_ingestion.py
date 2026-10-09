"""Flow ingestion must publish the totals stored in the SQLite knowledge base."""

import asyncio
import contextlib
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import anyio
import pytest
from langchain_core.embeddings import Embeddings
from langflow.api.utils import ingestion_run_service, knowledge_base_service
from langflow.services.database.models.jobs.model import JobStatus
from langflow.services.deps import get_job_service, get_settings_service
from lfx.components.files_and_knowledge.knowledge import KnowledgeComponent
from lfx.graph import Graph
from lfx.graph.graph.constants import Finish
from lfx.schema.dataframe import DataFrame


class LocalEmbeddings(Embeddings):
    def embed_documents(self, texts):
        return [[float(len(text)), 1.0] for text in texts]

    def embed_query(self, text):
        return self.embed_documents([text])[0]


@pytest.mark.parametrize("allow_duplicates", [False, True])
async def test_flow_ingestion_updates_sqlite_totals(
    client, logged_in_headers, active_user, monkeypatch, tmp_path, allow_duplicates
):
    monkeypatch.setattr(get_settings_service().settings, "knowledge_bases_dir", str(tmp_path))
    monkeypatch.delenv("PGVECTOR_CONNECTION_STRING", raising=False)
    monkeypatch.setattr(
        "lfx.components.files_and_knowledge.knowledge.get_embeddings", lambda **_kwargs: LocalEmbeddings()
    )
    name = "flow_ingestion_stats"
    endpoint = f"/api/v1/knowledge_bases/{name}"
    response = await client.post(
        "/api/v1/knowledge_bases",
        json={"name": name, "embedding_provider": "OpenAI", "embedding_model": "text-embedding-3-small"},
        headers=logged_in_headers,
    )
    assert response.status_code == 201, response.text
    assert response.json()["backend_type"] == "sqlite"
    response = await client.get(endpoint, headers=logged_in_headers)
    assert response.json()["chunks"] == 0
    assert response.json()["status"] == "empty"

    texts = ["first document", "second document", "third document", "fourth document", "café document"]
    component = KnowledgeComponent(
        knowledge_base=name,
        column_config=[
            {"column_name": "text", "vectorize": True, "identifier": False},
            {"column_name": "source", "vectorize": False, "identifier": False},
        ],
        allow_duplicates=allow_duplicates,
        _user_id=active_user.id,
    )

    repeated_texts = texts * (2 if allow_duplicates else 1)
    for input_texts, expected_texts in (
        (texts, texts),
        (texts, repeated_texts),
        (["appended document"], [*repeated_texts, "appended document"]),
    ):
        component.set(input_df=DataFrame({"text": input_texts, "source": ["documents.txt"] * len(input_texts)}))
        graph = Graph(start=component, end=component)
        async for result in graph.async_start():
            if not isinstance(result, Finish):
                assert result.result_dict, result
        response = await client.get(f"{endpoint}/chunks", headers=logged_in_headers)
        assert response.status_code == 200, response.text
        assert response.json()["total"] == len(expected_texts)
        assert sorted(chunk["content"] for chunk in response.json()["chunks"]) == sorted(expected_texts)

        response = await client.get(endpoint, headers=logged_in_headers)
        assert response.status_code == 200, response.text
        info = response.json()
        assert info["chunks"] == len(expected_texts)
        assert info["words"] == sum(len(text.split()) for text in expected_texts)
        assert info["characters"] == sum(len(text) for text in expected_texts)
        assert info["size"] > 0
        assert info["source_types"] == ["txt"]
        assert info["status"] == "ready"

    response = await client.get(f"{endpoint}/runs", headers=logged_in_headers)
    assert response.status_code == 200, response.text
    runs = response.json()["runs"]
    assert len(runs) == 3
    assert all(run["status"] == "succeeded" for run in runs)


@pytest.mark.parametrize("cancel_kind", ["task", "scope"])
@pytest.mark.parametrize("cancel_stage", ["tracking", "embedding"])
@pytest.mark.parametrize("has_documents", [False, True])
async def test_cancelled_flow_ingestion_finalizes_run(
    client, logged_in_headers, active_user, monkeypatch, tmp_path, cancel_kind, cancel_stage, has_documents
):
    monkeypatch.setattr(get_settings_service().settings, "knowledge_bases_dir", str(tmp_path))
    monkeypatch.delenv("PGVECTOR_CONNECTION_STRING", raising=False)
    embeddings = LocalEmbeddings()
    monkeypatch.setattr("lfx.components.files_and_knowledge.knowledge.get_embeddings", lambda **_kwargs: embeddings)
    name = "cancelled_flow_ingestion"
    endpoint = f"/api/v1/knowledge_bases/{name}"
    response = await client.post(
        "/api/v1/knowledge_bases",
        json={"name": name, "embedding_provider": "OpenAI", "embedding_model": "text-embedding-3-small"},
        headers=logged_in_headers,
    )
    assert response.status_code == 201, response.text
    component = KnowledgeComponent(
        knowledge_base=name,
        input_df=DataFrame({"text": ["original document"]}),
        _user_id=active_user.id,
    )
    if has_documents:
        await component.build_kb_info()
    component.set(input_df=DataFrame({"text": ["interrupted document"]}))
    operation_started = asyncio.Event()

    async def blocked_embeddings(_texts):
        operation_started.set()
        await asyncio.Event().wait()

    if cancel_stage == "embedding":
        monkeypatch.setattr(embeddings, "aembed_documents", blocked_embeddings)
    else:
        mark_running = ingestion_run_service.mark_running

        async def blocked_tracking(run_id):
            await mark_running(run_id)
            operation_started.set()
            await asyncio.Event().wait()

        monkeypatch.setattr(ingestion_run_service, "mark_running", blocked_tracking)
    cancel_scopes = []

    async def ingest():
        with anyio.CancelScope() as scope:
            cancel_scopes.append(scope)
            await component.build_results()

    task = asyncio.create_task(ingest())
    try:
        await asyncio.wait_for(operation_started.wait(), timeout=10)
        response = await client.get(f"{endpoint}/runs", headers=logged_in_headers)
        assert response.json()["runs"][0]["status"] == "running"
        if cancel_kind == "task":
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        else:
            cancel_scopes[0].cancel()
            await task
    finally:
        if not task.done():
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task

    response = await client.get(f"{endpoint}/runs", headers=logged_in_headers)
    run = response.json()["runs"][0]
    assert run["status"] == "cancelled"
    assert run["finished_at"] is not None
    assert run["chunks_created"] == 0
    job = await get_job_service().get_job_by_job_id(UUID(run["job_id"]))
    assert job.status == JobStatus.CANCELLED
    assert job.finished_timestamp is not None
    record = await knowledge_base_service.get_by_user_and_name(active_user.id, name)
    assert record.status == "ready"
    response = await client.get(endpoint, headers=logged_in_headers)
    assert response.json()["status"] == ("ready" if has_documents else "empty")
    assert response.json()["chunks"] == int(has_documents)


async def _create_ready_kb(client, headers, active_user, monkeypatch, tmp_path, name, *, has_documents):
    """Create a SQLite KB, optionally holding one flow-ingested chunk."""
    monkeypatch.setattr(get_settings_service().settings, "knowledge_bases_dir", str(tmp_path))
    monkeypatch.delenv("PGVECTOR_CONNECTION_STRING", raising=False)
    embeddings = LocalEmbeddings()
    monkeypatch.setattr("lfx.components.files_and_knowledge.knowledge.get_embeddings", lambda **_kwargs: embeddings)
    response = await client.post(
        "/api/v1/knowledge_bases",
        json={"name": name, "embedding_provider": "OpenAI", "embedding_model": "text-embedding-3-small"},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    component = KnowledgeComponent(
        knowledge_base=name,
        input_df=DataFrame({"text": ["original document"]}),
        _user_id=active_user.id,
    )
    if has_documents:
        await component.build_kb_info()
    component.set(input_df=DataFrame({"text": ["interrupted document"]}))
    return component, embeddings


async def _assert_cancel_restored_kb(client, headers, active_user, name, *, has_documents):
    endpoint = f"/api/v1/knowledge_bases/{name}"
    response = await client.get(f"{endpoint}/runs", headers=headers)
    run = response.json()["runs"][0]
    assert run["status"] == "cancelled"
    assert run["finished_at"] is not None
    assert run["chunks_created"] == 0
    job = await get_job_service().get_job_by_job_id(UUID(run["job_id"]))
    assert job.status == JobStatus.CANCELLED
    record = await knowledge_base_service.get_by_user_and_name(active_user.id, name)
    assert record.status == "ready"
    expected_status = "ready" if has_documents else "empty"
    response = await client.get(endpoint, headers=headers)
    assert response.json()["status"] == expected_status
    assert response.json()["chunks"] == int(has_documents)
    response = await client.get("/api/v1/knowledge_bases", headers=headers)
    listed = next(kb for kb in response.json() if kb["dir_name"] == name)
    assert listed["status"] == expected_status
    assert listed["chunks"] == int(has_documents)


async def test_repeated_cancellation_cannot_strand_the_run(
    client, logged_in_headers, active_user, monkeypatch, tmp_path
):
    """A stopped build can cancel its task again while the cancelled run is being finalized."""
    name = "repeatedly_cancelled_ingestion"
    component, embeddings = await _create_ready_kb(
        client, logged_in_headers, active_user, monkeypatch, tmp_path, name, has_documents=True
    )
    embedding_started = asyncio.Event()

    async def blocked_embeddings(_texts):
        embedding_started.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(embeddings, "aembed_documents", blocked_embeddings)
    finalize_started = asyncio.Event()
    release_finalize = asyncio.Event()
    finalize_run = ingestion_run_service.finalize_run

    async def slow_finalize(*args, **kwargs):
        finalize_started.set()
        await release_finalize.wait()
        await finalize_run(*args, **kwargs)

    monkeypatch.setattr(ingestion_run_service, "finalize_run", slow_finalize)

    task = asyncio.create_task(component.build_results())
    await asyncio.wait_for(embedding_started.wait(), timeout=10)
    task.cancel()
    await asyncio.wait_for(finalize_started.wait(), timeout=10)
    task.cancel()
    await asyncio.sleep(0.05)
    release_finalize.set()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, timeout=10)

    await _assert_cancel_restored_kb(client, logged_in_headers, active_user, name, has_documents=True)


async def test_disconnected_playground_stream_finalizes_the_run(
    client, logged_in_headers, active_user, monkeypatch, tmp_path
):
    """Leaving the flow drops the stream; the run must still end cancelled.

    Mirrors ``_stream_event_frames``: Starlette cancels the response's AnyIO
    scope on disconnect, and the generator's ``finally`` awaits the run task
    inside that scope, so AnyIO re-cancels the run task on every loop tick.
    """
    name = "disconnected_stream_ingestion"
    component, embeddings = await _create_ready_kb(
        client, logged_in_headers, active_user, monkeypatch, tmp_path, name, has_documents=True
    )
    embedding_started = asyncio.Event()

    async def blocked_embeddings(_texts):
        embedding_started.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(embeddings, "aembed_documents", blocked_embeddings)

    async def stream_response():
        run_task = asyncio.create_task(component.build_results())
        try:
            await asyncio.Event().wait()
        finally:
            if not run_task.done():
                run_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await run_task

    with anyio.fail_after(10):
        async with anyio.create_task_group() as task_group:
            task_group.start_soon(stream_response)
            await embedding_started.wait()
            task_group.cancel_scope.cancel()

    await _assert_cancel_restored_kb(client, logged_in_headers, active_user, name, has_documents=True)


@pytest.mark.parametrize("cancel_stage", ["embedding", "write"])
@pytest.mark.parametrize("has_documents", [False, True])
async def test_knowledge_page_cancel_stops_flow_ingestion(
    client, logged_in_headers, active_user, monkeypatch, tmp_path, cancel_stage, has_documents
):
    """Cancelling from the Knowledge page ends the flow's run without marking the KB failed."""
    # A write-stage cancel lands after the embeddings return, so only the
    # recheck under the write lease may catch it; the watcher never polls.
    poll_seconds = 0.05 if cancel_stage == "embedding" else 3600
    monkeypatch.setattr("lfx.components.files_and_knowledge.knowledge.JOB_CANCEL_POLL_SECONDS", poll_seconds)
    name = "page_cancelled_flow_ingestion"
    component, embeddings = await _create_ready_kb(
        client, logged_in_headers, active_user, monkeypatch, tmp_path, name, has_documents=has_documents
    )
    cancel_endpoint = f"/api/v1/knowledge_bases/{name}/cancel"
    embedding_started = asyncio.Event()

    async def blocked_embeddings(_texts):
        embedding_started.set()
        await asyncio.Event().wait()

    async def cancelled_after_embedding(texts):
        response = await client.post(cancel_endpoint, headers=logged_in_headers)
        assert response.status_code == 200, response.text
        return embeddings.embed_documents(texts)

    if cancel_stage == "embedding":
        monkeypatch.setattr(embeddings, "aembed_documents", blocked_embeddings)
    else:
        monkeypatch.setattr(embeddings, "aembed_documents", cancelled_after_embedding)

    task = asyncio.create_task(component.build_results())
    try:
        if cancel_stage == "embedding":
            await asyncio.wait_for(embedding_started.wait(), timeout=10)
            response = await client.get("/api/v1/knowledge_bases", headers=logged_in_headers)
            assert next(kb for kb in response.json() if kb["dir_name"] == name)["status"] == "ingesting"
            response = await client.post(cancel_endpoint, headers=logged_in_headers)
            assert response.status_code == 200, response.text
        with pytest.raises(Exception, match="was cancelled"):
            await asyncio.wait_for(task, timeout=10)
    finally:
        if not task.done():
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task

    await _assert_cancel_restored_kb(client, logged_in_headers, active_user, name, has_documents=has_documents)
    response = await client.get(f"/api/v1/knowledge_bases/{name}/chunks", headers=logged_in_headers)
    assert "interrupted document" not in [chunk["content"] for chunk in response.json()["chunks"]]


async def test_cancelled_upload_keeps_the_kb_status(client, logged_in_headers, active_user, monkeypatch, tmp_path):
    """An upload cancelled from the Knowledge page leaves the KB as it was, not failed."""
    from langflow.api.utils.kb_helpers import KBIngestionHelper
    from langflow.services.database.models.jobs.model import JobType

    name = "cancelled_upload"
    await _create_ready_kb(client, logged_in_headers, active_user, monkeypatch, tmp_path, name, has_documents=True)
    record = await knowledge_base_service.get_by_user_and_name(active_user.id, name)
    job_service = get_job_service()
    job_id = uuid4()
    await job_service.create_job(
        job_id=job_id,
        flow_id=job_id,
        job_type=JobType.INGESTION,
        asset_id=record.id,
        asset_type="knowledge_base",
        user_id=active_user.id,
    )
    await job_service.update_job_status(job_id, JobStatus.CANCELLED)
    monkeypatch.setattr(KBIngestionHelper, "build_embeddings", AsyncMock(return_value=LocalEmbeddings()))

    result = await KBIngestionHelper.perform_ingestion(
        kb_name=name,
        kb_path=None,
        files_data=[("upload.txt", b"uploaded document")],
        chunk_size=100,
        chunk_overlap=0,
        separator="",
        source_name="upload",
        current_user=active_user,
        model_selection={"name": "text-embedding-3-small", "provider": "OpenAI"},
        task_job_id=job_id,
        job_service=job_service,
    )

    assert result["message"] == "Job cancelled"
    record = await knowledge_base_service.get_by_user_and_name(active_user.id, name)
    assert record.status == "ready"
    assert record.failure_reason is None
    endpoint = f"/api/v1/knowledge_bases/{name}"
    response = await client.get(endpoint, headers=logged_in_headers)
    assert response.json()["status"] == "ready"
    response = await client.get("/api/v1/knowledge_bases", headers=logged_in_headers)
    listed = next(kb for kb in response.json() if kb["dir_name"] == name)
    assert listed["status"] == "ready"
    assert listed["last_job_id"] == str(job_id)


async def test_live_flow_ingestion_is_not_swept_as_orphaned(
    client, logged_in_headers, active_user, monkeypatch, tmp_path
):
    """Another worker's orphan sweep must leave a running flow ingestion alone."""
    settings = get_settings_service().settings
    monkeypatch.setattr(settings, "knowledge_bases_dir", str(tmp_path))
    monkeypatch.setattr(settings, "background_heartbeat_interval_s", 0.1)
    # A run whose worker died: the same sweep must still fail it.
    dead_job_id = uuid4()
    await get_job_service().create_job(job_id=dead_job_id, flow_id=dead_job_id, status=JobStatus.IN_PROGRESS)
    monkeypatch.delenv("PGVECTOR_CONNECTION_STRING", raising=False)
    embeddings = LocalEmbeddings()
    monkeypatch.setattr("lfx.components.files_and_knowledge.knowledge.get_embeddings", lambda **_kwargs: embeddings)
    name = "live_flow_ingestion"
    endpoint = f"/api/v1/knowledge_bases/{name}"
    response = await client.post(
        "/api/v1/knowledge_bases",
        json={"name": name, "embedding_provider": "OpenAI", "embedding_model": "text-embedding-3-small"},
        headers=logged_in_headers,
    )
    assert response.status_code == 201, response.text
    component = KnowledgeComponent(
        knowledge_base=name,
        input_df=DataFrame({"text": ["slow document"]}),
        _user_id=active_user.id,
    )
    embedding_started = asyncio.Event()
    release = asyncio.Event()

    async def slow_embeddings(texts):
        embedding_started.set()
        await release.wait()
        return embeddings.embed_documents(texts)

    monkeypatch.setattr(embeddings, "aembed_documents", slow_embeddings)

    task = asyncio.create_task(component.build_kb_info())
    try:
        await asyncio.wait_for(embedding_started.wait(), timeout=10)
        # Outlive the lease and the insert-time heartbeat, so only the run's
        # own keep-alive keeps its job fresh.
        await asyncio.sleep(1.5)
        swept = await get_job_service().sweep_orphans(lease_ttl_s=1.0)
        response = await client.get(f"{endpoint}/runs", headers=logged_in_headers)
        mid_run = response.json()["runs"][0]
    finally:
        release.set()
        await asyncio.wait_for(task, timeout=10)

    assert swept == [dead_job_id]
    assert mid_run["status"] == "running"
    response = await client.get(f"{endpoint}/runs", headers=logged_in_headers)
    run = response.json()["runs"][0]
    assert run["status"] == "succeeded"
    job = await get_job_service().get_job_by_job_id(UUID(run["job_id"]))
    assert job.status == JobStatus.COMPLETED
    assert job.error is None
