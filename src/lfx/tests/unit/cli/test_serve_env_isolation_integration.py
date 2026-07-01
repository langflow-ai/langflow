"""End-to-end env-isolation tests for `lfx serve` (spawns a live multi-worker server).

Demonstrates the actual security guarantee — caller A writes os.environ, caller B
must not read it — across real worker processes, which can only be observed with
live processes, not in-process unit tests.

Probe flow: a component writes a canary to os.environ and reports whether it SAW a
prior write. What the scenarios establish about each isolation knob:
- ``--workers 1 --reset-environ``: single persistent process, yet ``clean`` every
  request — isolation comes from the per-run os.environ snapshot/restore, not a fresh
  process. (Without --reset-environ this same setup LEAKS, proving the hazard is real.)
- ``--workers 2 --max-requests 1 --reset-environ``: warm workers (recycling does the
  work of hygiene, --reset-environ does the work of isolation) -> ``clean``.
- ``--workers 2 --use-sync-workers``: the blocking sync worker exits synchronously after
  each request, so requests land on fresh processes -> ``clean``.
- ``--workers 2 --max-requests 1`` ALONE (async, no --reset-environ): XFAILS -> the
  async worker recycles gracefully, so a winding-down worker still serves later
  requests and LEAKS. Recycling is NOT a per-request isolation guarantee here; only
  --use-sync-workers or --reset-environ are.

Skipped in CI (spawns gunicorn + a real server; slow) — run locally as a harness.
"""

import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from pathlib import Path

import pytest

_is_ci = os.environ.get("CI", "").lower() in {"1", "true", "yes"}
pytestmark = [
    pytest.mark.skipif(_is_ci, reason="spawns a live multi-worker server; not for fast CI"),
    pytest.mark.skipif(sys.platform == "win32", reason="isolation path uses gunicorn (Unix-only)"),
]

PROBE_FLOW = """
import os
from lfx.components.input_output import ChatInput, ChatOutput
from lfx.custom import Component
from lfx.graph import Graph
from lfx.io import MessageTextInput, Output
from lfx.schema.message import Message

PROBE_KEY = "LFX_LEAK_PROBE"
CANARY = "SECRET-CANARY-VALUE"


class EnvLeakProbe(Component):
    display_name = "Env Leak Probe"
    inputs = [MessageTextInput(name="input_value", display_name="Input")]
    outputs = [Output(name="status", display_name="Status", method="get_status")]

    def get_status(self) -> Message:
        seen = os.environ.get(PROBE_KEY)
        os.environ[PROBE_KEY] = CANARY
        status = "LEAKED" if seen == CANARY else "clean"
        return Message(text=f"{status}|pid={os.getpid()}")


chat_input = ChatInput()
leak = EnvLeakProbe().set(input_value=chat_input.message_response)
chat_output = ChatOutput().set(input_value=leak.get_status)
graph = Graph(chat_input, chat_output)
"""

_API_KEY = "leak-test-key"  # pragma: allowlist secret


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _get(url: str):
    req = urllib.request.Request(url, headers={"x-api-key": _API_KEY})  # noqa: S310
    with urllib.request.urlopen(req, timeout=5) as resp:  # noqa: S310
        return json.load(resp)


