"""Compare the actual base/head completed-task methods at INFO and DEBUG.

Run: uv run python scripts/benchmark/graph_result_logging.py
This isolates result handling with completed-vertex fixtures and a real filtering
structlog logger. It is not a complete graph or endpoint latency benchmark.
"""

# Standalone local benchmark deliberately loads the pinned base method and prints samples.
# ruff: noqa: S101, S102, SLF001
import argparse
import ast
import asyncio
import json
import logging
from statistics import median
from time import perf_counter_ns
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd
import structlog
from lfx.graph import Graph
from lfx.graph.graph import base as graph_module
from lfx.graph.graph.schema import VertexBuildResult
from structlog.testing import ReturnLogger

BASELINE = "04cd19bc"


async def load_baseline():
    """Compile the verified baseline method with the same runtime dependencies."""
    process = await asyncio.create_subprocess_exec(
        "git", "show", f"{BASELINE}:src/lfx/src/lfx/graph/graph/base.py", stdout=asyncio.subprocess.PIPE
    )
    output, _ = await process.communicate()
    if process.returncode:
        message = "Baseline Git revision is unavailable"
        raise RuntimeError(message)
    tree = ast.parse(output.decode())
    method = next(
        node for node in ast.walk(tree) if isinstance(node, ast.AsyncFunctionDef) and node.name == "_execute_tasks"
    )
    module = ast.Module(
        body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0), method],
        type_ignores=[],
    )
    namespace = dict(vars(graph_module))
    exec(compile(ast.fix_missing_locations(module), "base_graph_result_logging", "exec"), namespace)
    return namespace["_execute_tasks"], namespace


async def measure(repeats, iterations, vertices):
    """Interleave full method calls with task creation and the same logger/scheduler stubs."""
    baseline, namespace = await load_baseline()
    result = []
    for level in (logging.INFO, logging.DEBUG):
        log = structlog.wrap_logger(
            ReturnLogger(), processors=[], wrapper_class=structlog.make_filtering_bound_logger(level)
        ).bind(run_id="benchmark")
        namespace["logger"] = log
        for shape in ("scalar", "nested", "dataframe"):
            value = {
                "scalar": 42,
                "nested": {"rows": [{"text": "a" * 30, "n": i} for i in range(30)]},
                "dataframe": pd.DataFrame({f"column{i}": range(200) for i in range(8)}),
            }[shape]
            graph = Graph()

            async def no_successors(*_args, **_kwargs):
                """Keep topology work identical and outside the selected formatting question."""
                return []

            graph.get_next_runnable_vertices = no_successors
            completed = [
                VertexBuildResult(
                    result_dict={},
                    params="{}",
                    valid=True,
                    artifacts={},
                    vertex=SimpleNamespace(id=f"v{i}", built_result=value, built_object=value),
                )
                for i in range(vertices)
            ]

            async def batch(method, graph=graph, completed=completed):
                """Build actual tasks for the graph method's gather/iteration path."""

                async def ready(row):
                    """Return an already-built vertex without conversion."""
                    return row

                tasks = [asyncio.create_task(ready(row), name=row.vertex.id) for row in completed]
                assert await method(graph, tasks, asyncio.Lock()) == []

            samples = {"base": [], "head": []}
            with patch.object(graph_module, "logger", log):
                for repetition in range(repeats + 1):
                    for name, method in (
                        (("base", baseline), ("head", Graph._execute_tasks))
                        if repetition % 2
                        else (("head", Graph._execute_tasks), ("base", baseline))
                    ):
                        started = perf_counter_ns()
                        for _ in range(iterations):
                            await batch(method)
                        milliseconds = (perf_counter_ns() - started) / iterations / 1e6
                        if repetition:
                            samples[name].append(milliseconds)
            result.append(
                {
                    "level": "INFO" if level == logging.INFO else "DEBUG",
                    "shape": shape,
                    "vertices": vertices,
                    "samples_ms": samples,
                    "median_ms": {name: median(rows) for name, rows in samples.items()},
                }
            )
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=7)
    parser.add_argument("--iterations", type=int, default=5)
    parser.add_argument("--vertices", type=int, default=12)
    args = parser.parse_args()
    print(json.dumps(asyncio.run(measure(args.repeats, args.iterations, args.vertices)), indent=2))
