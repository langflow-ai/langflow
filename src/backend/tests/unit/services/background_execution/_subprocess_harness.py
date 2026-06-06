"""Real-process real-service harness: a REAL ``langflow worker`` OS subprocess.

Phase 4 proved the scaled claim/run/reattach/stop paths in-process (same event
loop). This closes that honest caveat with an ACTUAL separate process:

* Real Postgres (``LANGFLOW_TEST_DATABASE_URI``) as the durable store, shared
  between the test-side API facade and the worker subprocess.
* Real Redis (``LANGFLOW_TEST_REDIS_URL``, a dedicated DB index) as the claim
  queue + Streams live bus + cancel pub/sub.
* A real no-LLM flow (ChatInput -> ChatOutput) seeded into the shared DB, so the
  worker's PRODUCTION ``_default_frame_source_factory`` builds and runs a real
  graph — not a scripted source.

The worker is launched with ``subprocess.Popen(["uv", "run", "langflow",
"worker", ...])`` and torn down in a finally. Every wait is bounded by a deadline
so a regression FAILS loudly instead of hanging.
"""

from __future__ import annotations

import contextlib
import os
import subprocess
import uuid
from dataclasses import dataclass, field
from urllib.parse import urlparse, urlunparse

# Async driver the project actually ships for Postgres (see pyproject:
# sqlalchemy[postgresql_psycopg]). psycopg v3 accepts the ``options`` connect
# arg the DatabaseService sets for Postgres; asyncpg does not.
_PSYCOPG_PREFIX = "postgresql+psycopg://"

# The pending claim-queue key the worker drains (RedisJobClaimQueue default). The
# test-side harness enqueues to this same key; isolation comes from a dedicated
# redis DB index that is flushed per test.
_PENDING_KEY = "langflow:bg:pending"


def psycopg_url(raw: str) -> str:
    """Normalize a Postgres URL to the async psycopg (v3) driver."""
    if raw.startswith(_PSYCOPG_PREFIX):
        return raw
    for prefix in ("postgresql+asyncpg://", "postgresql+psycopg2://", "postgresql://", "postgres://"):
        if raw.startswith(prefix):
            return _PSYCOPG_PREFIX + raw[len(prefix) :]
    return raw


def redis_db_url(base_url: str, db_index: int) -> str:
    """Return ``base_url`` pointed at a specific redis DB index (path = /N)."""
    parsed = urlparse(base_url)
    return urlunparse(parsed._replace(path=f"/{db_index}"))


