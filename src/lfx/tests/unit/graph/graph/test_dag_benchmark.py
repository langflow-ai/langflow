"""Exercise the standalone QA utility through real HTTP, outside the product API."""

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from aiohttp.test_utils import TestClient, TestServer


@pytest.fixture
def benchmark(monkeypatch):
    import tracemalloc

    if tracemalloc.is_tracing():
        pytest.skip("utility requires ownership of tracing; preserve ambient tracer")
    root = Path(__file__).resolve().parents[6]
    scripts = root / "scripts" / "benchmark"
    monkeypatch.syspath_prepend(str(scripts))
    spec = importlib.util.spec_from_file_location("dag_benchmark_under_test", scripts / "dag_scheduler.py")
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    return module


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        [],
        None,
        1,
        "bad",
        {"case": "typo"},
        {"case": []},
        {"limit": 0},
        {"limit": -1},
        {"limit": True},
        {"limit": 2.0},
        {"limit": "2"},
        {"unexpected": 1},
    ],
)
async def test_proxy_invalid_request_rejected_before_service_start(benchmark, monkeypatch, payload):
    def unexpected_service():
        pytest.fail("invalid request started inference service")

    monkeypatch.setattr(benchmark, "inference_service", unexpected_service)
    async with TestClient(TestServer(benchmark.make_proxy_app())) as client:
        response = await client.post("/run", json=payload)
        assert response.status == 400


@pytest.mark.asyncio
async def test_proxy_malformed_json_rejected(benchmark):
    async with TestClient(TestServer(benchmark.make_proxy_app())) as client:
        response = await client.post("/run", data="{")
        assert response.status == 400


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [{}, {"case": "tiny", "limit": 2}])
async def test_proxy_valid_request_runs_real_graph(benchmark, payload):
    async with TestClient(TestServer(benchmark.make_proxy_app())) as client:
        response = await client.post("/run", json=payload)
        assert response.status == 200
        record = await response.json()
    assert record["case"] == payload.get("case", "asymmetric")
    assert record["limit"] == payload.get("limit")
    assert record["active_at_return"] == record["http_active_at_return"] == 0
    assert record["http_requests"] == 7


def test_provenance_binds_untracked_source_and_deletions(benchmark, tmp_path):
    git = shutil.which("git")
    assert git is not None
    subprocess.run([git, "init", "-q", str(tmp_path)], check=True)  # noqa: S603 - local test repository
    tracked = tmp_path / "tracked.py"
    tracked.write_text("one")
    subprocess.run([git, "-C", str(tmp_path), "add", "tracked.py"], check=True)  # noqa: S603
    before = benchmark.source_provenance(tmp_path)
    new = tmp_path / "new.py"
    new.write_text("first")
    added = benchmark.source_provenance(tmp_path)
    new.write_text("second")
    changed = benchmark.source_provenance(tmp_path)
    tracked.unlink()
    deleted = benchmark.source_provenance(tmp_path)
    assert len({item["source_manifest_sha"] for item in (before, added, changed, deleted)}) == 4
    assert {item["path"] for item in changed["source_manifest"]} == {"tracked.py", "new.py"}
    assert next(item for item in deleted["source_manifest"] if item["path"] == "tracked.py")["sha256"] is None


