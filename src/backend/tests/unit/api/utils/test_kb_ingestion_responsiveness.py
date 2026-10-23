"""Synchronous ingestion work must not stop API requests or worker heartbeats."""

import asyncio
import threading
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langflow.api.utils import ingestion_run_service, kb_helpers, knowledge_base_service


@pytest.mark.asyncio
@pytest.mark.parametrize("slow_stage", ["extract_text_from_bytes", "chunk_text_for_ingestion"])
async def test_ingestion_keeps_event_loop_responsive(slow_stage):
    loop_thread = threading.get_ident()
    observed_threads = []
    heartbeat_during_work = threading.Event()
    work_started = threading.Event()
    work_finished = threading.Event()
    real_chunker = kb_helpers.chunk_text_for_ingestion

    def slow_work(*args, **kwargs):
        observed_threads.append(threading.get_ident())
        work_started.set()
        try:
            # The heartbeat must be able to run before this synchronous work
            # returns. A deadline also lets the broken implementation fail cleanly.
            heartbeat_during_work.wait(timeout=2)
            if slow_stage == "extract_text_from_bytes":
                assert args == ("report.txt", b"knowledge base content")
                return "knowledge base content"
            return real_chunker(*args, **kwargs)
        finally:
            work_finished.set()

    async def heartbeat():
        while not work_finished.is_set():
            if work_started.is_set():
                heartbeat_during_work.set()
                return
            await asyncio.sleep(0.005)

    backend = MagicMock()
    backend.add_documents = AsyncMock()
    backend.storage_size_bytes = AsyncMock(return_value=0)
    backend.teardown = AsyncMock()
    job_service = AsyncMock()
    job_service.get_job_by_job_id.return_value = None
    with (
        patch.object(knowledge_base_service, "get_by_user_and_name", new=AsyncMock(return_value=None)),
        patch.object(ingestion_run_service, "create_run", new=AsyncMock(return_value=uuid.uuid4())),
        patch.object(ingestion_run_service, "mark_running", new=AsyncMock()),
        patch.object(ingestion_run_service, "finalize_run", new=AsyncMock()) as finalize,
        patch.object(kb_helpers, "backend_for_name", new=AsyncMock(return_value=backend)),
        patch.object(kb_helpers.KBIngestionHelper, "build_embeddings", new=AsyncMock(return_value=MagicMock())),
        patch.object(kb_helpers.KBAnalysisHelper, "update_text_metrics_via_backend", new=AsyncMock()),
        patch.object(kb_helpers, slow_stage, new=slow_work),
    ):
        pulse = asyncio.create_task(heartbeat())
        try:
            result = await kb_helpers.KBIngestionHelper.perform_ingestion(
                kb_name="responsiveness_test",
                kb_path=None,
                files_data=[("report.txt", b"knowledge base content")],
                chunk_size=100,
                chunk_overlap=0,
                separator="\n",
                source_name="report",
                current_user=SimpleNamespace(id=uuid.uuid4()),
                model_selection={"name": "text-embedding-3-small", "provider": "OpenAI"},
                task_job_id=uuid.uuid4(),
                job_service=job_service,
            )
        finally:
            pulse.cancel()
            await asyncio.gather(pulse, return_exceptions=True)

    assert heartbeat_during_work.is_set(), "Ingestion blocked the event loop"
    assert observed_threads
    assert all(thread != loop_thread for thread in observed_threads)
    assert result["files_processed"] == 1
    assert result["chunks_created"] == 1
    documents = backend.add_documents.await_args.args[0]
    assert documents[0].page_content == "knowledge base content"
    assert documents[0].metadata["file_name"] == "report.txt"
    finalize.assert_awaited_once()
    backend.teardown.assert_awaited_once()
