"""Ingestion into a shared knowledge base must follow the knowledge base owner.

Remote backends name their storage from the owner id plus the knowledge base
name, so the ``user_id`` handed to ``create_backend`` decides where chunks land.
When an authorization plugin lets a collaborator ingest into another user's
knowledge base, the routes resolve the owner through ``_guard_kb_action``; these
tests pin that storage routing, the knowledge base row, and rollback cleanup
follow that owner, while embedding credentials and the ingestion source stay
with the collaborator who started the run.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langflow.api.utils import knowledge_base_service
from langflow.api.utils.kb_helpers import KBIngestionHelper
from lfx.base.knowledge_bases.backends.base import METADATA_KEY_JOB_ID

if TYPE_CHECKING:
    from httpx import AsyncClient

KB_NAME = "shared_kb"
OWNER_CONFIG = {"url_variable": "OPENSEARCH_URL"}
MODEL = {"name": "text-embedding-3-small", "provider": "OpenAI"}


@pytest.fixture
def cross_user_grant():
    """An authorization plugin that shares every knowledge base with the actor."""
    authz = MagicMock()
    authz.supports_cross_user_fetch = AsyncMock(return_value=True)
    authz.is_enabled = AsyncMock(return_value=True)
    authz.enforce = AsyncMock(return_value=True)
    with (
        patch("langflow.services.deps.get_authorization_service", return_value=authz),
        patch("langflow.api.v1.knowledge_bases.ensure_knowledge_base_permission", new=AsyncMock()),
    ):
        yield authz


@pytest.fixture
async def owners_kb(user_two):
    """``user_two`` owns an OpenSearch knowledge base the actor has no row for."""
    return await knowledge_base_service.create_record(
        user_id=user_two.id,
        name=KB_NAME,
        model_selection=MODEL,
        backend_type="opensearch",
        backend_config=OWNER_CONFIG,
    )


@pytest.fixture
def task_service():
    ts = MagicMock()
    ts.fire_and_forget_task = AsyncMock()
    with (
        patch("langflow.api.v1.knowledge_bases.get_task_service", return_value=ts),
        patch("langflow.api.v1.knowledge_bases.get_job_service", return_value=AsyncMock()),
    ):
        yield ts


def _fake_backend() -> MagicMock:
    backend = MagicMock()
    backend.add_documents = AsyncMock()
    backend.teardown = AsyncMock()
    return backend


async def _run_dispatched_ingestion(task_service: MagicMock, *, add_documents_error: Exception | None = None):
    """Run the ``perform_ingestion`` call a route dispatched, with storage mocked out."""
    dispatched = dict(task_service.fire_and_forget_task.await_args.kwargs)
    run = dispatched.pop("run_coro_func")
    dispatched.pop("job_id")
    backend = _fake_backend()
    if add_documents_error is not None:
        backend.add_documents.side_effect = add_documents_error
    with (
        patch("langflow.api.utils.kb_helpers.create_backend", return_value=backend) as create_backend,
        patch(
            "langflow.api.utils.kb_helpers.KBIngestionHelper.build_embeddings", new=AsyncMock(return_value=MagicMock())
        ) as build_embeddings,
        patch(
            "langflow.api.utils.kb_helpers.KBIngestionHelper.cleanup_chroma_chunks_by_job", new=AsyncMock()
        ) as cleanup,
        patch("langflow.api.utils.kb_helpers.KBAnalysisHelper.update_text_metrics_via_backend", new=AsyncMock()),
        patch(
            "langflow.api.utils.ingestion_run_service.create_run", new=AsyncMock(return_value=uuid.uuid4())
        ) as run_row,
        patch("langflow.api.utils.ingestion_run_service.mark_running", new=AsyncMock()),
        patch("langflow.api.utils.ingestion_run_service.finalize_run", new=AsyncMock()),
    ):
        if add_documents_error is None:
            await run(**dispatched)
        else:
            with pytest.raises(type(add_documents_error)):
                await run(**dispatched)
    return SimpleNamespace(
        create_backend=create_backend,
        build_embeddings=build_embeddings,
        cleanup=cleanup,
        run_row=run_row,
        dispatched=dispatched,
    )


def _assert_routed_to_owner(result: SimpleNamespace, *, owner, actor, owners_kb) -> None:
    result.create_backend.assert_called_once()
    assert result.create_backend.call_args.args == ("opensearch",)
    assert result.create_backend.call_args.kwargs["backend_config"] == OWNER_CONFIG
    assert result.create_backend.call_args.kwargs["user_id"] == owner.id
    assert result.run_row.await_args.kwargs["kb_id"] == owners_kb.id
    # The collaborator's own model credentials pay for the embeddings.
    assert result.build_embeddings.await_args.args[2].id == actor.id


@pytest.mark.usefixtures("cross_user_grant")
async def test_file_ingest_writes_to_the_owners_storage(
    client: AsyncClient, logged_in_headers, active_user, user_two, owners_kb, task_service
):
    response = await client.post(
        f"api/v1/knowledge_bases/{KB_NAME}/ingest",
        headers=logged_in_headers,
        files={"files": ("notes.txt", b"shared knowledge base content", "text/plain")},
        data={"source_name": "notes", "chunk_size": "100", "chunk_overlap": "0"},
    )
    assert response.status_code == 200, response.text

    result = await _run_dispatched_ingestion(task_service)

    _assert_routed_to_owner(result, owner=user_two, actor=active_user, owners_kb=owners_kb)


@pytest.mark.usefixtures("cross_user_grant")
async def test_file_ingest_rollback_cleans_the_owners_storage(
    client: AsyncClient, logged_in_headers, user_two, owners_kb, task_service
):
    response = await client.post(
        f"api/v1/knowledge_bases/{KB_NAME}/ingest",
        headers=logged_in_headers,
        files={"files": ("notes.txt", b"shared knowledge base content", "text/plain")},
        data={"source_name": "notes", "chunk_size": "100", "chunk_overlap": "0"},
    )
    assert response.status_code == 200, response.text

    result = await _run_dispatched_ingestion(task_service, add_documents_error=RuntimeError("write failed"))

    result.cleanup.assert_awaited_once()
    assert result.cleanup.await_args.kwargs["user_id"] == user_two.id
    assert result.cleanup.await_args.kwargs["backend_type"] == "opensearch"
    assert result.cleanup.await_args.kwargs["backend_config"] == owners_kb.backend_config


@pytest.fixture
def folder_settings(tmp_path):
    allowed_root = tmp_path / "allowed"
    folder = allowed_root / "docs"
    folder.mkdir(parents=True)
    (folder / "readme.md").write_text("shared knowledge base content")
    settings = SimpleNamespace(
        settings=SimpleNamespace(kb_allowed_folder_roots=[str(allowed_root)], kb_folder_max_file_size_bytes=4096)
    )
    with patch("langflow.api.v1.knowledge_bases.get_settings_service", return_value=settings):
        yield folder


@pytest.mark.usefixtures("cross_user_grant")
async def test_folder_ingest_writes_to_the_owners_storage(
    client: AsyncClient, logged_in_headers, active_user, user_two, owners_kb, task_service, folder_settings
):
    response = await client.post(
        f"api/v1/knowledge_bases/{KB_NAME}/ingest/folder",
        headers=logged_in_headers,
        json={"path": str(folder_settings), "chunk_size": 500, "chunk_overlap": 0},
    )
    assert response.status_code == 200, response.text

    result = await _run_dispatched_ingestion(task_service)

    _assert_routed_to_owner(result, owner=user_two, actor=active_user, owners_kb=owners_kb)
    # The folder is read with the collaborator's access, not the owner's.
    assert result.dispatched["source"].user_id == active_user.id


@pytest.mark.usefixtures("cross_user_grant")
async def test_connector_ingest_writes_to_the_owners_storage(
    client: AsyncClient, logged_in_headers, active_user, user_two, owners_kb, task_service, folder_settings
):
    response = await client.post(
        f"api/v1/knowledge_bases/{KB_NAME}/ingest/connector",
        headers=logged_in_headers,
        json={"source_type": "folder", "source_config": {"path": str(folder_settings)}},
    )
    assert response.status_code == 200, response.text

    result = await _run_dispatched_ingestion(task_service)

    _assert_routed_to_owner(result, owner=user_two, actor=active_user, owners_kb=owners_kb)
    assert result.dispatched["source"].user_id == active_user.id


@pytest.mark.usefixtures("cross_user_grant")
async def test_cancel_cleans_the_owners_storage(client: AsyncClient, logged_in_headers, user_two, owners_kb):
    job = SimpleNamespace(job_id=uuid.uuid4(), status=SimpleNamespace(value="in_progress"))
    job_service = MagicMock()
    job_service.get_latest_jobs_by_asset_ids = AsyncMock(return_value={owners_kb.id: job})
    job_service.update_job_status = AsyncMock()
    task_service = MagicMock()
    task_service.revoke_task = AsyncMock(return_value=True)

    from langflow.services.deps import get_service
    from langflow.services.schema import ServiceType

    def service(service_type, default=None):
        if service_type == ServiceType.JOB_SERVICE:
            return job_service
        if service_type == ServiceType.TASK_SERVICE:
            return task_service
        return get_service(service_type, default)

    with (
        patch("langflow.services.deps.get_service", side_effect=service),
        patch(
            "langflow.api.v1.knowledge_bases.KBIngestionHelper.cleanup_chroma_chunks_by_job", new=AsyncMock()
        ) as cleanup,
    ):
        response = await client.post(f"api/v1/knowledge_bases/{KB_NAME}/cancel", headers=logged_in_headers)

    assert response.status_code == 200, response.text
    cleanup.assert_awaited_once()
    assert cleanup.await_args.args[0] == job.job_id
    assert cleanup.await_args.kwargs["user_id"] == user_two.id
    assert cleanup.await_args.kwargs["backend_type"] == "opensearch"
    assert cleanup.await_args.kwargs["backend_config"] == OWNER_CONFIG


async def test_cleanup_deletes_by_job_id_through_the_given_owner():
    job_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    backend = MagicMock()
    backend.delete_by = AsyncMock()
    backend.teardown = AsyncMock()
    with patch("langflow.api.utils.kb_helpers.create_backend", return_value=backend) as create_backend:
        await KBIngestionHelper.cleanup_chroma_chunks_by_job(
            job_id, None, KB_NAME, backend_type="opensearch", backend_config=OWNER_CONFIG, user_id=owner_id
        )
    assert create_backend.call_args.kwargs["user_id"] == owner_id
    backend.delete_by.assert_awaited_once_with({METADATA_KEY_JOB_ID: str(job_id)})


async def test_deleting_a_kb_cancels_a_collaborators_inflight_ingestion(
    client: AsyncClient, logged_in_headers, active_user, user_two
):
    """The owner deleting a knowledge base must stop ingestion a collaborator started.

    Otherwise the collaborator's run keeps writing into the deleted knowledge
    base's storage after its row is gone.
    """
    from langflow.services.database.models.jobs.model import JobStatus, JobType
    from langflow.services.deps import get_job_service

    record = await knowledge_base_service.create_record(
        user_id=active_user.id,
        name=KB_NAME,
        model_selection=MODEL,
        backend_type="opensearch",
        backend_config=OWNER_CONFIG,
    )
    job_service = get_job_service()
    job_id = uuid.uuid4()
    await job_service.create_job(
        job_id=job_id,
        flow_id=job_id,
        job_type=JobType.INGESTION,
        asset_id=record.id,
        asset_type="knowledge_base",
        user_id=user_two.id,
    )
    await job_service.update_job_status(job_id, JobStatus.IN_PROGRESS)

    with patch("langflow.api.v1.knowledge_bases._delete_remote_backend_collection", new=AsyncMock(return_value=None)):
        response = await client.delete(f"api/v1/knowledge_bases/{KB_NAME}", headers=logged_in_headers)

    assert response.status_code == 200, response.text
    job = await job_service.get_job_by_job_id(job_id)
    assert job.status == JobStatus.CANCELLED
