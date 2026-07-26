"""Build and pin the performance-suite flow fixtures.

Generates isolator flows via ``Graph.dump`` (embedding the committed custom-component
sources), copies pinned fixtures, and builds generated-equivalent KB/outbound graphs.
Writes ``flows/fixture_index.json`` with content hashes for every fixture.

``Graph.dump`` assigns fresh node IDs on every rebuild, so a full ``build_all``
rewrites *all* generated fixtures even when only one isolator changed. Prefer
rebuilding only when component sources or graph topology change, and keep
unrelated fixture diffs out of PRs (restore + selective rebuild, or accept the
noise only when intentionally refreshing the whole set).

Run from ``src/backend``::

    PYTHONPATH=. uv run python -m tests.locust.langflow_runtime.flows.build_fixtures
    PYTHONPATH=. uv run python -m tests.locust.langflow_runtime.flows.build_fixtures --check
"""

from __future__ import annotations

import argparse
import sys
from typing import TYPE_CHECKING

from tests.locust.langflow_runtime.flows import validate_fixtures
from tests.locust.langflow_runtime.flows.builders import (
    build_cpu_graph,
    build_disk_io,
    build_ensemble_journey,
    build_ensemble_journey_hitl,
    build_kb_ingest,
    build_kb_retrieve,
    build_multiproc_churn,
    build_outbound_basic_prompting,
    build_passthrough,
    build_payload_echo,
    build_queue_short,
    build_webhook_passthrough,
    copy_human_input_flow,
    copy_memory_chatbot,
)
from tests.locust.langflow_runtime.flows.defaults import (
    COMPONENTS_DIR,
    DEFAULT_QUEUE_INPUT,
    DEFAULT_QUEUE_SLEEP_MS,
    FIXTURES_DIR,
    FLOWS_DIR,
)
from tests.locust.langflow_runtime.flows.fixture_index import build_fixture_index
from tests.locust.langflow_runtime.hashing import component_source_hashes as _component_source_hashes
from tests.locust.langflow_runtime.hashing import sha256_file

if TYPE_CHECKING:
    from pathlib import Path

__all__ = [
    "DEFAULT_QUEUE_INPUT",
    "DEFAULT_QUEUE_SLEEP_MS",
    "build_all",
    "component_source_hashes",
    "main",
]


def component_source_hashes() -> dict[str, str]:
    return _component_source_hashes(COMPONENTS_DIR)


def build_all() -> dict[str, Path]:
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    paths = {
        "perf_passthrough.json": build_passthrough(),
        "perf_webhook_passthrough.json": build_webhook_passthrough(),
        "MemoryChatbotNoLLM.json": copy_memory_chatbot(),
        "human_input_flow.json": copy_human_input_flow(),
        "perf_queue_short.json": build_queue_short(),
        "perf_kb_ingest.json": build_kb_ingest(),
        "perf_kb_retrieve.json": build_kb_retrieve(),
        "perf_cpu_graph.json": build_cpu_graph(),
        "perf_multiproc_churn.json": build_multiproc_churn(),
        "perf_disk_io.json": build_disk_io(),
        "perf_payload_echo.json": build_payload_echo(),
        "perf_outbound_basic_prompting.json": build_outbound_basic_prompting(),
        "perf_ensemble_journey.json": build_ensemble_journey(),
        "perf_ensemble_journey_hitl.json": build_ensemble_journey_hitl(),
    }
    allowed = set(paths)
    for path in FIXTURES_DIR.glob("*.json"):
        if path.name not in allowed:
            path.unlink()
    build_fixture_index(paths)
    errors = validate_fixtures.validate_fixture_index()
    if errors:
        msg = "build_all produced an invalid fixture_index:\n" + "\n".join(f"  - {e}" for e in errors)
        raise RuntimeError(msg)
    return paths


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate the committed fixtures/fixture_index without rebuilding (exit 1 on failure).",
    )
    parser.add_argument(
        "--import-check",
        action="store_true",
        help="With --check, also round-trip fixtures through Graph.from_payload.",
    )
    args = parser.parse_args(argv)

    if args.check:
        errors = validate_fixtures.validate_fixture_index()
        if args.import_check:
            errors.extend(validate_fixtures.validate_importable())
        if errors:
            print(f"FAILED ({len(errors)} issue(s)):", file=sys.stderr)
            for error in errors:
                print(f"  - {error}", file=sys.stderr)
            return 1
        print(f"OK: committed fixtures validate against {FLOWS_DIR / 'fixture_index.json'}")
        if args.import_check:
            print("OK: Graph.from_payload import check passed")
        return 0

    paths = build_all()
    index = FLOWS_DIR / "fixture_index.json"
    print(f"Wrote {len(paths)} fixtures under {FIXTURES_DIR}")
    print(f"Wrote fixture_index {index} ({sha256_file(index)[:12]}…)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
