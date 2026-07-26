"""Provision state file load/save and redaction helpers."""

from __future__ import annotations

import json
import os
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tests.locust.langflow_runtime.paths import state_dir as default_state_dir
from tests.locust.langflow_runtime.paths import state_path_for as default_state_path_for
from tests.locust.langflow_runtime.provision import STATE_SCHEMA_VERSION

SECRET_KEYS = frozenset({"api_key", "password", "token", "access_token", "secret"})

__all__ = [
    "STATE_DIR",
    "load_state",
    "new_state",
    "redact_state_for_log",
    "register_resource",
    "resource_tagged_for_env",
    "save_state",
    "state_path_for",
]


def __getattr__(name: str) -> Any:
    """Expose ``STATE_DIR`` as a live Path so ``PERF_DATA_DIR`` is honored."""
    if name == "STATE_DIR":
        return default_state_dir()
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)


def state_path_for(env_id: str, *, state_dir: Path | None = None) -> Path:
    if state_dir is not None:
        safe = env_id.replace("/", "_").replace("..", "_")
        return state_dir / f"{safe}.json"
    return default_state_path_for(env_id)


def new_state(
    *,
    env_id: str,
    host: str,
    mode: str,
    fixture_index_hash: str,
) -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "env_id": env_id,
        "host": host.rstrip("/"),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "fixture_index_hash": fixture_index_hash,
        "mode": mode,
        "api_key": None,
        "api_key_id": None,
        "project_id": None,
        "username": None,
        "flows": {},
        "webhooks": {"validated": False, "copies": []},
        "hitl": {"validated": False, "usable": False},
        "kb": {},
        "chat_seed": {"seeded": False, "turns": 0},
        "mcp": {"configured": False},
        "resources": [],
        "teardown_order": [],
        "credentials": {},
        "flags": {
            "webhook_validated": False,
            "hitl_validated": False,
            "mcp_tools_ok": False,
            "chat_seeded": False,
        },
    }


def register_resource(
    state: dict[str, Any],
    *,
    kind: str,
    resource_id: str,
    name: str | None = None,
    env_id: str | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    """Append an ownership-tagged resource and prepend it to teardown_order."""
    tagged_env = env_id or state.get("env_id")
    entry: dict[str, Any] = {
        "kind": kind,
        "id": str(resource_id),
        "name": name,
        "env_id": tagged_env,
    }
    if extra:
        entry.update(extra)
    state.setdefault("resources", []).append(entry)
    token = f"{kind}:{resource_id}"
    order: list[str] = state.setdefault("teardown_order", [])
    if token in order:
        order.remove(token)
    order.insert(0, token)


def load_state(env_id: str, *, state_dir: Path | None = None) -> dict[str, Any]:
    path = state_path_for(env_id, state_dir=state_dir)
    if not path.exists():
        msg = f"provision state not found: {path}"
        raise FileNotFoundError(msg)
    return json.loads(path.read_text(encoding="utf-8"))


def save_state(state: dict[str, Any], *, state_dir: Path | None = None) -> Path:
    env_id = str(state["env_id"])
    path = state_path_for(env_id, state_dir=state_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(state, indent=2, sort_keys=True) + "\n"
    # Atomic write with restrictive mode to avoid a world-readable window.
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    fd = os.open(str(tmp_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
        os.replace(tmp_path, path)
        os.chmod(path, 0o600)
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink()
        raise
    return path


def redact_state_for_log(state: dict[str, Any]) -> dict[str, Any]:
    """Return a deep copy with secret-looking values replaced by ***."""
    return _redact(deepcopy(state))


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, item in value.items():
            if key.lower() in SECRET_KEYS and item:
                out[key] = "***"
            else:
                out[key] = _redact(item)
        return out
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


def resource_tagged_for_env(resource: dict[str, Any], env_id: str) -> bool:
    return str(resource.get("env_id") or "") == str(env_id)
