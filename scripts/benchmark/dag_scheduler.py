"""Paired real Graph.arun benchmark using loopback HTTP custom components.

Run in the locked lfx environment, from the repository root:
  python scripts/benchmark/dag_scheduler.py --pairs 7 --output /tmp/dag.json
A new Graph is built for every observation; no cached same-Graph comparisons.
Supported invocations: this script directly from the source checkout, or its
--serve loopback proxy, with one active observation loop per process. Concurrent
other-loop observations fail fast; they are not parallel measurement support.
Proxy peaks include process-wide framework/service allocations outside the
observation lock. Serialization prevents cross-stop, not allocation isolation.
Use the sequential CLI for controlled paired comparisons, not concurrent proxy peaks.
Namespace-package installations without a concrete lfx.__file__ may fail during
Graph.arun; use the source checkout environment, not this utility as a package API.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import platform
import shutil
import subprocess
import threading
import time
import tracemalloc
import weakref
from pathlib import Path

from aiohttp import ClientSession, web
from dag_inference_service import inference_service
from lfx.custom.custom_component.component import Component
from lfx.graph import Graph
from lfx.graph.graph import dag_scheduler as graph_dag_scheduler
from lfx.io import FloatInput, HandleInput, Output, StrInput
from lfx.schema.message import Message


class LocalInference(Component):
    """Materialized adapter; all request/session work is owned and awaited."""

    supports_dependency_ready_scheduling = True
    inputs = [
        HandleInput(name="messages", input_types=["Message"], is_list=True),
        StrInput(name="endpoint"),
        StrInput(name="operation", value="infer"),
        FloatInput(name="latency", value=0),
    ]
    outputs = [Output(name="message", method="infer")]

    async def infer(self) -> Message:
        text = " ".join(message.text for message in (self.messages or [])) or "Example DOCUMENT"
        async with (
            ClientSession() as session,
            session.post(
                self.endpoint,
                json={"id": self._id, "text": text, "delay": self.latency, "operation": self.operation},
            ) as response,
        ):
            response.raise_for_status()
            data = await response.json()
        if not session.closed:
            msg = "HTTP session was not closed"
            raise RuntimeError(msg)
        return Message(text=data["text"])


def make_graph(case: str, endpoint: str) -> Graph:
    delays = {"a1": 0.25, "a2": 0.01, "b1": 0.01, "b2": 0.25}
    if case == "reverse":
        delays = {"a1": 0.01, "a2": 0.25, "b1": 0.25, "b2": 0.01}
    elif case == "balanced":
        delays = dict.fromkeys(delays, 0.13)
    elif case == "tiny":
        delays = dict.fromkeys(delays, 0)
    if case == "wide":
        names = ["input", *(f"branch{i}" for i in range(16)), "out"]
        parents = {name: ["input"] for name in names[1:-1]}
        parents["out"] = names[1:-1]
        delays = dict.fromkeys(names[1:-1], 0.01)
    else:
        names = ["input", "a1", "a2", "b1", "b2", "join", "out"]
        parents = {"a1": ["input"], "a2": ["a1"], "b1": ["input"], "b2": ["b1"], "join": ["a2", "b2"], "out": ["join"]}
    nodes = {
        name: LocalInference(
            _id=name,
            endpoint=endpoint,
            latency=delays.get(name, 0),
            operation="extract" if name in {"a2", "b1"} else "infer",
        )
        for name in names
    }
    for name, dependencies in parents.items():
        nodes[name].set(messages=[nodes[parent].infer for parent in dependencies])
    return Graph(nodes["input"], nodes["out"])


# Observations are supported on one event loop per process (the CLI/proxy model).
# Locks are loop-local so separate sequential asyncio.run calls remain usable.
_observation_locks = weakref.WeakKeyDictionary()
_process_observation_guard = threading.Lock()


async def observation(case, limit, service):
    loop = asyncio.get_running_loop()
    lock = _observation_locks.setdefault(loop, asyncio.Lock())
    async with lock:
        # Do not block an event-loop thread waiting on another loop's observation.
        if not _process_observation_guard.acquire(blocking=False):
            msg = "Another event loop already owns benchmark observation state"
            raise RuntimeError(msg)
        try:
            if tracemalloc.is_tracing():
                msg = "Cannot measure while external memory tracing is active"
                raise RuntimeError(msg)
            return await _observation(case, limit, service)
        finally:
            _process_observation_guard.release()


async def _observation(case, limit, service):
    graph = make_graph(case, service.url)
    service.events.clear()
    service.requests = service.peak = 0
    events = []
    active = 0
    peak = 0
    original = graph.build_vertex

    async def build(vertex_id, **kwargs):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        events.append((vertex_id, "start", time.perf_counter()))
        try:
            return await original(vertex_id=vertex_id, **kwargs)
        finally:
            active -= 1
            events.append((vertex_id, "end", time.perf_counter()))

    graph.build_vertex = build
    original_execute = graph_dag_scheduler.execute_dependency_ready
    scheduler_limits = []

    async def witnessed_execute(*args, **kwargs):
        # Graph.__eq__ compares representations, so use identity, not equality.
        if args and args[0] is graph:
            scheduler_limits.append(kwargs.get("max_concurrency"))
        return await original_execute(*args, **kwargs)

    graph_dag_scheduler.execute_dependency_ready = witnessed_execute
    owns_tracing = False
    try:
        tracemalloc.start()
        owns_tracing = True
        start = time.perf_counter()
        await graph.arun(inputs=[{}], outputs=["out"], dag_max_concurrency=limit)
        elapsed_ms = (time.perf_counter() - start) * 1000
        _, peak_bytes = tracemalloc.get_traced_memory()
    finally:
        if owns_tracing:
            tracemalloc.stop()
        graph_dag_scheduler.execute_dependency_ready = original_execute
        graph.build_vertex = original
    # Exactly one process call is expected because this utility supplies one input.
    if scheduler_limits != ([] if limit is None else [limit]):
        msg = "Requested scheduler did not match the scheduler that ran"
        raise RuntimeError(msg)
    text = graph.get_vertex("out").built_object["message"].text
    if active or service.active:
        msg = "Owned HTTP/build work survived Graph.arun"
        raise RuntimeError(msg)
    return {
        "case": case,
        "limit": limit,
        "scheduler": "default" if limit is None else "dependency_ready",
        "scheduler_limits": scheduler_limits,
        "elapsed_ms": elapsed_ms,
        "first_component_output_ms": min(t for _, event, t in events if event == "end") * 1000 - start * 1000,
        "peak_admitted": peak,
        "peak_http": service.peak,
        "http_requests": service.requests,
        "active_at_return": active,
        "http_active_at_return": service.active,
        "peak_bytes": peak_bytes,
        "digest": hashlib.sha256(text.encode()).hexdigest(),
        "text": text,
        "timeline": [(vertex, event, (t - start) * 1000) for vertex, event, t in events],
        "http_timeline": [(vertex, event, (t - start) * 1000) for vertex, event, t in service.events],
    }


def source_provenance(root: Path, *, exclude: Path | None = None):
    """Bind tracked and non-ignored new file bytes, including deleted paths."""
    git = shutil.which("git")
    if git is None:
        msg = "git is required for source provenance"
        raise RuntimeError(msg)
    paths = subprocess.check_output(  # noqa: S603 - resolved executable, fixed git subcommand
        [git, "-C", str(root), "ls-files", "-z", "--cached", "--others", "--exclude-standard"]
    )
    manifest = []
    for name in sorted(set(paths.decode().split("\0")) - {""}):
        path = root / name
        if exclude is not None and path.resolve() == exclude.resolve():
            continue
        manifest.append(
            {"path": name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None}
        )
    encoded = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    return {"source_manifest": manifest, "source_manifest_sha": hashlib.sha256(encoded).hexdigest()}


async def run(pairs, *, output_path: Path | None = None):
    root = Path(__file__).resolve().parents[2]
    provenance = await asyncio.to_thread(source_provenance, root, exclude=output_path)
    records = []
    async with inference_service() as service:
        for case in ("asymmetric", "reverse", "balanced", "tiny", "wide"):
            limit = 8 if case == "wide" else 2
            for mode in (None, limit):
                await observation(case, mode, service)
            for pair in range(pairs):
                modes = (None, limit) if pair % 2 == 0 else (limit, None)
                pair_records = []
                for mode in modes:
                    record = await observation(case, mode, service)
                    record["pair"] = pair
                    records.append(record)
                    pair_records.append(record)
                if pair_records[0]["digest"] != pair_records[1]["digest"]:
                    msg = "Baseline and dependency-ready outputs differ"
                    raise AssertionError(msg)
    after = await asyncio.to_thread(source_provenance, root, exclude=output_path)
    if after != provenance:
        msg = "Source bytes changed during benchmark"
        raise RuntimeError(msg)
    git = shutil.which("git")
    base_sha = await asyncio.to_thread(subprocess.check_output, [git, "-C", str(root), "rev-parse", "HEAD"], text=True)
    tracked_diff = await asyncio.to_thread(subprocess.check_output, [git, "-C", str(root), "diff", "HEAD"])
    return {
        **provenance,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "base_sha": base_sha.strip(),
        "tracked_diff_sha": hashlib.sha256(tracked_diff).hexdigest(),
        "scope": "Controlled loopback HTTP adapter, not commercial model/provider throughput.",
        "records": records,
    }


def make_proxy_app():
    """Test proxy for independent QA, not a product HTTP API."""

    async def execute(request):
        try:
            payload = await request.json()
        except (ValueError, UnicodeError) as exc:
            raise web.HTTPBadRequest(text="Expected a JSON object") from exc
        cases = {"asymmetric", "reverse", "balanced", "tiny", "wide"}
        if not isinstance(payload, dict) or set(payload) - {"case", "limit"}:
            raise web.HTTPBadRequest(text="Expected case and/or limit")
        case, limit = payload.get("case", "asymmetric"), payload.get("limit")
        if not isinstance(case, str) or case not in cases:
            raise web.HTTPBadRequest(text="Unknown benchmark case")
        if limit is not None and (type(limit) is not int or limit <= 0):
            raise web.HTTPBadRequest(text="limit must be a positive integer or null")
        # Each proxy request owns its metrics/service to avoid cross-run counters.
        async with inference_service() as service:
            return web.json_response(await observation(case, limit, service))

    app = web.Application()
    app.router.add_post("/run", execute)
    return app


async def serve():
    runner = web.AppRunner(make_proxy_app())
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 8766)
    await site.start()
    print("Test proxy listening on http://127.0.0.1:8766/run", flush=True)
    try:
        await asyncio.Event().wait()
    finally:
        await runner.cleanup()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pairs", type=int, default=7)
    parser.add_argument("--output", type=Path, default=Path("dag-scheduler.json"))
    parser.add_argument("--serve", action="store_true")
    args = parser.parse_args()
    if args.serve:
        asyncio.run(serve())
    else:
        result = asyncio.run(run(args.pairs, output_path=args.output))
        args.output.write_text(json.dumps(result, indent=2))
        print(args.output)
