"""Background worker that runs approved erase requests, one replica at a time.

A named lease (the generic ``trigger_lease`` table) makes the worker a singleton across replicas;
the holder renews it between batches, and any replica takes over once it expires.
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING

from lfx.log.logger import logger
from sqlmodel import col, select

from langflow.api.utils.migration_pause import is_paused, writing
from langflow.services.data_subjects.engine import RUNNABLE, is_retry_due, run_request
from langflow.services.data_subjects.expiry import approve_expired_requests
from langflow.services.database.models.data_subject_request import DataSubjectRequest
from langflow.services.deps import session_scope
from langflow.services.triggers import leases

if TYPE_CHECKING:
    from uuid import UUID

LEASE_NAME = "data_subject_eraser"
LEASE_TTL_SECONDS = 120.0
IDLE_INTERVAL_SECONDS = 5.0
CANDIDATE_BATCH = 50


class DataSubjectEraseWorker:
    def __init__(self, *, interval: float = IDLE_INTERVAL_SECONDS) -> None:
        self._interval = interval
        self._stop = asyncio.Event()
        self._wake = asyncio.Event()
        self._task: asyncio.Task | None = None
        self._owner = leases.new_owner_token("dsr")

    def notify(self) -> None:
        """Ask the loop to look for work now instead of waiting for the next tick."""
        self._wake.set()

    async def start(self) -> None:
        if self._task is not None:
            return
        # Events bind to the loop that first awaits them; an app restarted in the same process runs a new loop.
        self._stop = asyncio.Event()
        self._wake = asyncio.Event()
        self._owner = leases.new_owner_token("dsr")
        self._task = asyncio.create_task(self._run(), name="data-subject-eraser")

    async def stop(self) -> None:
        if self._task is None:
            return
        self._stop.set()
        self._wake.set()
        with contextlib.suppress(asyncio.CancelledError):
            await self._task
        self._task = None
        with contextlib.suppress(Exception):
            async with session_scope() as session:
                await leases.release(session, name=LEASE_NAME, owner=self._owner)

    async def _run(self) -> None:
        while not self._stop.is_set():
            try:
                # A pass holds a place, so a pause waits for the erase that is under way.
                with writing(name="data_subject_eraser") as let_in:
                    if let_in:
                        await self.run_once()
            except Exception as exc:  # noqa: BLE001 - the loop must survive a transient database outage
                await logger.awarning("op=data_subject_worker tick failed: %s", type(exc).__name__)
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(self._wake.wait(), timeout=self._interval)
            self._wake.clear()

    async def _renew(self) -> None:
        async with session_scope() as session:
            if not await leases.acquire(session, name=LEASE_NAME, owner=self._owner, ttl_s=LEASE_TTL_SECONDS):
                msg = "Lost the data subject eraser lease"
                raise RuntimeError(msg)

    async def _due_requests(self) -> list[UUID]:
        """Up to ``CANDIDATE_BATCH`` runnable requests, paging past ones that are waiting or out of retries.

        Retry state lives in a JSON column, so it is filtered here; paging keeps a run of exhausted
        requests from hiding the approvals queued behind them.
        """
        due: list[UUID] = []
        offset = 0
        async with session_scope() as session:
            while len(due) < CANDIDATE_BATCH:
                rows = (
                    await session.exec(
                        select(DataSubjectRequest)
                        .where(col(DataSubjectRequest.status).in_(RUNNABLE))
                        .order_by(col(DataSubjectRequest.decided_at), col(DataSubjectRequest.id))
                        .offset(offset)
                        .limit(CANDIDATE_BATCH)
                    )
                ).all()
                due.extend(row.id for row in rows if is_retry_due(row))
                if len(rows) < CANDIDATE_BATCH:
                    break
                offset += CANDIDATE_BATCH
        return due[:CANDIDATE_BATCH]

    async def run_once(self) -> int:
        """Approve overdue requests when auto-erase is on, then run every due request once.

        Returns how many erase runs were attempted.
        """
        # A paused instance erases nothing. An approved request keeps its status, and the first pass
        # after the pause runs it.
        if is_paused():
            return 0
        async with session_scope() as session:
            if not await leases.acquire(session, name=LEASE_NAME, owner=self._owner, ttl_s=LEASE_TTL_SECONDS):
                return 0
        await approve_expired_requests()
        attempted = 0
        for request_id in await self._due_requests():
            # A pause that began during this pass lets the erase under way end, and no other starts.
            if self._stop.is_set() or is_paused():
                break
            await run_request(request_id, heartbeat=self._renew)
            attempted += 1
        return attempted


data_subject_erase_worker = DataSubjectEraseWorker()
