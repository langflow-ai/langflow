"""Multiplayer writes (POST /api/v2/flows/{id}/ops) on real PostgreSQL, through real server processes.

Each (write mode, engine) runs two Langflow server processes on one database,
so every process has its own cache and the advisory lock is the only thing
that orders their writes. The tests drive them over HTTP and read the
database directly to check what was stored.

Needs a disposable PostgreSQL database; skipped unless both are set:

- ``LANGFLOW_TEST_MULTIPLAYER_ADMIN_URL``: psycopg URL of the database, used
  by the test to reset its schema and read it (direct to PostgreSQL);
- ``LANGFLOW_TEST_MULTIPLAYER_DB_URL``: the SQLAlchemy URL the servers use
  (direct, or through PgBouncer in transaction mode).

The test drops and recreates the ``public`` schema of that database.
"""

from __future__ import annotations

import asyncio
import os
import socket
import subprocess
import sys
import time
import uuid
from itertools import pairwise
from typing import TYPE_CHECKING

import httpx
import orjson
import psycopg
import pytest

if TYPE_CHECKING:
    from pathlib import Path

ADMIN_URL = os.environ.get("LANGFLOW_TEST_MULTIPLAYER_ADMIN_URL")
DB_URL = os.environ.get("LANGFLOW_TEST_MULTIPLAYER_DB_URL")

pytestmark = pytest.mark.skipif(
    not (ADMIN_URL and DB_URL), reason="LANGFLOW_TEST_MULTIPLAYER_ADMIN_URL and _DB_URL not set"
)

MODES = ("nocache", "cache", "wal")
ENGINES = ("python", "rust")
CADENCE = 5
WINDOW = 40
BASE_NODES = 6
FIELD_PATH = ["data", "node", "template", "t", "value"]
NS = uuid.UUID("6d3f5d0e-6a52-4b1e-9d3b-2f0a0c1e7a11")

_FAIL_TRIGGERS = """
CREATE OR REPLACE FUNCTION mp_test_fail_insert() RETURNS trigger AS $$
BEGIN
  IF NEW.ops::text LIKE '%mp-inject-fail-insert%' THEN RAISE EXCEPTION 'injected insert failure'; END IF;
  RETURN NEW;
END $$ LANGUAGE plpgsql;
CREATE TRIGGER mp_test_fail_insert BEFORE INSERT ON flow_operation
  FOR EACH ROW EXECUTE FUNCTION mp_test_fail_insert();
CREATE OR REPLACE FUNCTION mp_test_at_commit() RETURNS trigger AS $$
BEGIN
  IF NEW.ops::text LIKE '%mp-inject-fail-commit%' THEN RAISE EXCEPTION 'injected commit failure'; END IF;
  IF NEW.ops::text LIKE '%mp-inject-slow-commit%' THEN PERFORM pg_sleep(1.5); END IF;
  RETURN NULL;
END $$ LANGUAGE plpgsql;
CREATE CONSTRAINT TRIGGER mp_test_at_commit AFTER INSERT ON flow_operation
  DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION mp_test_at_commit();
"""


# --- Graphs and batches --------------------------------------------------------------------------


def node(node_id: str, value: str) -> dict:
    return {"id": node_id, "data": {"node": {"display_name": node_id, "template": {"t": {"value": value}}}}}


def base_graph() -> dict:
    return {"nodes": [node(f"n{i}", f"v{i}") for i in range(BASE_NODES)], "edges": []}


def set_field(node_id: str, value: str) -> list[dict]:
    return [
        {"type": "update_nodes", "updates": [{"op": "set_field", "id": node_id, "path": FIELD_PATH, "value": value}]}
    ]


def writer_batch(writer: int, i: int) -> tuple[str, list[dict]]:
    """Writer ``writer``'s batch ``i``: add a node, edit a shared node, edit its node, delete its node."""
    own = f"w{writer}-{i - i % 4}"
    step = i % 4
    if step == 0:
        return "add", [{"type": "add_nodes", "nodes": [node(own, "new")]}]
    if step == 1:
        return f"n{(writer + i) % BASE_NODES}", set_field(f"n{(writer + i) % BASE_NODES}", f"w{writer}-b{i}")
    if step == 2:
        return "own", set_field(own, f"w{writer}-o{i}")
    return "delete", [{"type": "delete_nodes", "ids": [own]}]


