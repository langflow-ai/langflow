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