@dataclass
class WorkerHarness:
    """Bound state for a real-process worker proof. Build via ``setup``."""

    db_url: str
    redis_url: str
    job_service: object
    procs: list[subprocess.Popen] = field(default_factory=list)
    _client: object | None = None
    _prior_db_env: str | None = None
    _prior_db_env_set: bool = False
    _prior_db_service: object | None = None
    _prior_settings_url: str | None = None
    _db_service: object | None = None

    async def seed_real_flow(self, *, input_value: str = "hello") -> tuple[uuid.UUID, uuid.UUID]:
        """Seed a real user + a real ChatInput->ChatOutput flow; return (user_id, flow_id).

        The flow ``data`` is produced by dumping a REAL connected Graph, so the
        worker builds the same graph the canvas would.
        """
        from langflow.services.database.models.flow.model import Flow
        from langflow.services.database.models.user.model import User
        from langflow.services.deps import session_scope
        from lfx.components.input_output import ChatInput, ChatOutput
        from lfx.graph import Graph

        chat_input = ChatInput(_id=f"ChatInput-{uuid.uuid4().hex[:6]}")
        chat_input.set(input_value=input_value)
        chat_output = ChatOutput(_id=f"ChatOutput-{uuid.uuid4().hex[:6]}")
        chat_output.set(input_value=chat_input.message_response)
        graph = Graph(start=chat_input, end=chat_output)
        flow_data = graph.dump()["data"]

        user_id = uuid.uuid4()
        flow_id = uuid.uuid4()
        async with session_scope() as session:
            session.add(User(id=user_id, username=f"wkr-{user_id}", password="x", is_active=True))  # noqa: S106
            session.add(Flow(id=flow_id, name=f"wkr-{flow_id}", data=flow_data, user_id=user_id))
            await session.commit()
        return user_id, flow_id

    async def seed_slow_flow(self) -> tuple[uuid.UUID, uuid.UUID]:
        """Seed a real multi-vertex no-LLM flow (MemoryChatbotNoLLM starter).

        Prompt + ChatInput + ChatOutput + Memory + TypeConverter cross several
        vertex boundaries, so the build loop is reliably mid-flight long enough to
        SIGKILL the worker or land a stop. Returns (user_id, flow_id).
        """
        import json
        from pathlib import Path

        from langflow.services.database.models.flow.model import Flow
        from langflow.services.database.models.user.model import User
        from langflow.services.deps import session_scope

        data_path = Path(__file__).parents[3] / "data" / "MemoryChatbotNoLLM.json"
        flow_data = json.loads(data_path.read_text(encoding="utf-8"))["data"]
        user_id = uuid.uuid4()
        flow_id = uuid.uuid4()
        async with session_scope() as session:
            session.add(User(id=user_id, username=f"slow-{user_id}", password="x", is_active=True))  # noqa: S106
            session.add(Flow(id=flow_id, name=f"slow-{flow_id}", data=flow_data, user_id=user_id))
            await session.commit()
        return user_id, flow_id

    async def submit_job(self, *, flow_id: uuid.UUID, user_id: uuid.UUID, input_value: str = "hello") -> uuid.UUID:
        """Persist a QUEUED job + its request and enqueue it on the claim queue.

        Mirrors exactly what the scaled facade ``submit`` does (create_job +
        update_job_metadata({"request": ...}) + LPUSH), so the worker hydrates a
        production-shaped job row.
        """
        job_id = uuid.uuid4()
        await self.job_service.create_job(job_id=job_id, flow_id=flow_id, user_id=user_id)
        request = {"flow_id": str(flow_id), "stream_protocol": "langflow", "input_value": input_value}
        await self.job_service.update_job_metadata(job_id, {"request": request})
        await self.client.lpush(_PENDING_KEY, str(job_id))
        return job_id

    @property
    def client(self):
        if self._client is None:
            from redis.asyncio import StrictRedis

            self._client = StrictRedis.from_url(self.redis_url)
        return self._client

    def spawn_worker(self, *, idle_block_ms: int = 200) -> subprocess.Popen:
        """Launch a REAL ``langflow worker`` OS subprocess against the shared store."""
        env = dict(os.environ)
        env["LANGFLOW_JOB_QUEUE_TYPE"] = "redis"
        env["LANGFLOW_DATABASE_URL"] = self.db_url
        env["LANGFLOW_REDIS_QUEUE_URL"] = self.redis_url
        # Keep the worker quiet + deterministic; no telemetry/tracing.
        env["LANGFLOW_DEACTIVATE_TRACING"] = "true"
        env["DO_NOT_TRACK"] = "true"
        # A REAL OS subprocess is the whole point of this proof (closes the Phase
        # 4 in-process caveat); the argv is a fixed literal, not untrusted input.
        # ``start_new_session`` puts the worker in its OWN process group: ``uv run``
        # spawns a child python that does NOT inherit a SIGTERM sent to ``uv``, so
        # we signal the whole group (see ``_kill_proc``) to avoid leaking workers.
        proc = subprocess.Popen(  # noqa: S603
            ["uv", "run", "langflow", "worker", "--idle-block-ms", str(idle_block_ms)],  # noqa: S607
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        self.procs.append(proc)
        return proc

    @staticmethod
    def signal_group(proc: subprocess.Popen, sig: int) -> None:
        """Send ``sig`` to the subprocess's whole process group (kills uv + python)."""
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(os.getpgid(proc.pid), sig)

    async def wait_for_status(self, job_id: uuid.UUID, targets: set, *, timeout: float = 60.0):
        """Poll the durable job row until its status is in ``targets``, bounded by ``timeout``.

        Raises AssertionError on timeout so a regression fails loudly. The worker
        subprocess output is included in the failure message so a worker that
        failed to boot or claim is diagnosable.
        """
        import asyncio

        deadline = asyncio.get_event_loop().time() + timeout
        last = None
        while asyncio.get_event_loop().time() < deadline:
            job = await self.job_service.get_job_by_job_id(job_id)
            last = job.status if job else None
            if last in targets:
                return job
            # Surface an early worker crash instead of waiting the full timeout.
            dead = [p for p in self.procs if p.poll() is not None]
            if dead and not any(p.poll() is None for p in self.procs):
                break
            await asyncio.sleep(0.2)
        msg = f"job {job_id} never reached {targets}; last status={last}\n{self.drain_worker_output()}"
        raise AssertionError(msg)

    def drain_worker_output(self) -> str:
        """Return any buffered stdout/stderr from the worker subprocesses (best-effort)."""
        chunks = []
        for proc in self.procs:
            if proc.stdout is None:
                continue
            with contextlib.suppress(Exception):
                if proc.poll() is None:
                    proc.terminate()
                out = proc.stdout.read()
                if out:
                    chunks.append(f"--- worker pid={proc.pid} output ---\n{out.decode(errors='replace')[-4000:]}")
        return "\n".join(chunks) if chunks else "(no worker output captured)"

    async def teardown(self) -> None:
        import signal

        for proc in self.procs:
            if proc.poll() is None:
                # Signal the whole group so the ``uv run`` child python dies too.
                self.signal_group(proc, signal.SIGTERM)
        for proc in self.procs:
            with contextlib.suppress(Exception):
                proc.wait(timeout=10)
            if proc.poll() is None:
                self.signal_group(proc, signal.SIGKILL)
                with contextlib.suppress(Exception):
                    proc.wait(timeout=5)
        if self._client is not None:
            with contextlib.suppress(Exception):
                await self._client.flushdb()
            with contextlib.suppress(Exception):
                await self._client.aclose()
        # Tear down the pg engine and restore the manager's DB service + settings
        # url + env var so this harness does not leak state to later tests.
        from langflow.services.deps import get_settings_service
        from lfx.services.manager import get_service_manager
        from lfx.services.schema import ServiceType

        manager = get_service_manager()
        manager.services.pop(ServiceType.DATABASE_SERVICE, None)
        if self._db_service is not None:
            with contextlib.suppress(Exception):
                await self._db_service.teardown()
        if self._prior_db_service is not None:
            manager.services[ServiceType.DATABASE_SERVICE] = self._prior_db_service
        if self._prior_settings_url is not None:
            get_settings_service().settings.database_url = self._prior_settings_url
        if self._prior_db_env_set:
            os.environ["LANGFLOW_DATABASE_URL"] = self._prior_db_env  # type: ignore[assignment]
        else:
            os.environ.pop("LANGFLOW_DATABASE_URL", None)


async def setup_worker_harness(pg_uri: str, redis_base_url: str, *, redis_db: int = 14) -> WorkerHarness:
    """Stand up the shared store + a JobService bound to it. Caller owns teardown.

    Migrates (creates) the schema on the shared Postgres via the async psycopg
    engine and binds ``session_scope`` to it, so both the test-side facade and
    the worker subprocess read the SAME durable store.
    """
    from langflow.services.database.factory import DatabaseServiceFactory
    from langflow.services.deps import get_settings_service
    from langflow.services.jobs.service import JobService
    from lfx.services.manager import get_service_manager
    from lfx.services.schema import ServiceType

    db_url = psycopg_url(pg_uri)
    redis_url = redis_db_url(redis_base_url, redis_db)

    # The Settings.database_url ``mode='before'`` validator discards a directly
    # assigned value and re-derives a config-dir sqlite path UNLESS
    # LANGFLOW_DATABASE_URL is set. Set it in the test process so both the
    # test-side engine AND the inherited worker subprocess bind to the SAME pg.
    prior_db_env = os.environ.get("LANGFLOW_DATABASE_URL")
    prior_db_env_set = "LANGFLOW_DATABASE_URL" in os.environ
    os.environ["LANGFLOW_DATABASE_URL"] = db_url

    settings_service = get_settings_service()
    prior_settings_url = settings_service.settings.database_url
    settings_service.settings.database_url = db_url
    manager = get_service_manager()
    prior_db_service = manager.services.pop(ServiceType.DATABASE_SERVICE, None)
    db_service = DatabaseServiceFactory().create(settings_service)
    manager.services[ServiceType.DATABASE_SERVICE] = db_service
    await db_service.create_db_and_tables()

    harness = WorkerHarness(
        db_url=db_url,
        redis_url=redis_url,
        job_service=JobService(),
        _prior_db_env=prior_db_env,
        _prior_db_env_set=prior_db_env_set,
        _prior_db_service=prior_db_service,
        _prior_settings_url=prior_settings_url,
        _db_service=db_service,
    )
    # Flush the dedicated redis DB so a prior run cannot leak claim-queue ids.
    await harness.client.flushdb()
    return harness