def _run_flow(port: int, flow_id: str, value: str) -> str:
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/flows/{flow_id}/run",
        data=json.dumps({"input_value": value}).encode(),
        method="POST",
        headers={"x-api-key": _API_KEY, "content-type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
        return json.load(resp)["result"]


@contextmanager
def _serve(tmp_path: Path, extra_args: list[str]):
    flow = tmp_path / "leak_flow.py"
    flow.write_text(PROBE_FLOW, encoding="utf-8")
    port = _free_port()
    log = (tmp_path / "server.log").open("w")
    env = {**os.environ, "LANGFLOW_API_KEY": _API_KEY}
    proc = subprocess.Popen(  # noqa: S603
        [sys.executable, "-m", "lfx", "serve", str(flow), "--host", "127.0.0.1", "--port", str(port), *extra_args],
        env=env,
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    try:
        flow_id = _wait_ready(port, proc, tmp_path)
        yield port, flow_id
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        log.close()


def _wait_ready(port: int, proc: subprocess.Popen, tmp_path: Path, timeout: float = 120.0) -> str:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            log = (tmp_path / "server.log").read_text(encoding="utf-8")
            msg = f"serve exited early (code {proc.returncode}):\n{log[-2000:]}"
            raise RuntimeError(msg)
        try:
            flows = _get(f"http://127.0.0.1:{port}/flows")
            if flows:
                return flows[0]["id"]
        except (urllib.error.URLError, ConnectionError, TimeoutError, OSError):
            pass
        time.sleep(1)
    msg = "serve did not become ready in time"
    raise RuntimeError(msg)


def _statuses(results):
    # Each result is "clean|pid=NNNN" or "LEAKED|pid=NNNN".
    return [r.split("|", 1)[0] for r in results]


def test_no_env_leak_multi_worker_warm(tmp_path):
    """workers=2 with warm long-lived workers (--max-requests 0, no recycling) -> no env leak.

    This is the production model: workers are NOT recycled per request, so isolation comes
    entirely from per-request os.environ snapshot/restore, even as each warm worker serves
    many requests.
    """
    with _serve(tmp_path, ["--workers", "2", "--max-requests", "0", "--reset-environ"]) as (port, fid):
        results = [_run_flow(port, fid, f"req{i}") for i in range(12)]
    assert _statuses(results) == ["clean"] * 12, results


def test_no_env_leak_single_worker(tmp_path):
    """workers=1 (single persistent process, NO recycling) -> still no cross-request leak.

    This is the strongest demonstration that per-request os.environ snapshot/restore in
    ``guarded_execute`` is what enforces isolation: every request is served by the SAME
    process (recycling never happens here), yet none sees a prior request's env write.
    Before that fix, this exact scenario leaked from the 2nd request onward.
    """
    with _serve(tmp_path, ["--workers", "1", "--reset-environ"]) as (port, fid):
        results = [_run_flow(port, fid, f"req{i}") for i in range(12)]
    assert _statuses(results) == ["clean"] * 12, results
    # All requests served by the same process (no recycling) -> isolation came from
    # per-request env restore, not from a fresh process.
    pids = {r.split("pid=", 1)[1] for r in results if "pid=" in r}
    assert len(pids) == 1, f"expected a single reused worker process, got pids={pids} results={results}"


@pytest.mark.xfail(
    strict=True,
    reason=(
        "KNOWN LIMITATION: async --max-requests recycling does NOT give per-request isolation. "
        "uvicorn honors limit_max_requests (logs 'Maximum request limit exceeded. Terminating "
        "process.') but the async worker shuts down GRACEFULLY/asynchronously — during the "
        "deferred-exit window the still-alive worker keeps accepting and serving new requests, so "
        "os.environ written by an earlier request LEAKS into a later one before the process exits. "
        "Observed (workers=2, max_requests=1): recurring LEAKED across requests. Strict per-request "
        "isolation IS available via --use-sync-workers (synchronous handle->check->exit; verified 8/8 "
        "clean, 8 distinct PIDs) or via --reset-environ (env snapshot/restore). Remove this xfail "
        "only if the async path is made to isolate (e.g. disable HTTP keep-alive + stop accepting "
        "on the recycling worker so a dying worker cannot serve a second request)."
    ),
)
def test_no_env_leak_multi_worker_recycle_async(tmp_path):
    """workers=2 async worker with --max-requests 1 (no --reset-environ) -> SHOULD isolate, but leaks.

    The module docstring's structural-isolation model assumes each request runs in a freshly-forked,
    recycled worker. On the async (uvicorn) worker that does not hold: recycling is graceful/deferred,
    so a worker keeps serving while it winds down and leaks a prior request's os.environ write.

    Currently XFAILS — see decorator. The working isolation paths are --use-sync-workers and
    --reset-environ; this test documents the async gap and will flip to passing if it's closed.
    """
    with _serve(tmp_path, ["--workers", "2", "--max-requests", "1"]) as (port, fid):
        results = [_run_flow(port, fid, f"req{i}") for i in range(12)]
    assert _statuses(results) == ["clean"] * 12, results


def test_sync_workers_serves_requests(tmp_path):
    """--use-sync-workers (gunicorn sync worker + a2wsgi bridge) serves requests via the real CLI.

    Proves the opt-in sync-worker path boots and the ASGI->WSGI bridge handles requests,
    and that --reset-environ still enforces isolation under the sync worker.
    """
    with _serve(tmp_path, ["--workers", "2", "--use-sync-workers", "--reset-environ"]) as (port, fid):
        results = [_run_flow(port, fid, f"req{i}") for i in range(8)]
    assert all("pid=" in r for r in results), results  # the a2wsgi bridge served every request
    assert _statuses(results) == ["clean"] * 8, results  # reset-environ holds under sync worker