def request_id(*parts: object) -> str:
    return str(uuid.uuid5(NS, ":".join(map(str, parts))))


def values(graph: dict) -> dict[str, str]:
    return {n["id"]: n["data"]["node"]["template"]["t"]["value"] for n in graph["nodes"]}


def engine_for(name: str):
    from lfx.services.flow_operations.engine import get_engine

    return get_engine(name)


def replay(engine_name: str, graph: dict | str, revisions: list[dict]) -> dict:
    engine = engine_for(engine_name)
    text = graph if isinstance(graph, str) else orjson.dumps(graph).decode()
    state = engine.GraphState(text.encode())
    operations = [op for rev in revisions for op in rev["operations"]]
    if operations:
        state.replay(orjson.dumps(operations))
    return orjson.loads(state.to_json())


def same_graph(engine_name: str, left: dict, right: dict) -> bool:
    return engine_for(engine_name).graphs_equal(left, right)


# --- Servers -------------------------------------------------------------------------------------


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _reset_schema() -> None:
    with psycopg.connect(ADMIN_URL, autocommit=True) as conn:
        conn.execute("DROP SCHEMA IF EXISTS public CASCADE")
        conn.execute("CREATE SCHEMA public")


class Server:
    def __init__(self, mode: str, engine: str, workdir: Path, index: int) -> None:
        self.port = _free_port()
        self.url = f"http://127.0.0.1:{self.port}"
        self.log = workdir / f"server-{mode}-{engine}-{index}.log"
        config_dir = workdir / f"config-{mode}-{engine}-{index}"
        config_dir.mkdir(parents=True, exist_ok=True)
        env = {
            "PATH": os.environ.get("PATH", ""),
            "HOME": os.environ.get("HOME", ""),
            "TMPDIR": os.environ.get("TMPDIR", str(workdir)),
            "LANGFLOW_DATABASE_URL": DB_URL,
            "LANGFLOW_CONFIG_DIR": str(config_dir),
            "LANGFLOW_FLOW_HISTORY_ENABLED": "true",
            "LANGFLOW_FLOW_WRITE_MODE": mode,
            "LANGFLOW_FLOW_ENGINE": engine,
            "LANGFLOW_FLOW_REVISION_CHECKPOINT_CADENCE": str(CADENCE),
            "LANGFLOW_FLOW_REVISION_RETENTION_WINDOW": str(WINDOW),
            "LANGFLOW_WORKERS": "1",
            "LANGFLOW_AUTO_LOGIN": "true",
            "LANGFLOW_SKIP_AUTH_AUTO_LOGIN": "true",
            "LANGFLOW_CREATE_STARTER_PROJECTS": "false",
            "LANGFLOW_UPDATE_STARTER_PROJECTS": "false",
            "LANGFLOW_LOG_LEVEL": "warning",
            "LANGFLOW_DO_NOT_TRACK": "true",
            "LANGFLOW_OPS_BENCH": "1",
        }
        self._log_file = self.log.open("wb")
        self.proc = subprocess.Popen(  # noqa: S603
            [
                sys.executable,
                "-m",
                "langflow",
                "run",
                "--backend-only",
                "--host",
                "127.0.0.1",
                "--port",
                str(self.port),
                "--workers",
                "1",
            ],
            env=env,
            stdout=self._log_file,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )

    def wait_ready(self, timeout: float = 240) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.proc.poll() is not None:
                msg = f"server exited: {self.log.read_text()[-3000:]}"
                raise RuntimeError(msg)
            try:
                if httpx.get(f"{self.url}/health", timeout=2).status_code == 200:
                    return
            except httpx.HTTPError:
                pass
            time.sleep(0.5)
        msg = f"server not ready: {self.log.read_text()[-3000:]}"
        raise RuntimeError(msg)

    def stop(self) -> None:
        if self.proc.poll() is None:
            os.killpg(self.proc.pid, 15)
            try:
                self.proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                os.killpg(self.proc.pid, 9)
                self.proc.wait()
        self._log_file.close()


