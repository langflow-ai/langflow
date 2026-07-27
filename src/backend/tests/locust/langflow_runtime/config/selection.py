"""Resolve --axes / --suite selection into a runnable MovementProfile."""

from __future__ import annotations

import json
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any, Literal

from tests.locust.langflow_runtime.config.loader import PROFILES_DIR, load_profile, resolve_profile_path
from tests.locust.langflow_runtime.config.models import MovementProfile

# Canonical stress-axis order (also the --suite tutti expansion).
STRESS_AXES: tuple[str, ...] = (
    "protocol_calibration",
    "chat_db",
    "kb_ingest",
    "kb_retrieve",
    "cpu_graph",
    "multiproc",
    "disk_io",
    "ram_storage",
    "queue",
    "hitl",
    "outbound",
)

STRESS_AXES_SET = frozenset(STRESS_AXES)
SUITES_PATH = PROFILES_DIR / "suites.json"
ExternalApis = Literal["stubbed", "live"]


def load_suites_catalog() -> dict[str, Any]:
    raw = json.loads(SUITES_PATH.read_text(encoding="utf-8"))
    suites = raw.get("suites")
    if not isinstance(suites, dict):
        msg = f"suites.json must contain a 'suites' object: {SUITES_PATH}"
        raise TypeError(msg)
    return suites


def parse_axes(raw: str) -> list[str]:
    """Parse comma-separated axes; dedupe and normalize to canonical order."""
    tokens = [part.strip() for part in raw.split(",") if part.strip()]
    if not tokens:
        msg = "--axes requires at least one stress axis"
        raise ValueError(msg)
    unknown = sorted(set(tokens) - STRESS_AXES_SET)
    if unknown:
        msg = f"unknown stress axis/axes: {', '.join(unknown)}; known: {', '.join(STRESS_AXES)}"
        raise ValueError(msg)
    seen: set[str] = set()
    ordered: list[str] = []
    for axis in STRESS_AXES:
        if axis in tokens and axis not in seen:
            ordered.append(axis)
            seen.add(axis)
    return ordered


def _solo_profile_ref(axis: str) -> str:
    return f"solos/{axis}"


