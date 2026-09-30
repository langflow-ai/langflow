"""Tests for KB ingestion-run persistence on the unified ``job`` table.

Post-unification, ingestion runs no longer have their own table — the
lifecycle data lives on ``Job.job_metadata``. These tests pin the
contract: ``create_run``, ``mark_running`` and ``finalize_run`` patch
the right keys onto the parent job's metadata, and the read-side
projection (``RunRow`` via ``get_run`` / ``list_runs_for_kb``) returns
the same shape the legacy ``IngestionRun`` row produced.
"""

from __future__ import annotations

import uuid

import pytest
from langflow.api.utils import ingestion_run_service
from langflow.services.database.models.jobs.model import Job, JobStatus, JobType
from langflow.services.deps import session_scope
from lfx.base.knowledge_bases.ingestion_sources.base import (
    IngestionItemResult,
    IngestionItemStatus,
    IngestionRunStatus,
    IngestionSummary,
    SourceType,
)


class _FakeSource:
    """Minimal stand-in for ``KBIngestionSource``.

    The service reads only ``source_type`` and ``describe()`` — keeps
    the test independent of the concrete file-upload / cloud-connector
    source classes.
    """

    def __init__(self, *, source_type: SourceType, config: dict | None = None) -> None:
        self.source_type = source_type
        self._config = config or {"source_name": "demo"}

    def describe(self) -> dict:
        return {"config": self._config}


