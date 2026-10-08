"""Flow ingestion must publish the totals stored in the SQLite knowledge base."""

import asyncio
from uuid import UUID

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
