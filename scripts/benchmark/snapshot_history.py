"""Reproducible standalone snapshot-history measurements (not application throughput).

Run from an LFX environment with PYTHONPATH pointed at the source being measured.
Use --baseline to omit the new constructor keyword on pristine source.
"""

from __future__ import annotations

import argparse
import asyncio
import gc
import hashlib
import importlib.metadata
import json
import platform
import resource
import sys
import time
import tracemalloc
from itertools import pairwise

from lfx.custom import Component
from lfx.graph import Graph
from lfx.io import MessageInput, Output
from lfx.schema.message import Message


class Passthrough(Component):
    inputs = [MessageInput(name="value")]
    outputs = [Output(name="message", method="run")]

    def run(self) -> Message:
        return self.value or Message(text="echo")


# Private diagnostics are precisely what this benchmark measures.
# ruff: noqa: SLF001


async def sample(size: int, runs: int, limit: int | None, *, baseline: bool) -> dict:
    gc.collect()
    nodes = [Passthrough(_id=f"p{i}") for i in range(size)]
    for previous, node in pairwise(nodes):
        node.set(value=previous.run)
    kwargs = {} if baseline or limit is None else {"snapshot_history_limit": limit}
    tracemalloc.start()
    started = time.perf_counter()
    graph = Graph(nodes[0], nodes[-1], **kwargs)
    construction_ms = (time.perf_counter() - started) * 1000
    graph.persist_messages = False
    latencies = []
    outputs = []
    for _ in range(runs):
        started = time.perf_counter()
        results = [result async for result in graph.async_start()]
        latencies.append((time.perf_counter() - started) * 1000)
        outputs.append({"count": len(results), "text": graph.vertices[-1].built_object["message"].text})
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return {
        "size": size,
        "runs": runs,
        "limit": limit,
        "baseline": baseline,
        "construction_ms": construction_ms,
        "run_ms": latencies,
        "tracemalloc_peak_bytes": peak,
        "process_max_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "history_length": len(graph._snapshots),
        "call_order_length": len(graph._call_order),
        "history_shallow_bytes": sys.getsizeof(graph._snapshots) + sum(sys.getsizeof(s) for s in graph._snapshots),
        "output_digest": hashlib.sha256(json.dumps(outputs, sort_keys=True).encode()).hexdigest(),
        "call_order_digest": hashlib.sha256(json.dumps(graph._call_order).encode()).hexdigest(),
        "chat_service": None,
        "whole_graph_cache_per_step": False,
        "events": "no event manager attached",
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", action="store_true")
    parser.add_argument("--start-sample", type=int, default=0)
    parser.add_argument("--policy", choices=["full", "0", "1", "16"])
    parser.add_argument("--size", type=int, required=True)
    parser.add_argument("--runs", type=int, default=2)
    parser.add_argument("--samples", type=int, default=5)
    parser.add_argument("--bounded-only", action="store_true")
    args = parser.parse_args()
    if args.baseline and (args.bounded_only or args.policy not in (None, "full")):
        parser.error("--baseline requires full history; incompatible with bounded policies")
    policies = [None] if args.baseline else [0, 1, 16] if args.bounded_only else [None, 0, 1, 16]
    if args.policy is not None:
        policies = [None if args.policy == "full" else int(args.policy)]
    environment = {
        "python": platform.python_version(),
        "platform": platform.system(),
        "graph_module": Graph.__module__,
        "dependencies": {name: importlib.metadata.version(name) for name in ["pydantic", "langchain-core"]},
        "rss_note": "process high-water mark, not per-sample allocation",
        "cache_backend": None,
    }
    print(json.dumps({"environment": environment}), flush=True)
    # One excluded warmup for each policy. Alternating sample order reduces monotonic drift.
    for policy in policies:
        await sample(args.size, args.runs, policy, baseline=args.baseline)
    for index in range(args.start_sample, args.start_sample + args.samples):
        for policy in policies if index % 2 == 0 else list(reversed(policies)):
            record = await sample(args.size, args.runs, policy, baseline=args.baseline)
            print(json.dumps({"sample": index, **record}), flush=True)


if __name__ == "__main__":
    asyncio.run(main())