@pytest.fixture(scope="module", params=[(m, e) for e in ENGINES for m in MODES], ids=lambda p: f"{p[0]}-{p[1]}")
def servers(request, tmp_path_factory):
    mode, engine = request.param
    workdir = tmp_path_factory.mktemp(f"mp-{mode}-{engine}")
    _reset_schema()
    first = Server(mode, engine, workdir, 0)
    started = [first]
    try:
        first.wait_ready()  # migrations run once, before the second process starts
        with psycopg.connect(ADMIN_URL, autocommit=True) as conn:
            conn.execute(_FAIL_TRIGGERS)
        second = Server(mode, engine, workdir, 1)
        started.append(second)
        second.wait_ready()
        yield {"mode": mode, "engine": engine, "urls": [first.url, second.url]}
    finally:
        for server in started:
            server.stop()


@pytest.fixture(scope="session")
def recorded() -> dict:
    """Results of the deterministic workload, by (mode, engine), compared across combinations."""
    return {}


# --- HTTP helpers --------------------------------------------------------------------------------


async def create_flow(client: httpx.AsyncClient, url: str, graph: dict | None = None) -> str:
    name = f"mp-{uuid.uuid4().hex[:10]}"
    response = await client.post(f"{url}/api/v1/flows/", json={"name": name, "data": graph or base_graph()})
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def post_ops(client, url, flow_id, operations, rid=None, base=None) -> httpx.Response:
    body = {"request_id": rid or str(uuid.uuid4()), "operations": operations}
    if base is not None:
        body["base_revision"] = base
    return await client.post(f"{url}/api/v2/flows/{flow_id}/ops", json=body)


async def v1_flow(client, url, flow_id) -> dict:
    response = await client.get(f"{url}/api/v1/flows/{flow_id}")
    assert response.status_code == 200, response.text
    return response.json()


async def join(client, url, flow_id) -> dict:
    response = await client.get(f"{url}/api/v2/flows/{flow_id}")
    assert response.status_code == 200, response.text
    return response.json()


async def revisions(client, url, flow_id, after) -> dict:
    response = await client.get(f"{url}/api/v2/flows/{flow_id}/revisions", params={"after": after})
    assert response.status_code == 200, response.text
    return response.json()


async def joined_graph(client, url, flow_id, engine) -> tuple[int, dict]:
    """What a v2 client sees: the join, then the revisions after it, replayed."""
    joined = await join(client, url, flow_id)
    feed = await revisions(client, url, flow_id, joined["revision"])
    assert not feed["retention_gap"], feed
    return feed["latest_revision"], replay(engine, joined["data"], feed["revisions"])


def db_rows(flow_id: str) -> list[tuple[int, int, dict]]:
    with psycopg.connect(ADMIN_URL) as conn:
        rows = conn.execute(
            "SELECT start_revision, end_revision, ops::text FROM flow_operation WHERE flow_id = %s "
            "ORDER BY start_revision",
            (flow_id,),
        ).fetchall()
    return [(s, e, orjson.loads(ops)) for s, e, ops in rows]


def db_flow(flow_id: str) -> tuple[str, int, int]:
    with psycopg.connect(ADMIN_URL) as conn:
        return conn.execute(
            "SELECT data::text, current_revision, latest_revision FROM flow WHERE id = %s", (flow_id,)
        ).fetchone()


def assert_rows_contiguous(flow_id: str, head: int) -> None:
    rows = db_rows(flow_id)
    assert rows, "no log rows"
    for (_s1, e1, _), (s2, _e2, _) in pairwise(rows):
        assert s2 == e1 + 1, f"gap or overlap between rows ending {e1} and starting {s2}"
    for start, end, envelope in rows:
        count = sum(len(batch["operations"]) for batch in envelope["batches"])
        assert count == end - start + 1
    assert rows[-1][1] == head


