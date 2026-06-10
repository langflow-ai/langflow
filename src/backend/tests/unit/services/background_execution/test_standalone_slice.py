"""LE-1439 guards: the kept background-execution slice is standalone.

Static guards, not behavioral tests. The single-node slice must not reference
the redis-scaled backend / worker modules (which do not ship on this branch) and
the held scaled + observability modules must stay absent, so enabling
``LANGFLOW_JOB_QUEUE_TYPE=redis`` can never pull a missing import into the facade.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import langflow.services.background_execution.factory as factory_mod
import langflow.services.background_execution.service as service_mod

_FORBIDDEN_SYMBOLS = (
    "redis_backend",
    "RedisBackgroundQueue",
    "_build_scaled_backend",
    "select_background_backend",
    "_build_redis_client",
    "background_execution.worker",
    "self._scaled",
    "self._is_redis",
)

_HELD_MODULES = ("redis_backend", "worker", "metrics", "metrics_collector", "worker_registry")


def test_service_and_factory_carry_no_scaled_backend_refs():
    for mod in (service_mod, factory_mod):
        source = Path(mod.__file__).read_text(encoding="utf-8")
        present = [tok for tok in _FORBIDDEN_SYMBOLS if tok in source]
        assert not present, f"{Path(mod.__file__).name} still references scaled-backend symbols: {present}"


def test_scaled_and_observability_modules_absent_on_this_branch():
    for name in _HELD_MODULES:
        full = f"langflow.services.background_execution.{name}"
        assert importlib.util.find_spec(full) is None, f"{full} must not ship on the single-node branch"
