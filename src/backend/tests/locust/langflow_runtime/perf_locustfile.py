"""Thin Locust entrypoint for the performance suite."""

from __future__ import annotations

import importlib
import json
import os
import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[3]
_backend_root = str(_BACKEND_ROOT)
if _backend_root in sys.path:
    sys.path.remove(_backend_root)
sys.path.insert(0, _backend_root)

import contextlib

from locust import events

from tests.locust.langflow_runtime.config.context import RunContext, build_run_context
from tests.locust.langflow_runtime.config.loader import load_profile
from tests.locust.langflow_runtime.shapes.profile import ProfileLoadShape
from tests.locust.langflow_runtime.users.registry import USER_REGISTRY

# Locust discovers LoadTestShape subclasses present in this module's globals.
__all__ = ["ProfileLoadShape"]


def _load_provision_state(path: str | None) -> dict | None:
    if not path:
        return None
    state_path = Path(path)
    if not state_path.exists():
        return None
    return json.loads(state_path.read_text(encoding="utf-8"))


def _resolve_run_context() -> RunContext:
    profile_path = os.environ.get("PERF_PROFILE_PATH")
    if not profile_path:
        msg = "PERF_PROFILE_PATH is required"
        raise RuntimeError(msg)
    profile = load_profile(profile_path)
    state = _load_provision_state(os.environ.get("PERF_STATE_PATH"))
    report_dir = os.environ.get("PERF_REPORT_DIR")
    overrides: dict = {"profile_path": profile_path, "state_path": os.environ.get("PERF_STATE_PATH")}
    raw_ctx = os.environ.get("PERF_RUN_CONTEXT_JSON")
    if raw_ctx:
        with contextlib.suppress(json.JSONDecodeError):
            overrides.update(json.loads(raw_ctx))
    return build_run_context(
        profile,
        host=os.environ.get("PERF_HOST") or os.environ.get("LANGFLOW_HOST"),
        run_id=os.environ.get("PERF_RUN_ID"),
        report_dir=report_dir,
        env_id=os.environ.get("PERF_ENV_ID"),
        provision_state=state,
        overrides=overrides,
    )


def _import_user_class(dotted_path: str):
    module_name, class_name = dotted_path.rsplit(".", 1)
    module = importlib.import_module(module_name)
    return getattr(module, class_name)


def _register_profile_users(context: RunContext) -> list[type]:
    selected: list[type] = []
    for entry in context.profile.workload.user_mix:
        dotted = USER_REGISTRY.get(entry.user_class)
        if dotted is None:
            msg = f"unknown user_class {entry.user_class!r}"
            raise RuntimeError(msg)
        user_cls = _import_user_class(dotted)
        user_cls.weight = entry.weight
        # Locust: fixed_count > 0 pins an exact population for this class.
        # count=None leaves the class weight-distributed (fixed_count=0).
        user_cls.fixed_count = int(entry.count) if entry.count is not None else 0
        selected.append(user_cls)
    return selected


try:
    run_context = _resolve_run_context()
except RuntimeError as exc:
    # Fail closed when invoked outside run.py without PERF_PROFILE_PATH.
    if os.environ.get("PERF_ALLOW_EMPTY_LOCUSTFILE") == "1":
        run_context = None
    else:
        raise RuntimeError(
            "perf_locustfile requires PERF_PROFILE_PATH (launch via tests.locust.langflow_runtime.run)"
        ) from exc

if run_context is not None:
    for user_cls in _register_profile_users(run_context):
        globals()[user_cls.__name__] = user_cls


@events.init.add_listener
def _on_init(environment, **_kwargs) -> None:
    if run_context is None:
        return
    environment.run_context = run_context
    environment.host = run_context.host


@events.test_start.add_listener
def _on_test_start(environment, **_kwargs) -> None:
    try:
        from tests.locust.langflow_runtime.metrics.reports import register_reporting_listeners
    except ImportError:
        return
    register_reporting_listeners(environment)


@events.test_stop.add_listener
def _on_test_stop(environment, **_kwargs) -> None:
    try:
        from tests.locust.langflow_runtime.metrics.reports import finalize_reports
        from tests.locust.langflow_runtime.shapes.drain import reset_movement_state
    except ImportError:
        return
    finalize_reports(environment)
    reset_movement_state(environment)
