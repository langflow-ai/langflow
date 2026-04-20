# Cold-Start Benchmark Harness

This harness measures `lfx run` (bare boot + with-flow) and `langflow run` cold-start
latency. It is the measurement foundation for the cold-start improvements effort.

## Entry points

Two Makefile targets, two very different meanings:

| Target | Use for | Authoritative? |
|--------|---------|----------------|
| `make bench-docker` | Runs inside a fresh `python:3.13-slim` container. Fresh container per measurement via `hyperfine --prepare 'docker rm -f ...'`. Produces CI-comparable numbers. | Yes |
| `make bench-local` | Runs against the dev venv on the host. No cold-cache prep. Fast iteration only. | No. NOT comparable to CI or the committed baseline. |

`bench-docker` is the only source of numbers that can be compared to the baseline
committed in `thresholds.json`. `bench-local` is strictly for fast iteration.

## Layout (filled in as later plans land)

```
src/backend/tests/benchmarks/
├── __init__.py             # plan 01
├── conftest.py             # plan 01 (pytest opt-out); extended in plan 02 (mock fixture)
├── README.md               # plan 01 (this file)
├── reports/                # driver output; gitignored except .gitkeep
├── fixtures/               # plan 02: basic_prompting, document_qa, no-op flow
├── mock_llm.py             # plan 02: BaseChatOpenAI._generate/._agenerate monkey-patch
├── Dockerfile              # plan 04: python:3.13-slim + uv + hyperfine; ARG BENCH_VARIANT=lean|prebaked
├── driver.py               # plan 05: hyperfine wrapper, pyinstrument + -X importtime capture, baseline writer
├── scenarios/              # plan 05: lfx_bare.py, lfx_with_flow.py, langflow_run.py
├── snapshot.py             # plan 05: one-shot baseline capture + thresholds.json write
└── thresholds.json         # plan 06: committed baseline numbers for CI regression gate
```

## Hyperfine flag rationale

`--warmup 0`: default is 3 warmup runs. For cold-start we MUST NOT warm caches.

`--prepare 'docker rm -f lfx-bench 2>/dev/null || true'`: destroys the ephemeral
container BEFORE EACH TIMING RUN so every measurement starts from cold image boot.

`--min-runs 5 --max-runs 10`: enough samples to detect outliers without burning CI.

`--export-json reports/<scenario>.json`: structured output for the diff/gate logic.

`--shell sh`: smaller shell, less noise on the measurement.

## Why `src/backend/tests/benchmarks/` is NOT collected by pytest

These scripts are subprocess entry points for `hyperfine` and `pyinstrument`. They
are not assertions. The sibling `conftest.py` sets `collect_ignore_glob = ["*.py"]`
so `uv run pytest src/backend/tests` skips this tree.

## Installing the benchmark deps

From repo root: `uv sync --group benchmarks`

Brings in `pyinstrument`, `importtime-convert`, `importtime-waterfall`. None of these
are runtime deps for `lfx` or `langflow`; they live in the `benchmarks` optional
group only.
