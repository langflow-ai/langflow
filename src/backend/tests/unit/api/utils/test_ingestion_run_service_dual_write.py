"""Tests for the dual-write of ``ingestion_run`` to ``job.job_metadata``.

The expand-contract path toward unifying KB ingestion tracking on the
``job`` table writes the same lifecycle data to both rows. These
tests pin that contract: ``ingestion_run`` rows continue to be written
exactly as before, and a parallel ``job.job_metadata`` mirror is kept
in sync. Component-path ingestions (no ``job_id``) skip the mirror
without raising.
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest
from langflow.api.utils import ingestion_run_service
from langflow.services.database.models.ingestion_run import IngestionRun, IngestionRunStatus
from langflow.services.database.models.jobs.model import Job, JobStatus, JobType
from langflow.services.deps import session_scope
from lfx.base.knowledge_bases.ingestion_sources.base import (
    IngestionItemResult,
    IngestionItemStatus,
    IngestionSummary,
    SourceType,
)


class _FakeSource:
    """Minimal stand-in for ``KBIngestionSource``.

    The dual-write reads only ``source_type`` and ``describe()`` so a
    full source isn't needed — keeps the test independent of the
    concrete file-upload / cloud-connector source classes.
    """

    def __init__(self, *, source_type: SourceType, config: dict | None = None) -> None:
        self.source_type = source_type
        self._config = config or {"source_name": "demo"}

    def describe(self) -> dict:
        return {"config": self._config}


async def _insert_job(*, job_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """Insert a Job row so the mirror has a target to update."""
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


async def _read_run_status(run_id: uuid.UUID) -> str | None:
    async with session_scope() as session:
        row = await session.get(IngestionRun, run_id)
        return None if row is None else row.status


@pytest.mark.usefixtures("client")
class TestCreateRunDualWrite:
    async def test_writes_initial_metadata_to_job(self, active_user) -> None:
        job_id = uuid.uuid4()
        await _insert_job(job_id=job_id, user_id=active_user.id)

        run_id = await ingestion_run_service.create_run(
            kb_name="kb_alpha",
            source=_FakeSource(source_type=SourceType.FILE_UPLOAD),
            job_id=job_id,
            user_id=active_user.id,
            kb_id=None,
        )

        # ``ingestion_run`` row exists and is PENDING — legacy path
        # untouched.
        assert await _read_run_status(run_id) == IngestionRunStatus.PENDING.value

        # ``job.job_metadata`` mirrors the same row.
        metadata = await _read_job_metadata(job_id)
        assert metadata is not None
        assert metadata["kind"] == "kb_ingestion"
        assert metadata["ingestion_run_id"] == str(run_id)
        assert metadata["kb_name"] == "kb_alpha"
        assert metadata["source_type"] == SourceType.FILE_UPLOAD.value
        assert metadata["status"] == IngestionRunStatus.PENDING.value

    async def test_skips_mirror_when_job_id_is_none(self, active_user) -> None:
        # Component-path ingestions don't have a Job row. The mirror
        # must not crash — it just no-ops.
        run_id = await ingestion_run_service.create_run(
            kb_name="kb_beta",
            source=_FakeSource(source_type=SourceType.FILE_UPLOAD),
            job_id=None,
            user_id=active_user.id,
        )
        assert await _read_run_status(run_id) == IngestionRunStatus.PENDING.value

    async def test_swallows_missing_job_row(self, active_user) -> None:
        # If the job_id is set but the row is missing (clock skew,
        # explicit delete, test fixtures), the run still records.
        ghost_job = uuid.uuid4()
        run_id = await ingestion_run_service.create_run(
            kb_name="kb_gamma",
            source=_FakeSource(source_type=SourceType.FILE_UPLOAD),
            job_id=ghost_job,
            user_id=active_user.id,
        )
        assert await _read_run_status(run_id) == IngestionRunStatus.PENDING.value
        assert await _read_job_metadata(ghost_job) is None  # never created


@pytest.mark.usefixtures("client")
class TestMarkRunningDualWrite:
    async def test_propagates_status_to_job(self, active_user) -> None:
        job_id = uuid.uuid4()
        await _insert_job(job_id=job_id, user_id=active_user.id)
        run_id = await ingestion_run_service.create_run(
            kb_name="kb_run",
            source=_FakeSource(source_type=SourceType.FILE_UPLOAD),
            job_id=job_id,
            user_id=active_user.id,
        )

        await ingestion_run_service.mark_running(run_id)

        assert await _read_run_status(run_id) == IngestionRunStatus.RUNNING.value
        metadata = await _read_job_metadata(job_id)
        assert metadata is not None
        assert metadata["status"] == IngestionRunStatus.RUNNING.value
        # Earlier keys survive the shallow merge.
        assert metadata["kind"] == "kb_ingestion"


@pytest.mark.usefixtures("client")
class TestFinalizeRunDualWrite:
    async def test_writes_counters_and_items_to_job(self, active_user) -> None:
        job_id = uuid.uuid4()
        await _insert_job(job_id=job_id, user_id=active_user.id)
        run_id = await ingestion_run_service.create_run(
            kb_name="kb_done",
            source=_FakeSource(source_type=SourceType.FILE_UPLOAD),
            job_id=job_id,
            user_id=active_user.id,
        )
        await ingestion_run_service.mark_running(run_id)

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
            run_id,
            summary=summary,
            status=IngestionRunStatus.PARTIAL,
            error_message=None,
        )

        # Legacy table reflects the final state…
        assert await _read_run_status(run_id) == IngestionRunStatus.PARTIAL.value

        # …and so does the mirror.
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
        # round-trip into the DB column.
        assert isinstance(metadata["finished_at"], str)


class TestUpdateJobMetadataHelper:
    """Exercises ``JobService.update_job_metadata`` directly."""

    async def test_merges_into_empty_metadata(self, active_user) -> None:
        from langflow.services.deps import get_job_service

        job_id = uuid.uuid4()
        await _insert_job(job_id=job_id, user_id=active_user.id)
        svc = get_job_service()
        if svc is None:  # service not wired in this test profile
            pytest.skip("job service unavailable in test profile")

        result = await svc.update_job_metadata(job_id, {"a": 1, "b": 2})
        assert result is not None
        assert result.job_metadata == {"a": 1, "b": 2}

    async def test_shallow_merges_with_existing(self, active_user) -> None:
        from langflow.services.deps import get_job_service

        job_id = uuid.uuid4()
        await _insert_job(job_id=job_id, user_id=active_user.id)
        svc = get_job_service()
        if svc is None:
            pytest.skip("job service unavailable in test profile")

        await svc.update_job_metadata(job_id, {"a": 1, "b": 2})
        await svc.update_job_metadata(job_id, {"b": 99, "c": 3})

        result = await svc.update_job_metadata(job_id, {})
        assert result is not None
        assert result.job_metadata == {"a": 1, "b": 99, "c": 3}

    async def test_replace_overwrites_existing(self, active_user) -> None:
        from langflow.services.deps import get_job_service

        job_id = uuid.uuid4()
        await _insert_job(job_id=job_id, user_id=active_user.id)
        svc = get_job_service()
        if svc is None:
            pytest.skip("job service unavailable in test profile")

        await svc.update_job_metadata(job_id, {"a": 1, "b": 2})
        await svc.update_job_metadata(job_id, {"only": "this"}, replace=True)

        result = await svc.update_job_metadata(job_id, {})
        # ``replace=True`` clears prior keys; the empty patch on the
        # final read merges nothing (because ``replace`` defaults to
        # False but the dict is empty anyway).
        assert result is not None
        assert result.job_metadata == {"only": "this"}

    async def test_returns_none_for_missing_job(self) -> None:
        from langflow.services.deps import get_job_service

        svc = get_job_service()
        if svc is None:
            pytest.skip("job service unavailable in test profile")

        result = await svc.update_job_metadata(uuid.uuid4(), {"a": 1})
        assert result is None


def _unused_imports() -> None:
    """Keep MagicMock import alive for future test extensions."""
    _ = MagicMock
