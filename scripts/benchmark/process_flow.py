"""Measure nested group expansion, without timing assertions.

Run from the repository root with ``uv run --no-sync python scripts/benchmark/process_flow.py``.
"""

import copy
import json
from pathlib import Path
from statistics import median
from time import perf_counter
from unittest.mock import patch

from lfx.graph.graph.utils import process_flow


def main():
    fixture = Path(__file__).resolve().parents[2] / "src/lfx/tests/data/grouped_chat.json"
    original = json.loads(fixture.read_text(encoding="utf-8"))["data"]
    deepcopy = copy.deepcopy
    for depth in (0, 1, 3, 6):
        flow = copy.deepcopy(original)
        for level in range(depth):
            group_id = f"benchmark-group-{level}"
            flow = {
                "nodes": [
                    {
                        "id": group_id,
                        "data": {
                            "id": group_id,
                            "node": {"template": {}, "flow": {"data": flow}},
                        },
                    },
                ],
                "edges": [],
            }

        untouched = copy.deepcopy(flow)
        durations = []
        for _ in range(15):
            start = perf_counter()
            result = process_flow(flow)
            durations.append(perf_counter() - start)

        flow_copies = 0

        def count_flow_copies(value, *args, **kwargs):
            nonlocal flow_copies
            if isinstance(value, dict) and "nodes" in value and "edges" in value:
                flow_copies += 1
            return deepcopy(value, *args, **kwargs)

        with patch("copy.deepcopy", count_flow_copies):
            counted_result = process_flow(flow)
        if counted_result != result or flow != untouched:
            msg = "Group expansion changed its input or produced inconsistent results"
            raise AssertionError(msg)
        print(f"extra_depth={depth} flow_copies={flow_copies} median_ms={median(durations) * 1000:.3f}")


if __name__ == "__main__":
    main()
