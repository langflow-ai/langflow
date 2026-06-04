"""The ``langflow worker`` process: claim jobs off redis and run the JobRunner.

In the scaled backend the API process only enqueues; this separate process
drains the claim queue. On startup it reconciles orphaned leases
(``requeue_lost``), then loops: claim a job id (blocking pop with a timeout so it
can observe the stop event), run the runner, release the lease. A runner crash
still releases the lease so the id does not get stuck on the processing list —
the watchdog reconciles the durable job row separately.
"""

from __future__ import annotations

import asyncio
from typing import Any

from lfx.log.logger import logger


async def run_worker_loop(
    backend: Any,
    runner: Any,
    *,
    stop_event: asyncio.Event,
    idle_block_ms: int = 1000,
) -> None:
    """Claim-and-run loop. Returns when *stop_event* is set.

    Args:
        backend: object exposing requeue_lost(), claim(block_ms=), complete(id).
        runner: object exposing run(job_id).
        stop_event: set by the signal handler for cooperative shutdown.
        idle_block_ms: how long claim() blocks waiting for work each iteration;
            kept short so the loop notices stop_event promptly.
    """
    # Startup reconcile: requeue work lost by a previously-crashed worker.
    await backend.requeue_lost()

    while not stop_event.is_set():
        job_id = await backend.claim(block_ms=idle_block_ms)
        if job_id is None:
            # claim() blocks up to idle_block_ms on a real redis, but a backend
            # that returns None promptly (empty queue, error path, test double)
            # must not hot-spin — yield so the stop signal and other tasks run.
            await asyncio.sleep(0)
            continue
        try:
            await runner.run(job_id)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            await logger.aexception(f"Worker: runner failed for job {job_id}: {exc}")
        finally:
            # Always release the lease — the durable job row + watchdog decide
            # whether the work should be retried; a stuck processing-list entry
            # would block reconcile forever.
            await backend.complete(job_id)
