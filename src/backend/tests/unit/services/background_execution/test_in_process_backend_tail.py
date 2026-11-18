"""In-process reattachment uses durable terminal history and ends when its job disappears."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest
from langflow.services.background_execution.in_process_backend import InProcessBackend
from langflow.services.background_execution.live_bus import InMemoryLiveBus, LiveFrame
from langflow.services.database.models.jobs.model import JobStatus


class _JobStore:
    def __init__(self, job, rows, *, on_read=None):
        self.job = job
        self.rows = rows
        self.on_read = on_read

    async def get_job_by_job_id(self, _job_id):
        return self.job

    async def read_events(self, _job_id, *, after_seq=0):
        rows = [row for row in self.rows if row.seq > after_seq]
        if self.on_read is not None:
            await self.on_read()
        return rows


def _backend(monkeypatch, store, bus):
    monkeypatch.setattr("langflow.services.deps.get_job_service", lambda: store)
    return InProcessBackend(
        executor=None,
        bus=bus,
        settings=None,
        owner=None,
        get_frame_source_factory=lambda: None,
    )


async def _collect(backend, job_id, *, last_seq=0):
    return [
        frame
        async for frame in backend.tail(
            str(job_id), last_seq=last_seq, frame_row=lambda row: f"wire:{row.payload}".encode()
        )
    ]


async def test_tail_ends_when_the_job_is_already_missing(monkeypatch):
    backend = _backend(monkeypatch, _JobStore(None, []), InMemoryLiveBus())

    assert await asyncio.wait_for(_collect(backend, uuid4()), timeout=1) == []


async def test_tail_ends_when_the_job_disappears_during_replay(monkeypatch):
    store = _JobStore(SimpleNamespace(status=JobStatus.IN_PROGRESS), [SimpleNamespace(seq=1, payload="saved")])

    async def delete_job():
        store.job = None
        store.rows = []

    store.on_read = delete_job
    backend = _backend(monkeypatch, store, InMemoryLiveBus())

    assert await asyncio.wait_for(_collect(backend, uuid4()), timeout=2) == [b"wire:saved"]


@pytest.mark.parametrize(
    "status",
    [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED, JobStatus.TIMED_OUT, JobStatus.SUSPENDED],
)
async def test_finished_tail_replays_only_durable_rows_after_the_cursor(monkeypatch, status):
    job_id = uuid4()
    bus = InMemoryLiveBus()

    async def publish_late_local_frame():
        await bus.publish(str(job_id), LiveFrame(seq=3, data=b"late-local-frame"))

    rows = [SimpleNamespace(seq=1, payload="before-cursor"), SimpleNamespace(seq=2, payload="terminal")]
    store = _JobStore(SimpleNamespace(status=status), rows, on_read=publish_late_local_frame)
    backend = _backend(monkeypatch, store, bus)

    assert await asyncio.wait_for(_collect(backend, job_id, last_seq=1), timeout=2) == [b"wire:terminal"]


async def test_finished_tail_with_an_exhausted_cursor_returns_no_frames(monkeypatch):
    store = _JobStore(SimpleNamespace(status=JobStatus.COMPLETED), [SimpleNamespace(seq=1, payload="saved")])
    backend = _backend(monkeypatch, store, InMemoryLiveBus())

    assert await asyncio.wait_for(_collect(backend, uuid4(), last_seq=1), timeout=2) == []
