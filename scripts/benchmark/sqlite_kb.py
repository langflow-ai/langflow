"""Reproducible local SQLite search measurements, excluding model/network time.

Example: uv run --with apsw==3.53.4.0 --with sqlite-vec==0.1.9 \
    python scripts/benchmark/sqlite_kb.py --rows 10000 --dimensions 384 1536 3072

Results describe this machine and workload, not supported capacity or an SLO.
The temporary corpus is deleted on completion. Large cases require free local
disk space proportional to rows * dimensions * 4 plus SQLite overhead.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import platform
import statistics
import tempfile
import time
from pathlib import Path
from uuid import uuid4

import numpy as np
from langchain_core.embeddings import Embeddings
from lfx.base.knowledge_bases.backends import IngestedDocument, SQLiteBackend, SQLiteStorageContext


class FixedQuery(Embeddings):
    def __init__(self, vector: list[float]) -> None:
        """Store the fixed query vector used to compare benchmark runs."""
        self.vector = vector

    def embed_documents(self, texts: list[str]) -> list[list[float]]:  # noqa: ARG002
        """Reject document embedding so the benchmark measures stored vectors alone."""
        msg = "The benchmark must import vectors without embedding documents"
        raise AssertionError(msg)

    def embed_query(self, text: str) -> list[float]:  # noqa: ARG002
        """Return the same query vector for every benchmark search."""
        return self.vector


async def benchmark(rows: int, dimensions: int, runs: int) -> dict:
    """Measure vector import and filtered search latency with deterministic inputs."""
    generator = np.random.default_rng(20261001)
    query = generator.standard_normal(dimensions, dtype=np.float32).tolist()
    with tempfile.TemporaryDirectory(prefix="lfx-sqlite-benchmark-") as directory:
        backend = SQLiteBackend(
            "benchmark",
            storage_context=SQLiteStorageContext(Path(directory).resolve(), uuid4(), uuid4()),
            embedding_function=FixedQuery(query),
            create=True,
        )
        start = time.perf_counter()
        for offset in range(0, rows, 250):
            vectors = generator.standard_normal((min(250, rows - offset), dimensions), dtype=np.float32)
            if offset == 0:
                vectors[0] = query
            await backend.add_embedded_documents(
                [
                    IngestedDocument(
                        id=f"{offset + index:012d}",
                        content=f"document {offset + index}",
                        metadata={"source_metadata": {"group": str((offset + index) % 100)}},
                        embedding=vector.tolist(),
                    )
                    for index, vector in enumerate(vectors)
                ]
            )
        ingest_seconds = time.perf_counter() - start
        timings = {}
        for label, source_filter in (("all", None), ("one_percent", {"group": ["0"]})):
            elapsed = []
            for _ in range(runs):
                start = time.perf_counter()
                results = await backend.similarity_search("query", 10, source_filter=source_filter, with_scores=True)
                elapsed.append((time.perf_counter() - start) * 1000)
                if not results or results[0][0].id != "000000000000" or results[0][1] != 0:
                    msg = "Exact self-match was not preserved"
                    raise AssertionError(msg)
            timings[label] = {
                "first_query_ms": elapsed[0],
                "median_ms": statistics.median(elapsed),
                "max_ms": max(elapsed),
            }
        result = {
            "rows": await backend.count(),
            "dimensions": dimensions,
            "runs": runs,
            "ingest_seconds": ingest_seconds,
            "storage_bytes": await backend.storage_size_bytes(),
            "queries": timings,
        }
        await backend.teardown()
        return result


async def main() -> None:
    """Run the requested SQLite benchmark and print its measurements as JSON."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=10000)
    parser.add_argument("--dimensions", type=int, nargs="+", default=[384, 1536, 3072])
    parser.add_argument("--runs", type=int, default=5)
    arguments = parser.parse_args()
    if arguments.rows < 1 or arguments.runs < 1 or any(value < 1 for value in arguments.dimensions):
        parser.error("rows, dimensions and runs must be positive")
    for dimensions in arguments.dimensions:
        result = await benchmark(arguments.rows, dimensions, arguments.runs)
        result.update(python=platform.python_version(), platform=platform.platform(), machine=platform.machine())
        print(json.dumps(result, sort_keys=True), flush=True)


if __name__ == "__main__":
    asyncio.run(main())