# --- Tests ---------------------------------------------------------------------------------------


async def test_concurrent_writers_on_two_processes(servers):
    """Writers on two processes: revisions are gap-free, and every reader reaches the same graph."""
    engine, urls = servers["engine"], servers["urls"]
    writers, batches = 6, 20
    async with httpx.AsyncClient(timeout=60) as client:
        flow_id = await create_flow(client, urls[0])
        current_seen: list[int] = []
        stop = asyncio.Event()

        async def poll_current() -> None:
            async with await psycopg.AsyncConnection.connect(ADMIN_URL, autocommit=True) as conn:
                while not stop.is_set():
                    row = await (
                        await conn.execute("SELECT current_revision FROM flow WHERE id = %s", (flow_id,))
                    ).fetchone()
                    current_seen.append(row[0])
                    await asyncio.sleep(0.02)

        answers: list[tuple[int, int, str, dict]] = []

        async def writer(w: int) -> None:
            url = urls[w % len(urls)]
            for i in range(batches):
                target, operations = writer_batch(w, i)
                response = await post_ops(client, url, flow_id, operations, rid=request_id(flow_id, w, i))
                assert response.status_code == 200, response.text
                answer = response.json()
                assert answer["status"] == "applied"
                answers.append((answer["start_revision"], answer["end_revision"], target, operations[0]))

        poller = asyncio.create_task(poll_current())
        await asyncio.gather(*(writer(w) for w in range(writers)))
        stop.set()
        await poller

        # Every batch got its own revisions; together they are 1..head with no gap or overlap.
        answers.sort()
        expected = 1
        for start, end, _target, _op in answers:
            assert start == expected, f"revision {expected} missing or repeated"
            expected = end + 1
        head = expected - 1
        assert head == writers * batches

        # Flow.data's revision only moves forward.
        assert all(b >= a for a, b in pairwise(current_seen))

        # The last write to each shared node wins, in revision order.
        last_value = {f"n{i}": f"v{i}" for i in range(BASE_NODES)}
        for _start, _end, target, op in answers:
            if target.startswith("n"):
                last_value[target] = op["updates"][0]["value"]

        graphs = []
        for url in urls:
            flow = await v1_flow(client, url, flow_id)
            assert flow["current_revision"] == head
            graphs.append(flow["data"])
            latest, joined = await joined_graph(client, url, flow_id, engine)
            assert latest == head
            graphs.append(joined)
        for graph in graphs:
            assert values(graph) == last_value
            assert same_graph(engine, graph, graphs[0])

    await asyncio.sleep(0.5)  # let a checkpoint task finish
    assert_rows_contiguous(flow_id, head)
    _data, current, latest = db_flow(flow_id)
    assert current <= head
    assert latest <= head


async def test_retry_and_request_id_reuse(servers):
    urls = servers["urls"]
    async with httpx.AsyncClient(timeout=60) as client:
        flow_id = await create_flow(client, urls[0])
        rid = str(uuid.uuid4())
        first = await post_ops(client, urls[0], flow_id, set_field("n0", "first"), rid=rid)
        assert first.json() == {"status": "applied", "revision": 1, "start_revision": 1, "end_revision": 1}
        await post_ops(client, urls[1], flow_id, set_field("n1", "other"))
        # The same request again, on the other process: already applied, nothing new recorded.
        again = await post_ops(client, urls[1], flow_id, set_field("n0", "first"), rid=rid)
        assert again.status_code == 200
        assert again.json() == {"status": "already_applied", "revision": 2, "start_revision": 1, "end_revision": 1}
        reused = await post_ops(client, urls[0], flow_id, set_field("n0", "different"), rid=rid)
        assert reused.status_code == 409
        assert reused.json()["detail"]["code"] == "REQUEST_ID_REUSED"
        assert reused.json()["detail"]["latest_revision"] == 2
        # Two copies of one request at once: one applies, the other finds it.
        rid2 = str(uuid.uuid4())
        pair = await asyncio.gather(
            post_ops(client, urls[0], flow_id, set_field("n2", "pair"), rid=rid2),
            post_ops(client, urls[1], flow_id, set_field("n2", "pair"), rid=rid2),
        )
        statuses = sorted(r.json()["status"] for r in pair)
        assert statuses == ["already_applied", "applied"]
        assert {r.json()["start_revision"] for r in pair} == {3}
        assert (await revisions(client, urls[0], flow_id, 0))["latest_revision"] == 3


