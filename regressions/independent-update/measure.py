"""Measure actual old/new job payload methods against a disposable PostgreSQL DB.

Enable log_statement=all and log_line_prefix='%m [%p] %a ' on that instance,
then supply its server log to capture transaction control statements too.
"""

# Standalone benchmark: deliberate baseline AST execution, assertions, local log I/O, and stdout.
# ruff: noqa: INP001, S102, S101, SLF001, ASYNC230, T201

import argparse
import ast
import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path
from time import perf_counter
from types import SimpleNamespace
from uuid import uuid4

from langflow.services.database import autocommit
from langflow.services.database.models.jobs.model import Job, JobStatus
from langflow.services.jobs import service as jobs
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

BASELINE = "68e8338f3a6063c696fe25a1814cb15fc00c88ac"


async def main(args):
    """Run interleaved samples after warming both dedicated connection pools."""
    process = await asyncio.create_subprocess_exec(
        "git",
        "show",
        f"{BASELINE}:src/backend/base/langflow/services/jobs/service.py",
        stdout=asyncio.subprocess.PIPE,
    )
    output, _ = await process.communicate()
    if process.returncode:
        message = "Could not read baseline revision"
        raise RuntimeError(message)
    source = output.decode()
    tree = ast.parse(source)
    method = next(
        node for node in ast.walk(tree) if isinstance(node, ast.AsyncFunctionDef) and node.name == "_set_live_payload"
    )
    module = ast.Module(
        body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0), method],
        type_ignores=[],
    )
    namespace = dict(vars(jobs))
    exec(compile(ast.fix_missing_locations(module), "baseline_job_payload", "exec"), namespace)
    old = namespace["_set_live_payload"]
    engines = {
        mode: create_async_engine(
            args.url,
            connect_args={"server_settings": {"application_name": f"independent_update_{mode}"}},
            pool_size=1,
            max_overflow=0,
        )
        for mode in ("before", "after")
    }
    job_id = uuid4()
    service = jobs.JobService()

    @asynccontextmanager
    async def scope():
        async with AsyncSession(engines["before"], expire_on_commit=False) as session:
            yield session
            await session.commit()

    namespace["session_scope"] = scope
    autocommit.get_db_service = lambda: SimpleNamespace(engine=engines["after"])
    try:
        async with engines["before"].begin() as connection:
            await connection.run_sync(Job.__table__.create, checkfirst=True)
            row = Job(
                job_id=job_id,
                flow_id=uuid4(),
                status=JobStatus.IN_PROGRESS,
                user_id=uuid4(),
                job_metadata={"owner": "benchmark"},
            )
            await connection.execute(Job.__table__.insert().values(**row.model_dump()))
        methods = {"before": old, "after": jobs.JobService._set_live_payload}
        for method in methods.values():
            assert await method(service, job_id, "result", {"warm": True}, owner="benchmark")
        offset = Path(args.server_log).stat().st_size
        samples = {mode: [] for mode in methods}
        for index in range(args.samples):
            for mode in ("before", "after") if index % 2 == 0 else ("after", "before"):
                started = perf_counter()
                assert await methods[mode](service, job_id, "result", {"index": index}, owner="benchmark")
                samples[mode].append((perf_counter() - started) * 1000)
        with Path(args.server_log).open() as log:
            log.seek(offset)
            lines = log.read().splitlines()
        raw = [line for line in lines if "independent_update_" in line]
        print(json.dumps({"baseline": BASELINE, "milliseconds": samples, "server_log": raw}, indent=2))
    finally:
        async with engines["before"].begin() as connection:
            await connection.execute(Job.__table__.delete().where(Job.job_id == job_id))
        for engine in engines.values():
            await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--server-log", required=True)
    parser.add_argument("--samples", type=int, default=10)
    asyncio.run(main(parser.parse_args()))
