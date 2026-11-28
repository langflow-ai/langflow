"""Measure real warm state getters, including discarded factory dependency inference.

Run from the repository root with uv run python scripts/benchmark/service_factory_lookup.py.
Registry variants extend the real available-service type map with aliases; they
measure inference-key scaling, not extra initialized services or endpoint gains.
"""

# Standalone benchmark reports observations and deliberately binds an isolated manager.
# ruff: noqa: S101
import argparse
import json
import tracemalloc
from statistics import median
from time import perf_counter_ns
from unittest.mock import patch

from langflow.services import deps
from langflow.services import factory as factory_module
from langflow.services.state.service import InMemoryStateService
from lfx.services import manager as manager_module
from lfx.services.manager import ServiceManager
from lfx.services.schema import ServiceType


def measure(iterations: int, repeats: int) -> list[dict]:
    """Interleave eager/lazy calls with one manager and real backend factory constructors."""
    available = factory_module.import_all_services_into_a_dict()
    resolve = deps.get_service
    construct = factory_module.ServiceFactory.__init__
    infer = factory_module.infer_service_types
    counts = {"constructors": 0, "inference": 0}

    def counted_construct(self, *args, **kwargs):
        """Keep actual factory work inside the measured call."""
        counts["constructors"] += 1
        construct(self, *args, **kwargs)

    def counted_infer(*args, **kwargs):
        """Include the original cached inference's key generation."""
        counts["inference"] += 1
        return infer(*args, **kwargs)

    def eager(service_type, default=None, *, default_factory=None):
        """Reproduce construction at the old helper-to-manager boundary."""
        if default_factory is not None:
            default = default_factory()
        return resolve(service_type, default)

    results = []
    for factor in (1, 2, 4):
        registry = dict(available)
        for index in range(len(available) * (factor - 1)):
            registry[f"BenchmarkAlias{index}"] = InMemoryStateService
        manager = ServiceManager()
        manager.set_factory_registered()
        expected = object()
        manager.services[ServiceType.STATE_SERVICE] = expected
        samples = {"eager": [], "lazy": []}
        allocations = {}
        with (
            patch.object(manager_module, "get_service_manager", lambda manager=manager: manager),
            patch.object(factory_module, "import_all_services_into_a_dict", lambda registry=registry: registry),
            patch.object(factory_module.ServiceFactory, "__init__", counted_construct),
            patch.object(factory_module, "infer_service_types", counted_infer),
        ):
            for repetition in range(repeats + 1):
                for mode in ("eager", "lazy") if repetition % 2 else ("lazy", "eager"):
                    with patch.object(deps, "get_service", eager if mode == "eager" else resolve):
                        counts.update(constructors=0, inference=0)
                        started = perf_counter_ns()
                        for _ in range(iterations):
                            assert deps.get_state_service() is expected
                        elapsed = (perf_counter_ns() - started) / iterations
                        if repetition:
                            samples[mode].append({"ns_per_lookup": elapsed, **counts})
            for mode in samples:
                with patch.object(deps, "get_service", eager if mode == "eager" else resolve):
                    tracemalloc.start()
                    for _ in range(iterations):
                        deps.get_state_service()
                    retained, peak = tracemalloc.get_traced_memory()
                    tracemalloc.stop()
                    allocations[mode] = {"retained_bytes": retained, "peak_bytes": peak}
        results.append(
            {
                "type_map_size": len(registry),
                "iterations": iterations,
                "samples": samples,
                "median_ns": {mode: median(row["ns_per_lookup"] for row in rows) for mode, rows in samples.items()},
                "memory": allocations,
            }
        )
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=int, default=1000)
    parser.add_argument("--repeats", type=int, default=7)
    options = parser.parse_args()
    print(json.dumps(measure(options.iterations, options.repeats), indent=2))