async def test_refused_batch_records_nothing(servers):
    urls = servers["urls"]
    async with httpx.AsyncClient(timeout=60) as client:
        flow_id = await create_flow(client, urls[0])
        await post_ops(client, urls[0], flow_id, set_field("n0", "a"))
        refused = await post_ops(client, urls[0], flow_id, set_field("missing-node", "x"))
        assert refused.status_code == 422
        detail = refused.json()["detail"]
        assert detail["code"]
        assert detail["latest_revision"] == 1
        ok = await post_ops(client, urls[1], flow_id, set_field("n0", "b"))
        assert ok.json()["start_revision"] == 2
        ahead = await post_ops(client, urls[0], flow_id, set_field("n0", "c"), base=99)
        assert ahead.status_code == 409
        assert ahead.json()["detail"]["code"] == "BASE_REVISION_AHEAD"


@pytest.mark.parametrize("failure", ["insert", "commit"])
async def test_staged_batch_dropped_on_database_failure(servers, failure):
    """A write whose database work fails leaves no trace: not in the log, the cache, or later answers."""
    engine, urls = servers["engine"], servers["urls"]
    async with httpx.AsyncClient(timeout=60) as client:
        flow_id = await create_flow(client, urls[0])
        assert (await post_ops(client, urls[0], flow_id, set_field("n0", "kept"))).status_code == 200
        failed = await post_ops(client, urls[0], flow_id, set_field("n1", f"mp-inject-fail-{failure}"))
        assert failed.status_code == 500
        after = await post_ops(client, urls[0], flow_id, set_field("n2", "after"))
        assert after.json()["start_revision"] == 2
        for url in urls:
            graph = (await v1_flow(client, url, flow_id))["data"]
            assert values(graph)["n1"] == "v1"
            assert values(graph)["n0"] == "kept"
            assert values(graph)["n2"] == "after"
            _latest, joined = await joined_graph(client, url, flow_id, engine)
            assert same_graph(engine, joined, graph)
    assert_rows_contiguous(flow_id, 2)


async def test_readers_never_see_uncommitted_revisions(servers):
    urls = servers["urls"]
    async with httpx.AsyncClient(timeout=60) as client:
        flow_id = await create_flow(client, urls[0])
        await post_ops(client, urls[0], flow_id, set_field("n0", "committed"))
        for url in urls:  # warm both caches
            await v1_flow(client, url, flow_id)
        started = time.monotonic()
        slow = asyncio.create_task(post_ops(client, urls[0], flow_id, set_field("n1", "mp-inject-slow-commit")))
        await asyncio.sleep(0.3)
        seen = []

        async def read(kind: str, url: str) -> None:
            if kind == "v1":
                flow = await v1_flow(client, url, flow_id)
                seen.append((time.monotonic() - started, flow["current_revision"], values(flow["data"])["n1"]))
            elif kind == "join":
                joined = await join(client, url, flow_id)
                seen.append((time.monotonic() - started, joined["revision"], values(joined["data"])["n1"]))
            else:
                feed = await revisions(client, url, flow_id, 0)
                marker = any("mp-inject" in orjson.dumps(r).decode() for r in feed["revisions"])
                seen.append((time.monotonic() - started, feed["latest_revision"], "marker" if marker else "v1"))

        await asyncio.gather(*(read(kind, url) for kind in ("v1", "join", "revisions") for url in urls))
        response = await slow
        assert response.status_code == 200
        before_commit = [s for s in seen if s[0] < 1.4]
        assert before_commit, seen
        for _t, revision, value in before_commit:
            assert revision <= 1
            assert value == "v1"
        for url in urls:
            assert values((await v1_flow(client, url, flow_id))["data"])["n1"] == "mp-inject-slow-commit"


