"""Measure component type alias computation in extension migration, without timing assertions.

Run from the repository root with ``uv run --no-sync python scripts/benchmark/extension_migration.py``.
"""

import copy
from statistics import median
from time import perf_counter
from unittest.mock import patch

import lfx.utils.component_aliases as ca
from lfx.extension.migration.rewrite import migrate_flow_payload
from lfx.interface.components import component_cache


def main():
    # Build a simulated component registry with 30 categories and 200 components
    simulated_registry = {
        f"category_{cat}": {
            f"Component_{cat}_{comp}": {
                "display_name": f"Component {cat} {comp}",
                "name": f"Component_{cat}_{comp}",
            }
            for comp in range(7)
        }
        for cat in range(30)
    }

    # Total simulated components = 210
    total_components = sum(len(c) for c in simulated_registry.values())

    component_cache.all_types_dict = copy.deepcopy(simulated_registry)
    component_cache.all_types_ready = True
    component_cache.known_type_aliases = None

    payload = {
        "data": {
            "nodes": [
                {
                    "id": f"node-{i}",
                    "data": {
                        "id": f"node-{i}",
                        "type": f"Component_0_{i % 7}",
                        "node": {"template": {}},
                    },
                }
                for i in range(20)
            ],
            "edges": [],
        }
    }

    call_count = 0
    orig_fn = ca.get_component_type_aliases

    def count_alias_calls(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return orig_fn(*args, **kwargs)

    # 1. Cold run: caches aliases
    with patch.object(ca, "get_component_type_aliases", side_effect=count_alias_calls):
        cold_start = perf_counter()
        migrate_flow_payload(copy.deepcopy(payload))
        cold_duration = perf_counter() - cold_start
        cold_calls = call_count

    # 2. Warm runs: should make 0 alias computation calls
    warm_durations = []
    warm_calls_total = 0
    with patch.object(ca, "get_component_type_aliases", side_effect=count_alias_calls):
        for _ in range(15):
            call_count = 0
            start = perf_counter()
            migrate_flow_payload(copy.deepcopy(payload))
            warm_durations.append(perf_counter() - start)
            warm_calls_total += call_count

    if warm_calls_total != 0:
        msg = f"Expected 0 alias computation calls on warm migration, got {warm_calls_total}"
        raise AssertionError(msg)

    print(
        f"registry_components={total_components} "
        f"cold_alias_calls={cold_calls} "
        f"warm_alias_calls={warm_calls_total} "
        f"cold_ms={cold_duration * 1000:.3f} "
        f"warm_median_ms={median(warm_durations) * 1000:.3f}"
    )


if __name__ == "__main__":
    main()
