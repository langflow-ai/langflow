"""Unit tests for provision state + teardown safety guards."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.locust.langflow_runtime.provision.state import (
    load_state,
    new_state,
    redact_state_for_log,
    register_resource,
    save_state,
)
from tests.locust.langflow_runtime.provision.teardown import TeardownError, assert_safe_to_delete


def test_save_load_roundtrip(tmp_path: Path) -> None:
    state = new_state(
        env_id="perf-unit",
        host="http://127.0.0.1:7860",
        mode="superuser_pool",
        fixture_index_hash="abc123",
    )
    state["api_key"] = "sk-test-secret"  # pragma: allowlist secret
    state["credentials"]["api_key"] = "sk-test-secret"  # pragma: allowlist secret
    register_resource(state, kind="flow", resource_id="flow-1", name="perf-unit-flow", env_id="perf-unit")
    path = save_state(state, state_dir=tmp_path)
    assert path.exists()
    assert oct(path.stat().st_mode)[-3:] == "600"

    loaded = load_state("perf-unit", state_dir=tmp_path)
    assert loaded["env_id"] == "perf-unit"
    assert loaded["api_key"] == "sk-test-secret"  # pragma: allowlist secret
    assert loaded["teardown_order"][0] == "flow:flow-1"
    assert loaded["resources"][0]["env_id"] == "perf-unit"


def test_redact_secrets() -> None:
    state = new_state(
        env_id="perf-unit",
        host="http://localhost:7860",
        mode="existing_user",
        fixture_index_hash="hash",
    )
    state["api_key"] = "super-secret-key"  # pragma: allowlist secret
    state["credentials"] = {
        "api_key": "super-secret-key",  # pragma: allowlist secret
        "password": "hunter2",  # pragma: allowlist secret
        "username": "alice",
    }
    redacted = redact_state_for_log(state)
    assert redacted["api_key"] == "***"
    assert redacted["credentials"]["api_key"] == "***"
    assert redacted["credentials"]["password"] == "***"
    assert redacted["credentials"]["username"] == "alice"
    # Original untouched
    assert state["api_key"] == "super-secret-key"  # pragma: allowlist secret


def test_teardown_refuses_untagged_resources() -> None:
    foreign = {"kind": "flow", "id": "abc", "env_id": "other-env", "name": "nope"}
    with pytest.raises(TeardownError, match="refusing to delete"):
        assert_safe_to_delete(foreign, "perf-local")

    tagged = {"kind": "flow", "id": "abc", "env_id": "perf-local", "name": "ok"}
    assert_safe_to_delete(tagged, "perf-local")  # does not raise


def test_teardown_state_refuses_missing_ownership_record() -> None:
    from types import SimpleNamespace

    from tests.locust.langflow_runtime.provision.teardown import teardown_state

    state = {
        "env_id": "perf-local",
        "resources": [],
        "teardown_order": ["flow:orphan-id"],
    }
    http = SimpleNamespace()  # must not be called
    results = teardown_state(http, state, retries=1, retry_delay_s=0)  # type: ignore[arg-type]
    assert results == [
        {
            "token": "flow:orphan-id",
            "status": "refused",
            "error": "no ownership record in state.resources",
        }
    ]


def test_redact_nested_list() -> None:
    payload = {"resources": [{"api_key": "x", "id": "1"}], "token": "t"}
    out = redact_state_for_log(payload)
    assert out["resources"][0]["api_key"] == "***"
    assert out["token"] == "***"
    assert json.dumps(out)