async def test_wal_read_is_checkpoint_plus_replay(servers):
    """Flow.data plus the log rows after its revision is the graph a cached process serves."""
    engine, urls = servers["engine"], servers["urls"]
    async with httpx.AsyncClient(timeout=60) as client:
        flow_id = await create_flow(client, urls[0])
        for i in range(CADENCE * 3 + 2):  # past a few checkpoints, and not on one
            assert (
                await post_ops(client, urls[0], flow_id, set_field(f"n{i % BASE_NODES}", f"x{i}"))
            ).status_code == 200
        head = CADENCE * 3 + 2
        await asyncio.sleep(1.0)  # checkpoint tasks
        cached = (await v1_flow(client, urls[0], flow_id))["data"]
        built = (await v1_flow(client, urls[1], flow_id))["data"]  # never wrote: Flow.data + replay
        data, current, _latest = db_flow(flow_id)
        assert current <= head
        if servers["mode"] == "wal":
            assert current < head  # Flow.data is a checkpoint, behind the head
            assert current >= CADENCE
        else:
            assert current == head
        rows = [r for r in db_rows(flow_id) if r[1] > current]
        tail = [
            {"operations": [element["operation"]]}
            for _s, _e, envelope in rows
            for batch in envelope["batches"]
            for element in batch["operations"]
            if element["revision"] > current
        ]
        assert len(tail) == head - current
        from_db = replay(engine, data, tail)
        assert same_graph(engine, from_db, cached)
        assert same_graph(engine, built, cached)


async def test_checkpoint_never_moves_flow_data_backwards(servers):
    from langflow.services.flow_multiplayer import oplog
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlmodel.ext.asyncio.session import AsyncSession

    urls = servers["urls"]
    async with httpx.AsyncClient(timeout=60) as client:
        flow_id = await create_flow(client, urls[0])
        for i in range(CADENCE * 2):
            await post_ops(client, urls[0], flow_id, set_field("n0", f"y{i}"))
        await asyncio.sleep(1.0)
    data, current, _ = db_flow(flow_id)
    assert current >= CADENCE
    engine = create_async_engine(ADMIN_URL.replace("postgresql://", "postgresql+psycopg://"))
    try:
        async with AsyncSession(engine) as session:
            moved = await oplog.checkpoint_flow(
                session, uuid.UUID(flow_id), '{"nodes":[],"edges":[]}', revision=current - 1
            )
            same = await oplog.checkpoint_flow(session, uuid.UUID(flow_id), '{"nodes":[],"edges":[]}', revision=current)
            await session.commit()
    finally:
        await engine.dispose()
    assert not moved
    assert not same
    assert db_flow(flow_id)[:2] == (data, current)


