r"""Direct stress harness for transaction + vertex_build writes.

Bypasses FastAPI / locust / OpenAI by calling the same write functions the
graph executor invokes via BackgroundTasks. Reproduces the failure mode the
user reported (SQLite "database is locked" and Postgres pool timeouts) by
running many concurrent writers against the configured database.

Usage:
    uv run python src/backend/tests/stress/stress_telemetry_writes.py \
        --concurrency 200 --seconds 30

    DB_URL=$LANGFLOW_DATABASE_URL \
    uv run python src/backend/tests/stress/stress_telemetry_writes.py \
        --concurrency 500 --seconds 30

See README.md for full usage and what numbers to interpret.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import random
import sys
import time
import traceback
from collections import Counter
from uuid import uuid4

# Configure env BEFORE importing langflow so settings pick up the DB URL.
DB_URL = os.environ.get("DB_URL", "sqlite:///./stress.db")
os.environ.setdefault("LANGFLOW_DATABASE_URL", DB_URL)
os.environ.setdefault("LANGFLOW_TRANSACTIONS_STORAGE_ENABLED", "true")
os.environ.setdefault("LANGFLOW_VERTEX_BUILDS_STORAGE_ENABLED", "true")
# Auto-login keeps service init from blocking on user setup paths.
os.environ.setdefault("LANGFLOW_AUTO_LOGIN", "true")


async def setup() -> tuple[object, object]:
    from langflow.services.deps import get_db_service, get_settings_service
    from langflow.services.manager import get_service_manager
    from langflow.services.utils import initialize_services

    settings = get_settings_service().settings
    print(f"[setup] DB_URL={settings.database_url}")
    print(f"[setup] telemetry_writer_enabled={getattr(settings, 'telemetry_writer_enabled', 'n/a')}")
    await initialize_services()
    db_service = get_db_service()
    await db_service.initialize_alembic_log_file()
    await db_service.create_db_and_tables()

    if getattr(settings, "telemetry_writer_enabled", False):
        from langflow.services.deps import get_telemetry_writer_service

        writer = get_telemetry_writer_service()
        if writer is not None and writer.is_enabled():
            await writer.start()
            print(f"[setup] telemetry_writer started, running={writer.is_running()}")
    return db_service, get_service_manager()


def make_inputs(i: int) -> dict:
    return {
        "input_value": f"hello {i} {'x' * 200}",
        "config": {"temperature": 0.7, "model": "gpt-4o-mini"},
    }


def make_outputs(i: int) -> dict:
    return {
        "result": {"text": f"answer {i} " + ("y" * 400), "tokens": 123},
        "trace_id": str(uuid4()),
    }


async def worker(
    worker_id: int,
    flow_id: str,
    stop_at: float,
    counters: Counter,
    error_samples: dict[str, str],
) -> None:
    from lfx.graph.utils import log_vertex_build
    from lfx.services.deps import get_transaction_service

    tx_service = get_transaction_service()
    i = 0
    while time.monotonic() < stop_at:
        i += 1
        try:
            await tx_service.log_transaction(
                flow_id=flow_id,
                vertex_id=f"vertex-{worker_id}-{i % 5}",
                inputs=make_inputs(i),
                outputs=make_outputs(i),
                status="success",
                target_id=f"target-{worker_id}-{i % 5}",
            )
            counters["transactions_ok"] += 1
        except Exception as exc:
            key = f"tx:{type(exc).__name__}"
            counters[key] += 1
            error_samples.setdefault(key, f"{exc!s}\n{traceback.format_exc(limit=2)}")

        try:
            await log_vertex_build(
                flow_id=flow_id,
                vertex_id=f"vertex-{worker_id}-{i % 5}",
                valid=True,
                params=str(make_inputs(i)),
                data=make_outputs(i),
                artifacts=None,
            )
            counters["vertex_builds_ok"] += 1
        except Exception as exc:
            key = f"vb:{type(exc).__name__}"
            counters[key] += 1
            error_samples.setdefault(key, f"{exc!s}\n{traceback.format_exc(limit=2)}")

        await asyncio.sleep(random.uniform(0.0, 0.01))


async def count_rows(db_service) -> tuple[int, int]:
    from sqlalchemy import text

    async with db_service.engine.begin() as conn:
        tx = (await conn.execute(text('SELECT count(*) FROM "transaction"'))).scalar_one()
        vb = (await conn.execute(text('SELECT count(*) FROM "vertex_build"'))).scalar_one()
    return int(tx), int(vb)


def _print_writer_state(label: str, writer) -> None:
    print(
        f"[run]  writer @ {label}: "
        f"enq_tx={writer.enqueued_transactions} enq_vb={writer.enqueued_vertex_builds} "
        f"flushed_rows={writer.flushed_rows} failed_batches={writer.failed_batches} "
        f"dropped_tx={writer.dropped_transactions} dropped_vb={writer.dropped_vertex_builds} "
        f"tx_buffer={len(writer._tx_buffer)} vb_buffer={len(writer._vb_buffer)}"
    )


async def main_async(args) -> int:
    db_service, service_manager = await setup()
    flow_id = str(uuid4())
    counters: Counter = Counter()
    error_samples: dict[str, str] = {}

    print(f"[run]  concurrency={args.concurrency}  seconds={args.seconds}  flow={flow_id}")
    pre_tx, pre_vb = await count_rows(db_service)
    print(f"[run]  pre-rows tx={pre_tx} vb={pre_vb}")

    start = time.monotonic()
    stop_at = start + args.seconds
    workers = [
        asyncio.create_task(worker(i, flow_id, stop_at, counters, error_samples)) for i in range(args.concurrency)
    ]
    results = await asyncio.gather(*workers, return_exceptions=True)
    elapsed = time.monotonic() - start
    exc_types: Counter = Counter()
    for r in results:
        if isinstance(r, BaseException):
            exc_types[type(r).__name__] += 1
            error_samples.setdefault(
                f"worker:{type(r).__name__}",
                f"{r!s}\n{''.join(traceback.format_exception(r))[-200:]}",
            )
    if exc_types:
        print(f"[run]  worker-level exceptions: {dict(exc_types)}")

    writer = None
    try:
        from langflow.services.deps import get_telemetry_writer_service

        writer = get_telemetry_writer_service()
    except Exception:
        writer = None
    if writer is not None and writer.is_running():
        _print_writer_state("workers-done", writer)

    drain_grace = float(os.environ.get("DRAIN_GRACE_S", "5"))
    if drain_grace > 0:
        print(f"[run]  drain grace {drain_grace}s ...")
        await asyncio.sleep(drain_grace)

    if writer is not None and writer.is_running():
        _print_writer_state("post-drain", writer)

    post_tx, post_vb = await count_rows(db_service)
    print()
    print(f"[done] elapsed={elapsed:.2f}s")
    print(f"[done] counters: {dict(counters)}")
    print(f"[done] rows tx: pre={pre_tx} post={post_tx} delta={post_tx - pre_tx}")
    print(f"[done] rows vb: pre={pre_vb} post={post_vb} delta={post_vb - pre_vb}")
    if error_samples:
        print("[done] error samples:")
        for key, sample in list(error_samples.items())[:10]:
            print(f"  --- {key} ---")
            for line in sample.splitlines()[:6]:
                print(f"    {line}")

    try:
        await service_manager.teardown()
    except Exception as exc:
        print(f"[teardown] error: {exc}")

    errs = sum(v for k, v in counters.items() if not k.endswith("_ok"))
    print(f"[done] error_total={errs}")
    return 1 if errs > 0 else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--concurrency", type=int, default=200, help="Number of concurrent worker coroutines.")
    parser.add_argument("--seconds", type=int, default=20, help="Producer phase duration in seconds.")
    args = parser.parse_args()
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    sys.exit(main())
