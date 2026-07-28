"""Load and validate performance-suite movement profiles."""

from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from tests.locust.langflow_runtime.config.models import SCHEMA_VERSION, MovementProfile
from tests.locust.langflow_runtime.datasets.registry import DATASET_IDS

PROFILES_DIR = Path(__file__).resolve().parent.parent / "profiles"
FIXTURE_INDEX_PATH = Path(__file__).resolve().parent.parent / "flows" / "fixture_index.json"
SCHEMA_PATH = PROFILES_DIR / "schema.json"

_DURATION_RE = re.compile(r"^(?P<value>\d+(?:\.\d+)?)(?P<unit>s|m|h)?$", re.IGNORECASE)


_DURATION_FIELD_SUFFIXES = ("_s",)
_DURATION_FIELD_NAMES = frozenset({"duration", "deadline"})


def _is_duration_field(key: str) -> bool:
    return key in _DURATION_FIELD_NAMES or key.endswith(_DURATION_FIELD_SUFFIXES)


def _normalize_duration(value: Any, *, parent_key: str | None = None) -> Any:
    if isinstance(value, str) and parent_key is not None and _is_duration_field(parent_key):
        match = _DURATION_RE.fullmatch(value.strip())
        if not match:
            return value
        amount = float(match.group("value"))
        unit = (match.group("unit") or "s").lower()
        if unit == "m":
            return amount * 60.0
        if unit == "h":
            return amount * 3600.0
        return amount
    if isinstance(value, dict):
        return {key: _normalize_duration(item, parent_key=key) for key, item in value.items()}
    if isinstance(value, list):
        return [_normalize_duration(item, parent_key=parent_key) for item in value]
    return value


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in overlay.items():
        if key == "extends":
            continue
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged


def _load_fixture_index() -> dict[str, Any]:
    return json.loads(FIXTURE_INDEX_PATH.read_text(encoding="utf-8"))


def fixture_flow_ids() -> frozenset[str]:
    index = _load_fixture_index()
    return frozenset(flow["id"] for flow in index.get("flows", []))


def resolve_profile_path(path_or_id: str) -> Path:
    candidate = Path(path_or_id)
    if candidate.suffix == ".json" and candidate.exists():
        return candidate.resolve()
    if candidate.suffix != ".json":
        direct = PROFILES_DIR / f"{path_or_id}.json"
        if direct.exists():
            return direct.resolve()
        nested = list(PROFILES_DIR.rglob(f"{path_or_id}.json"))
        if len(nested) == 1:
            return nested[0].resolve()
        if len(nested) > 1:
            msg = f"profile id {path_or_id!r} is ambiguous: {[str(p) for p in nested]}"
            raise FileNotFoundError(msg)
    relative = PROFILES_DIR / path_or_id
    if relative.exists():
        return relative.resolve()
    if not path_or_id.endswith(".json"):
        relative_json = PROFILES_DIR / f"{path_or_id}.json"
        if relative_json.exists():
            return relative_json.resolve()
    msg = f"profile not found: {path_or_id}"
    raise FileNotFoundError(msg)


def _load_raw_profile(path: Path, *, _seen: set[Path] | None = None) -> dict[str, Any]:
    seen = _seen or set()
    resolved = path.resolve()
    if resolved in seen:
        msg = f"circular extends chain detected at {resolved}"
        raise ValueError(msg)
    seen.add(resolved)

    raw = json.loads(resolved.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        msg = f"profile root must be an object: {resolved}"
        raise TypeError(msg)

    extends = raw.get("extends")
    if extends is None:
        return _normalize_duration(raw)

    parent_path = resolve_profile_path(str(extends))
    parent = _load_raw_profile(parent_path, _seen=seen)
    merged = _deep_merge(parent, raw)
    merged.pop("extends", None)
    return _normalize_duration(merged)


def _validate_references(profile: MovementProfile) -> list[str]:
    errors: list[str] = []
    known_flows = fixture_flow_ids()

    for flow_id in profile.flow_selectors:
        if flow_id not in known_flows:
            errors.append(f"unknown flow_selector {flow_id!r} (not in fixture_index)")

    for dataset_id in profile.dataset_selectors:
        if dataset_id not in DATASET_IDS:
            errors.append(f"unknown dataset_selector {dataset_id!r} (not in DATASET_IDS)")

    if profile.schema_version != SCHEMA_VERSION:
        errors.append(f"unsupported schema_version {profile.schema_version!r}")

    return errors


def load_profile(path_or_id: str, *, validate_references: bool = True) -> MovementProfile:
    """Load, resolve inheritance, and validate a movement profile."""
    path = resolve_profile_path(path_or_id)
    raw = _load_raw_profile(path)
    try:
        profile = MovementProfile.model_validate(raw)
    except ValidationError as exc:
        msg = f"invalid profile {path}: {exc}"
        raise ValueError(msg) from exc

    if validate_references:
        errors = _validate_references(profile)
        if errors:
            msg = f"profile {profile.id} failed reference validation: {'; '.join(errors)}"
            raise ValueError(msg)

    return profile


def list_profiles() -> list[Path]:
    """Discover committed profile JSON files under profiles/.

    Skips schema.json, suites.json, and underscore-prefixed files.
    """
    profiles: list[Path] = []
    for path in sorted(PROFILES_DIR.rglob("*.json")):
        if path.name in {"schema.json", "suites.json"} or path.name.startswith("_"):
            continue
        profiles.append(path)
    return profiles


def emit_schema(path: Path | str | None = None) -> Path:
    """Write MovementProfile JSON schema to profiles/schema.json."""
    destination = Path(path) if path is not None else SCHEMA_PATH
    destination.parent.mkdir(parents=True, exist_ok=True)
    schema = MovementProfile.model_json_schema()
    destination.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return destination


def validate_profile(path_or_id: str) -> list[str]:
    """Validate one profile; return a list of error strings (empty if valid)."""
    try:
        load_profile(path_or_id, validate_references=True)
    except (OSError, TypeError, ValueError, ValidationError) as exc:
        return [str(exc)]
    return []


def validate_all_profiles() -> dict[str, list[str]]:
    """Validate every discovered profile."""
    results: dict[str, list[str]] = {}
    for path in list_profiles():
        rel = path.relative_to(PROFILES_DIR)
        results[str(rel)] = validate_profile(str(rel))
    return results