async def test_legacy_save(servers):
    """v1 PATCH takes the same lock and diffs against the graph at the head (in WAL, not Flow.data)."""
    engine, urls = servers["engine"], servers["urls"]
    async with httpx.AsyncClient(timeout=60) as client:
        flow_id = await create_flow(client, urls[0])
        await post_ops(client, urls[0], flow_id, set_field("n0", "op1"))
        await post_ops(client, urls[1], flow_id, [{"type": "add_nodes", "nodes": [node("extra", "e")]}])

        flow = await v1_flow(client, urls[0], flow_id)
        assert flow["current_revision"] == 2
        data = flow["data"]
        data["nodes"][1]["data"]["node"]["template"]["t"]["value"] = "legacy"
        stored_before = db_flow(flow_id)
        new_name = f"renamed-{uuid.uuid4().hex[:8]}"
        saved = await client.patch(
            f"{urls[1]}/api/v1/flows/{flow_id}",
            json={"data": data, "name": new_name},
            headers={"If-Match": f'"{flow["version_token"]}"'},
        )
        assert saved.status_code == 200, saved.text
        assert saved.json()["history"]["start_revision"] == 3
        stored_after = db_flow(flow_id)
        with psycopg.connect(ADMIN_URL) as conn:
            stored_name = conn.execute("SELECT name FROM flow WHERE id = %s", (flow_id,)).fetchone()[0]
        assert stored_name == new_name  # non-graph fields update the row in every mode
        if servers["mode"] == "wal":
            # WAL: the legacy save appends log rows only; Flow.data and its revision are the checkpoint's.
            assert stored_after[:2] == stored_before[:2]
            assert stored_after[1] < 3
        else:
            assert stored_after[1] == 3
        token = saved.json()["version_token"]
        assert token == (await v1_flow(client, urls[0], flow_id))["version_token"]

        # A multiplayer write in between makes that token stale.
        await post_ops(client, urls[0], flow_id, set_field("n2", "op4"))
        stale = await client.patch(
            f"{urls[0]}/api/v1/flows/{flow_id}", json={"data": data}, headers={"If-Match": f'"{token}"'}
        )
        assert stale.status_code == 409
        assert stale.json()["detail"]["code"] == "flow_version_conflict"

        # A blind save is diffed against the head: it reverts the write in between, and nothing else.
        blind = await client.patch(f"{urls[0]}/api/v1/flows/{flow_id}", json={"data": data})
        assert blind.status_code == 200, blind.text
        assert blind.json()["history"]["start_revision"] == 5
        for url in urls:
            graph = (await v1_flow(client, url, flow_id))["data"]
            assert same_graph(engine, graph, data)
            latest, joined = await joined_graph(client, url, flow_id, engine)
            assert latest == 5
            assert same_graph(engine, joined, data)
    assert_rows_contiguous(flow_id, 5)


async def test_retention_gap(servers):
    engine, urls = servers["engine"], servers["urls"]
    total = WINDOW + CADENCE * 4
    async with httpx.AsyncClient(timeout=60) as client:
        flow_id = await create_flow(client, urls[0])
        for i in range(total):
            assert (await post_ops(client, urls[i % 2], flow_id, set_field("n0", f"r{i}"))).status_code == 200
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline and db_rows(flow_id)[0][0] == 1:  # noqa: ASYNC110 -- polls the database
            await asyncio.sleep(0.2)
        first = db_rows(flow_id)[0][0]
        assert first > 1, "history was not compacted"
        gap = await revisions(client, urls[0], flow_id, 0)
        assert gap == {"latest_revision": total, "retention_gap": True, "revisions": []}
        tail = await revisions(client, urls[1], flow_id, total - 3)
        assert tail["retention_gap"] is False
        assert [r["revision"] for r in tail["revisions"]] == [total - 2, total - 1, total]
        latest, joined = await joined_graph(client, urls[0], flow_id, engine)
        assert latest == total
        assert values(joined)["n0"] == f"r{total - 1}"
    assert_rows_contiguous(flow_id, total)


async def test_engines_and_modes_store_the_same(servers, recorded):
    """One deterministic workload: identical answers, log and graph for every engine and mode."""
    urls = servers["urls"]
    async with httpx.AsyncClient(timeout=60) as client:
        flow_id = await create_flow(client, urls[0])
        answers = []
        for i in range(24):
            _target, operations = writer_batch(i % 3, i)
            response = await post_ops(client, urls[i % 2], flow_id, operations, rid=request_id("same", i))
            answers.append((response.status_code, response.json()))
        refused = await post_ops(client, urls[0], flow_id, set_field("nope", "x"), rid=request_id("same", "refused"))
        answers.append((refused.status_code, {k: v for k, v in refused.json()["detail"].items() if k != "message"}))
        graph = (await v1_flow(client, urls[1], flow_id))["data"]
        feed = await revisions(client, urls[0], flow_id, 0)
    stored = [
        [
            (element["revision"], element["operation"])
            for batch in envelope["batches"]
            for element in batch["operations"]
        ]
        for _s, _e, envelope in db_rows(flow_id)
    ]
    result = {"answers": answers, "graph": graph, "feed": feed["revisions"], "stored": stored}
    for (mode, engine), other in recorded.items():
        for key in ("answers", "graph", "feed", "stored"):
            assert result[key] == other[key], f"{key} differs from {mode}/{engine}"
    recorded[(servers["mode"], servers["engine"])] = result