async def _insert_job(*, job_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """Insert a Job row so the service has a target to update."""
    async with session_scope() as session:
        session.add(
            Job(
                job_id=job_id,
                flow_id=job_id,
                status=JobStatus.IN_PROGRESS,
                type=JobType.INGESTION,
                user_id=user_id,
            )
        )
        await session.commit()


async def _read_job_metadata(job_id: uuid.UUID) -> dict | None:
    async with session_scope() as session:
        job = await session.get(Job, job_id)
        return None if job is None else job.job_metadata


@pytest.mark.usefixtures("client")
class TestCreateRun:
    async def test_seeds_initial_metadata_on_job(self, active_user) -> None:
        job_id = uuid.uuid4()
        await _insert_job(job_id=job_id, user_id=active_user.id)

        returned = await ingestion_run_service.create_run(
            kb_name="kb_alpha",
            source=_FakeSource(source_type=SourceType.FILE_UPLOAD),
            job_id=job_id,
            user_id=active_user.id,
            kb_id=None,
        )
        # ``create_run`` returns the job_id so the caller can use it as
        # the legacy run_id handle.
        assert returned == job_id

        metadata = await _read_job_metadata(job_id)
        assert metadata is not None
        assert metadata["kind"] == "kb_ingestion"
        assert metadata["kb_name"] == "kb_alpha"
        assert metadata["source_type"] == SourceType.FILE_UPLOAD.value
        assert metadata["status"] == IngestionRunStatus.PENDING.value
        # ``ingestion_run_id`` is preserved as an alias of job_id so any
        # downstream code reading it doesn't have to know the unification
        # happened.
        assert metadata["ingestion_run_id"] == str(job_id)

    async def test_skips_when_job_id_is_none(self, active_user) -> None:
        # Defensive: no current call site hits this, but the service
        # no-ops cleanly rather than crashing.
        result = await ingestion_run_service.create_run(
            kb_name="kb_beta",
            source=_FakeSource(source_type=SourceType.FILE_UPLOAD),
            job_id=None,
            user_id=active_user.id,
        )
        assert result is None

    async def test_swallows_missing_job_row(self, active_user) -> None:
        # A stale or never-persisted job_id must not crash the helper.
        ghost_job = uuid.uuid4()
        result = await ingestion_run_service.create_run(
            kb_name="kb_gamma",
            source=_FakeSource(source_type=SourceType.FILE_UPLOAD),
            job_id=ghost_job,
            user_id=active_user.id,
        )
        # Returns the job_id (caller will hand it to mark_running which
        # also no-ops when the row is missing).
        assert result == ghost_job
        assert await _read_job_metadata(ghost_job) is None


@pytest.mark.usefixtures("client")
class TestMarkRunning:
    async def test_transitions_status(self, active_user) -> None:
        job_id = uuid.uuid4()
        await _insert_job(job_id=job_id, user_id=active_user.id)
        await ingestion_run_service.create_run(
            kb_name="kb_run",
            source=_FakeSource(source_type=SourceType.FILE_UPLOAD),
            job_id=job_id,
            user_id=active_user.id,
        )

        await ingestion_run_service.mark_running(job_id)

        metadata = await _read_job_metadata(job_id)
        assert metadata is not None
        assert metadata["status"] == IngestionRunStatus.RUNNING.value
        # Earlier keys survive the shallow merge.
        assert metadata["kind"] == "kb_ingestion"
        assert metadata["kb_name"] == "kb_run"


@pytest.mark.usefixtures("client")
class TestFinalizeRun:
    async def test_writes_counters_and_items(self, active_user) -> None:
        job_id = uuid.uuid4()
        await _insert_job(job_id=job_id, user_id=active_user.id)
        await ingestion_run_service.create_run(
            kb_name="kb_done",
            source=_FakeSource(source_type=SourceType.FILE_UPLOAD),
            job_id=job_id,
            user_id=active_user.id,
        )
        await ingestion_run_service.mark_running(job_id)

        summary = IngestionSummary(
            kb_name="kb_done",
            source_type=SourceType.FILE_UPLOAD.value,
            user_id=active_user.id,
            job_id=job_id,
            source_config={"source_name": "demo"},
        )
        summary.items = [
            IngestionItemResult(
                item_id="0:a.txt",
                display_name="a.txt",
                status=IngestionItemStatus.SUCCEEDED,
                chunks_created=3,
            ),
            IngestionItemResult(
                item_id="1:b.txt",
                display_name="b.txt",
                status=IngestionItemStatus.FAILED,
                error_message="boom",
            ),
        ]
        summary.total_items = 2
        summary.succeeded = 1
        summary.failed = 1
        summary.skipped = 0
        summary.total_bytes = 2048
        summary.chunks_created = 3

        await ingestion_run_service.finalize_run(
            job_id,
            summary=summary,
            status=IngestionRunStatus.PARTIAL,
            error_message=None,
        )

        metadata = await _read_job_metadata(job_id)
        assert metadata is not None
        assert metadata["status"] == IngestionRunStatus.PARTIAL.value
        assert metadata["total_items"] == 2
        assert metadata["succeeded"] == 1
        assert metadata["failed"] == 1
        assert metadata["chunks_created"] == 3
        assert metadata["total_bytes"] == 2048
        assert metadata["error_message"] is None
        # Items are serialised (not raw dataclasses).
        assert isinstance(metadata["items"], list)
        assert len(metadata["items"]) == 2
        assert metadata["items"][0]["item_id"] == "0:a.txt"
        assert metadata["items"][0]["status"] == "succeeded"
        assert metadata["items"][1]["status"] == "failed"
        # ``finished_at`` is an ISO string so it survives JSON
        # round-trip into the JSON column.
        assert isinstance(metadata["finished_at"], str)


@pytest.mark.usefixtures("client")
class TestRunRowProjection:
    """Read-side: ``get_run`` and ``list_runs_for_kb`` build RunRow."""

    async def test_get_run_returns_runrow_for_owner(self, active_user) -> None:
        job_id = uuid.uuid4()
        await _insert_job(job_id=job_id, user_id=active_user.id)
        await ingestion_run_service.create_run(
            kb_name="kb_get",
            source=_FakeSource(source_type=SourceType.FILE_UPLOAD),
            job_id=job_id,
            user_id=active_user.id,
        )

        row = await ingestion_run_service.get_run(job_id, user_id=active_user.id)
        assert row is not None
        assert row.id == job_id
        assert row.job_id == job_id
        assert row.kb_name == "kb_get"
        assert row.status == IngestionRunStatus.PENDING.value
        # Items default to empty until finalize runs.
        assert row.items == []

    async def test_get_run_returns_none_for_other_user(self, active_user) -> None:
        job_id = uuid.uuid4()
        await _insert_job(job_id=job_id, user_id=active_user.id)
        await ingestion_run_service.create_run(
            kb_name="kb_authz",
            source=_FakeSource(source_type=SourceType.FILE_UPLOAD),
            job_id=job_id,
            user_id=active_user.id,
        )

        row = await ingestion_run_service.get_run(job_id, user_id=uuid.uuid4())
        assert row is None

    async def test_get_run_filters_by_job_type(self, active_user) -> None:
        # A workflow job_id submitted to a KB-runs endpoint must 404.
        wf_job_id = uuid.uuid4()
        async with session_scope() as session:
            session.add(
                Job(
                    job_id=wf_job_id,
                    flow_id=wf_job_id,
                    status=JobStatus.COMPLETED,
                    type=JobType.WORKFLOW,
                    user_id=active_user.id,
                    job_metadata={"kb_name": "kb_wrong_type"},
                )
            )
            await session.commit()

        row = await ingestion_run_service.get_run(wf_job_id, user_id=active_user.id)
        assert row is None

    async def test_list_runs_for_kb_filters_and_paginates(self, active_user) -> None:
        """Legacy fallback: KB has no DB record, query falls back to JSON-extract on kb_name.

        Seeds Jobs but never creates a ``KnowledgeBaseRecord``, so
        ``list_runs_for_kb`` resolves ``kb_record`` to ``None`` and uses
        the JSON-extract path.
        """
        for _ in range(3):
            jid = uuid.uuid4()
            await _insert_job(job_id=jid, user_id=active_user.id)
            await ingestion_run_service.create_run(
                kb_name="kb_a",
                source=_FakeSource(source_type=SourceType.FILE_UPLOAD),
                job_id=jid,
                user_id=active_user.id,
            )
        other = uuid.uuid4()
        await _insert_job(job_id=other, user_id=active_user.id)
        await ingestion_run_service.create_run(
            kb_name="kb_b",
            source=_FakeSource(source_type=SourceType.FILE_UPLOAD),
            job_id=other,
            user_id=active_user.id,
        )

        rows, total = await ingestion_run_service.list_runs_for_kb(
            kb_name="kb_a",
            user_id=active_user.id,
            page=1,
            limit=2,
        )
        assert total == 3
        assert len(rows) == 2
        assert all(r.kb_name == "kb_a" for r in rows)

    async def test_list_runs_for_kb_uses_indexed_asset_id_when_record_exists(self, active_user) -> None:
        """Indexed path activates when a ``KnowledgeBaseRecord`` exists.

        With a record present the query filters on ``Job.asset_id``
        (btree-indexed) instead of doing a JSON-extract on
        ``Job.job_metadata.kb_name``.

        Verified by giving two Jobs the *same* ``kb_name`` in metadata
        but different ``asset_id`` values (one matching the kb_record,
        one a stranger). The indexed filter must surface only the
        kb_record-matched run.
        """
        from langflow.api.utils import knowledge_base_service

        # Create a real KB record so the indexed path activates.
        kb_record = await knowledge_base_service.create_record(
            user_id=active_user.id,
            name="kb_indexed",
            model_selection={"name": "model", "provider": "HuggingFace"},
        )

        # Job linked to the KB record via asset_id — should be returned.
        owned_job_id = uuid.uuid4()
        async with session_scope() as session:
            session.add(
                Job(
                    job_id=owned_job_id,
                    flow_id=owned_job_id,
                    status=JobStatus.COMPLETED,
                    type=JobType.INGESTION,
                    user_id=active_user.id,
                    asset_id=kb_record.id,
                    asset_type="knowledge_base",
                    job_metadata={"kind": "kb_ingestion", "kb_name": "kb_indexed"},
                )
            )
            await session.commit()

        # Stranger Job with the same kb_name in metadata but a
        # different asset_id — must NOT be returned because the
        # asset_id filter excludes it.
        stranger_job_id = uuid.uuid4()
        async with session_scope() as session:
            session.add(
                Job(
                    job_id=stranger_job_id,
                    flow_id=stranger_job_id,
                    status=JobStatus.COMPLETED,
                    type=JobType.INGESTION,
                    user_id=active_user.id,
                    asset_id=uuid.uuid4(),  # different from kb_record.id
                    asset_type="knowledge_base",
                    job_metadata={"kind": "kb_ingestion", "kb_name": "kb_indexed"},
                )
            )
            await session.commit()

        rows, total = await ingestion_run_service.list_runs_for_kb(
            kb_name="kb_indexed",
            user_id=active_user.id,
        )
        ids = {r.id for r in rows}
        assert owned_job_id in ids
        assert stranger_job_id not in ids
        assert total == 1


class TestPrivatePatchHelper:
    """Direct exercise of ``_patch_job_metadata`` merge semantics."""

    async def test_creates_metadata_when_absent(self, active_user) -> None:
        job_id = uuid.uuid4()
        await _insert_job(job_id=job_id, user_id=active_user.id)
        await ingestion_run_service._patch_job_metadata(job_id, {"a": 1, "b": 2})
        assert await _read_job_metadata(job_id) == {"a": 1, "b": 2}

    async def test_shallow_merges_existing_keys(self, active_user) -> None:
        job_id = uuid.uuid4()
        await _insert_job(job_id=job_id, user_id=active_user.id)
        await ingestion_run_service._patch_job_metadata(job_id, {"a": 1, "b": 2})
        await ingestion_run_service._patch_job_metadata(job_id, {"b": 99, "c": 3})
        assert await _read_job_metadata(job_id) == {"a": 1, "b": 99, "c": 3}

    async def test_swallows_missing_job(self) -> None:
        # No exception, no Job row created — silent no-op.
        await ingestion_run_service._patch_job_metadata(uuid.uuid4(), {"a": 1})