@pytest.mark.asyncio
async def test_observation_records_actual_scheduler_and_rejects_fallback(benchmark, monkeypatch):
    from lfx.graph.graph import dag_scheduler

    async with benchmark.inference_service() as service:
        full = await benchmark.observation("tiny", None, service)
        opted = await benchmark.observation("tiny", 2, service)
        assert full["scheduler"] == "default"
        assert full["scheduler_limits"] == []
        assert opted["scheduler"] == "dependency_ready"
        assert opted["scheduler_limits"] == [2]
        monkeypatch.setattr(dag_scheduler, "inspect_dag_candidate", lambda _graph: "forced fallback")
        with pytest.raises(RuntimeError, match="scheduler"):
            await benchmark.observation("tiny", 2, service)


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["failure", "cancel"])
async def test_observation_restores_tracer_and_scheduler_on_every_exit(benchmark, monkeypatch, mode):
    import asyncio
    import tracemalloc

    from lfx.graph import Graph
    from lfx.graph.graph import dag_scheduler

    assert not tracemalloc.is_tracing()
    original = dag_scheduler.execute_dependency_ready

    async def fail(*_args, **_kwargs):
        if mode == "cancel":
            raise asyncio.CancelledError
        msg = "controlled failure"
        raise RuntimeError(msg)

    monkeypatch.setattr(Graph, "arun", fail)
    error = asyncio.CancelledError if mode == "cancel" else RuntimeError
    async with benchmark.inference_service() as service:
        with pytest.raises(error):
            await benchmark.observation("tiny", 2, service)
    assert not tracemalloc.is_tracing()
    assert dag_scheduler.execute_dependency_ready is original


@pytest.mark.asyncio
async def test_external_tracer_is_preserved(benchmark):
    import tracemalloc

    tracemalloc.start()
    try:
        async with benchmark.inference_service() as service:
            with pytest.raises(RuntimeError, match="tracing"):
                await benchmark.observation("tiny", 2, service)
        assert tracemalloc.is_tracing()
    finally:
        tracemalloc.stop()


@pytest.mark.asyncio
async def test_overlapping_proxy_observations_do_not_overlap_owned_tracing(benchmark, monkeypatch):
    import asyncio
    import tracemalloc

    original_start = tracemalloc.start
    original_stop = tracemalloc.stop
    active = peak = 0

    def start():
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        original_start()

    def stop():
        nonlocal active
        active -= 1
        original_stop()

    monkeypatch.setattr(tracemalloc, "start", start)
    monkeypatch.setattr(tracemalloc, "stop", stop)
    async with TestClient(TestServer(benchmark.make_proxy_app())) as client:
        responses = await asyncio.gather(
            client.post("/run", json={"case": "tiny", "limit": 2}),
            client.post("/run", json={"case": "tiny", "limit": 2}),
        )
        assert [response.status for response in responses] == [200, 200]
        records = [await response.json() for response in responses]
        assert all(record["scheduler_limits"] == [2] and record["peak_bytes"] > 0 for record in records)
    assert active == 0
    assert peak == 1
    assert not tracemalloc.is_tracing()


def test_observations_support_separate_sequential_event_loops(benchmark):
    import asyncio

    async def run():
        async with benchmark.inference_service() as service:
            return await benchmark.observation("tiny", 2, service)

    for _ in range(2):
        assert asyncio.run(run())["scheduler_limits"] == [2]


def test_cross_thread_event_loop_rejected_before_shared_state(benchmark, monkeypatch):
    import asyncio
    import threading
    import tracemalloc
    from concurrent.futures import ThreadPoolExecutor

    from lfx.graph import Graph
    from lfx.graph.graph import dag_scheduler

    entered = threading.Event()
    release = threading.Event()
    original = dag_scheduler.execute_dependency_ready

    async def blocked_run(*_args, **_kwargs):
        entered.set()
        await asyncio.to_thread(release.wait, 5)
        msg = "controlled first run exit"
        raise RuntimeError(msg)

    monkeypatch.setattr(Graph, "arun", blocked_run)

    async def observe():
        async with benchmark.inference_service() as service:
            return await benchmark.observation("tiny", 2, service)

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(asyncio.run, observe())
        try:
            assert entered.wait(5)
            second = pool.submit(asyncio.run, observe())
            with pytest.raises(RuntimeError, match="Another event loop"):
                second.result(timeout=5)
        finally:
            release.set()
        with pytest.raises(RuntimeError, match="controlled first run exit"):
            first.result(timeout=5)
    assert dag_scheduler.execute_dependency_ready is original
    assert not tracemalloc.is_tracing()
