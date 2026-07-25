"""Shared hashing helpers for the performance-suite locust package.

Used by ``flows/build_fixtures`` and ``flows/validate_fixtures`` to pin and
drift-check fixture JSON and embedded isolator sources, and by unit tests in
``tests/locust/tests/unit/test_flow_collection.py``.
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

# Node data.type values from Graph.dump for the suite isolators.
ISOLATOR_TYPE_TO_KEY = {
    "PerfCpuBurn": "perf_cpu_burn",
    "PerfSleep": "perf_sleep",
    "PerfSubprocessChurn": "perf_subprocess_churn",
}


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def embedded_isolator_hashes(payload: dict[str, Any]) -> dict[str, str]:
    """Map isolator key -> sha256 of embedded template code, keyed by node type."""
    found: dict[str, str] = {}
    for node in payload.get("data", {}).get("nodes", []):
        node_data = node.get("data") or {}
        node_type = node_data.get("type")
        key = ISOLATOR_TYPE_TO_KEY.get(node_type)
        if key is None:
            continue
        code = node_data.get("node", {}).get("template", {}).get("code", {}).get("value")
        if isinstance(code, str):
            found[key] = sha256_text(code)
    return found


def component_source_hashes(components_dir: Path) -> dict[str, str]:
    return {
        "perf_cpu_burn": sha256_file(components_dir / "perf_cpu_burn.py"),
        "perf_sleep": sha256_file(components_dir / "perf_sleep.py"),
        "perf_subprocess_churn": sha256_file(components_dir / "perf_subprocess_churn.py"),
    }