def _merge_user_mix(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge user_mix entries, preserving per-class count/weight from first occurrence."""
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in entries:
        name = entry["user_class"]
        if name in seen:
            continue
        seen.add(name)
        merged.append(deepcopy(entry))
    return merged


def _entry_population(entry: dict[str, Any]) -> int:
    """Users allocated to one user_mix entry (count wins; else at least 1)."""
    count = entry.get("count")
    if count is not None:
        return max(int(count), 0)
    return 1


def solo_population(solo: MovementProfile) -> int:
    """Concurrent users this solo contributes when composed with other axes."""
    mix_pop = sum(_entry_population(entry.model_dump()) for entry in solo.workload.user_mix)
    if mix_pop > 0:
        return mix_pop
    for step in solo.windows.measured_steps:
        if step.users is not None:
            return int(step.users)
    return 1


def compose_axes_profile(axes: list[str]) -> MovementProfile:
    """Compose concurrent solo user classes for the given axes into one profile.

    Each solo's ``user_mix[].count`` is preserved and applied as Locust
    ``fixed_count`` at registration time. Measured ``users`` is the sum of
    per-axis populations so every selected class is spawned concurrently.

    Queue stays paced on ``QueueUser`` itself; mixed compositions use a closed
    load shape so other axes are not converted to a global paced model.
    """
    if not axes:
        msg = "compose_axes_profile requires at least one axis"
        raise ValueError(msg)
    unknown = sorted(set(axes) - STRESS_AXES_SET)
    if unknown:
        msg = f"unknown stress axis/axes: {', '.join(unknown)}"
        raise ValueError(msg)

    # Canonicalize order
    axes = [axis for axis in STRESS_AXES if axis in set(axes)]
    solos = [load_profile(_solo_profile_ref(axis)) for axis in axes]

    if len(solos) == 1:
        # Single-axis: keep the solo profile as-authored (incl. paced_closed queue).
        return solos[0]

    user_mix: list[dict[str, Any]] = []
    flow_selectors: list[str] = []
    dataset_selectors: list[str] = []
    protocols: list[str] = []
    modes: list[str] = []
    stress_categories: list[str] = []
    queue_arrival_rate: float | None = None

    for solo in solos:
        stress_categories.extend(solo.stress_categories)
        for proto in solo.protocols:
            if proto not in protocols:
                protocols.append(proto)
        for mode in solo.modes:
            if mode not in modes:
                modes.append(mode)
        for flow_id in solo.flow_selectors:
            if flow_id not in flow_selectors:
                flow_selectors.append(flow_id)
        for dataset_id in solo.dataset_selectors:
            if dataset_id not in dataset_selectors:
                dataset_selectors.append(dataset_id)
        user_mix.extend(entry.model_dump() for entry in solo.workload.user_mix)
        if solo.workload.workload_model == "paced_closed" and solo.workload.arrival_rate_per_s is not None:
            queue_arrival_rate = (queue_arrival_rate or 0.0) + solo.workload.arrival_rate_per_s

    merged_mix = _merge_user_mix(user_mix)
    # Ensure every class has an explicit count so fixed_count registration is stable.
    for entry in merged_mix:
        if entry.get("count") is None:
            entry["count"] = _entry_population(entry)

    populations = [solo_population(solo) for solo in solos]
    users_total = sum(populations)
    if users_total < 1:
        msg = f"composed axes {axes!r} produced zero concurrent users"
        raise ValueError(msg)
    if any(_entry_population(entry) < 1 for entry in merged_mix):
        msg = f"composed axes {axes!r} include a user class with zero population"
        raise ValueError(msg)

    # Mixed axes always use closed load; QueueUser paces itself when present.
    workload_model = "closed"

    base = solos[0]
    warm_users = max(s.windows.warm_up.users for s in solos)
    warm_duration = max(s.windows.warm_up.duration_s for s in solos)
    drain_deadline = max(s.windows.drain.deadline_s for s in solos)
    sampling = max(s.windows.sampling_interval_s for s in solos)
    poll = max(s.windows.poll_interval_s for s in solos)

    max_steps = max(len(s.windows.measured_steps) for s in solos)
    measured_steps: list[dict[str, Any]] = []
    for idx in range(max_steps):
        duration = 0.0
        spawn = 0.0
        for solo in solos:
            steps = solo.windows.measured_steps
            step = steps[idx] if idx < len(steps) else steps[-1]
            duration = max(duration, step.duration_s)
            spawn = max(spawn, step.spawn_rate)
        measured_steps.append(
            {
                "duration_s": duration,
                "spawn_rate": max(spawn, float(users_total)),
                "users": users_total,
            }
        )

    safety = base.safety_limits.model_dump()
    for solo in solos[1:]:
        other = solo.safety_limits
        safety["provider_spend_usd"] = max(safety["provider_spend_usd"], other.provider_spend_usd)
        safety["backlog_max"] = max(safety["backlog_max"], other.backlog_max)
        safety["storage_growth_bytes"] = max(safety["storage_growth_bytes"], other.storage_growth_bytes)
        safety["error_storm_rate"] = min(safety["error_storm_rate"], other.error_storm_rate)
        safety["drain_timeout_s"] = max(safety["drain_timeout_s"], other.drain_timeout_s)
        safety["cleanup_timeout_s"] = max(safety["cleanup_timeout_s"], other.cleanup_timeout_s)

    reset = base.reset_rules.model_dump()
    for solo in solos[1:]:
        other = solo.reset_rules.model_dump()
        for key, value in other.items():
            reset[key] = bool(reset.get(key)) or bool(value)

    think = None
    for solo in solos:
        if solo.workload.think_time is not None:
            think = solo.workload.think_time.model_dump()
            break

    profile_id = "+".join(axes)
    purpose = f"Concurrent stress axes: {', '.join(axes)}."
    unique_categories = list(dict.fromkeys(stress_categories))

    raw: dict[str, Any] = {
        "schema_version": "1",
        "id": profile_id,
        "test_type": "capacity",
        "purpose": purpose,
        "movement_kind": "axis_set",
        "stress_categories": unique_categories,
        "protocols": protocols,
        "modes": modes,
        "flow_selectors": flow_selectors,
        "dataset_selectors": dataset_selectors,
        "workload": {
            "workload_model": workload_model,
            "user_mix": merged_mix,
            "think_time": think,
            "axis_arrival_rates": {"queue": queue_arrival_rate} if queue_arrival_rate is not None else {},
        },
        "windows": {
            "warm_up": {"duration_s": warm_duration, "users": warm_users},
            "measured_steps": measured_steps,
            "drain": {"deadline_s": drain_deadline},
            "sampling_interval_s": sampling,
            "poll_interval_s": poll,
        },
        "correctness_sampling": base.correctness_sampling.model_dump(),
        "safety_limits": safety,
        "validity": {
            "max_generator_cpu_pct": min(s.validity.max_generator_cpu_pct for s in solos),
            "allowed_scheduling_lateness_s": max(s.validity.allowed_scheduling_lateness_s for s in solos),
            "cold_warm": "either",
        },
        "reset_rules": reset,
    }
    if think is None:
        raw["workload"].pop("think_time", None)
    return MovementProfile.model_validate(raw)


def resolve_suite_axes(suite_name: str, catalog: dict[str, Any] | None = None) -> list[str]:
    suites = catalog if catalog is not None else load_suites_catalog()
    entry = suites.get(suite_name)
    if entry is None:
        msg = f"unknown suite {suite_name!r}; known: {', '.join(sorted(suites))}"
        raise ValueError(msg)
    if entry.get("kind") != "axes":
        msg = f"suite {suite_name!r} is not an axes-expanding suite"
        raise ValueError(msg)
    axes_spec = entry.get("axes")
    if axes_spec == "all":
        return list(STRESS_AXES)
    if not isinstance(axes_spec, list) or not axes_spec:
        msg = f"suite {suite_name!r} axes must be a non-empty list or 'all'"
        raise ValueError(msg)
    return parse_axes(",".join(str(a) for a in axes_spec))


def natural_profile_ref(external_apis: ExternalApis) -> str:
    return f"natural/natural_mix_external_{external_apis}"


def resolve_selection(
    *,
    axes: str | None = None,
    suite: str | None = None,
    external_apis: str | None = None,
) -> tuple[MovementProfile, Path, dict[str, Any]]:
    """Resolve CLI selection to a profile, on-disk path, and metadata."""
    if bool(axes) == bool(suite):
        msg = "exactly one of --axes or --suite is required"
        raise ValueError(msg)

    meta: dict[str, Any] = {"selection": {}}
    catalog = load_suites_catalog()

    if axes is not None:
        if external_apis is not None:
            msg = "--external-apis is only valid with --suite natural"
            raise ValueError(msg)
        parsed = parse_axes(axes)
        profile = compose_axes_profile(parsed)
        path = write_composed_profile(profile)
        meta["selection"] = {"kind": "axes", "axes": parsed}
        return profile, path, meta

    assert suite is not None
    entry = catalog.get(suite)
    if entry is None:
        msg = f"unknown suite {suite!r}; known: {', '.join(sorted(catalog))}"
        raise ValueError(msg)

    kind = entry.get("kind")
    if kind == "axes":
        if external_apis is not None:
            msg = "--external-apis is only valid with --suite natural"
            raise ValueError(msg)
        parsed = resolve_suite_axes(suite, catalog)
        profile = compose_axes_profile(parsed)
        path = write_composed_profile(profile)
        meta["selection"] = {"kind": "suite", "suite": suite, "axes": parsed}
        return profile, path, meta

    if kind == "profile":
        if external_apis is not None:
            msg = "--external-apis is only valid with --suite natural"
            raise ValueError(msg)
        profile_ref = str(entry["profile"])
        profile = load_profile(profile_ref)
        path = resolve_profile_path(profile_ref)
        meta["selection"] = {"kind": "suite", "suite": suite, "profile": profile_ref}
        return profile, path, meta

    if kind == "natural":
        if external_apis not in {"stubbed", "live"}:
            msg = "--suite natural requires --external-apis stubbed|live"
            raise ValueError(msg)
        profile_ref = natural_profile_ref(external_apis)  # type: ignore[arg-type]
        profile = load_profile(profile_ref)
        path = resolve_profile_path(profile_ref)
        meta["selection"] = {
            "kind": "suite",
            "suite": suite,
            "external_apis": external_apis,
            "profile": profile_ref,
        }
        return profile, path, meta

    msg = f"suite {suite!r} has unsupported kind {kind!r}"
    raise ValueError(msg)


def write_composed_profile(profile: MovementProfile, directory: Path | None = None) -> Path:
    """Persist a composed profile JSON for Locust (PERF_PROFILE_PATH)."""
    if directory is None:
        directory = Path(tempfile.mkdtemp(prefix="langflow-perf-profile-"))
    else:
        directory.mkdir(parents=True, exist_ok=True)
    safe_id = profile.id.replace("/", "_").replace("+", "__")
    path = directory / f"{safe_id}.json"
    path.write_text(profile.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return path.resolve()
