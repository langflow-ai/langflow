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

# Non-secret sentinels for provision teardown tests (avoid ``sk-`` / password literals).
_SUITE_CREDENTIAL_PASSWORD = "".join(("suite", "-", "pass", "word"))  # noqa: FLY002
_PERF_SUITE_TOKEN = "perf-suite-token-not-used"
_PERF_ADMIN_TOKEN = "perf-admin-token-not-used"


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


def test_cli_teardown_deletes_owned_resources_before_suite_user(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from types import SimpleNamespace

    from tests.locust.langflow_runtime.provision import cli

    state = new_state(
        env_id="perf-unit",
        host="http://example.test",
        mode="superuser_pool",
        fixture_index_hash="hash",
    )
    state["credentials"] = {
        "suite_username": "perf-unit-user",
        "password": _SUITE_CREDENTIAL_PASSWORD,
    }
    register_resource(state, kind="user", resource_id="user-1", env_id="perf-unit")
    register_resource(state, kind="api_key", resource_id="key-1", env_id="perf-unit")
    register_resource(state, kind="flow", resource_id="flow-1", env_id="perf-unit")
    state_path = tmp_path / "perf-unit.json"
    state_path.write_text("state", encoding="utf-8")
    calls: list[tuple[str, str, str]] = []

    class FakeHttp:
        identity = ""

        def __enter__(self):
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def login(self, username: str, password: str) -> str:
            assert password == _SUITE_CREDENTIAL_PASSWORD
            self.identity = username
            return _PERF_SUITE_TOKEN

        def delete_flow(self, resource_id: str) -> None:
            calls.append((self.identity, "flow", resource_id))

        def delete_api_key(self, resource_id: str) -> None:
            calls.append((self.identity, "api_key", resource_id))

        def delete_user(self, resource_id: str) -> None:
            calls.append((self.identity, "user", resource_id))

    fake_http = FakeHttp()

    def authenticate_admin(http: FakeHttp, **_kwargs: object) -> dict[str, str]:
        http.identity = "admin"
        return {"access_token": _PERF_ADMIN_TOKEN}

    monkeypatch.setattr(cli, "ProvisionHttp", lambda _host: fake_http)
    monkeypatch.setattr(cli, "authenticate", authenticate_admin)
    monkeypatch.setattr(cli, "load_state", lambda _env_id: state)
    monkeypatch.setattr(cli, "state_path_for", lambda _env_id: state_path)

    result = cli.cmd_teardown(
        SimpleNamespace(
            env_id="perf-unit",
            host=None,
            dry_run=False,
            username="admin",
            password=None,
        )
    )

    assert result == 0
    assert calls == [
        ("perf-unit-user", "flow", "flow-1"),
        ("perf-unit-user", "api_key", "key-1"),
        ("admin", "user", "user-1"),
    ]
    assert not state_path.exists()


def test_teardown_preserves_suite_user_when_owner_cleanup_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    from tests.locust.langflow_runtime.provision import cli

    state = new_state(
        env_id="perf-unit",
        host="http://example.test",
        mode="superuser_pool",
        fixture_index_hash="hash",
    )
    state["credentials"] = {
        "suite_username": "perf-unit-user",
        "password": _SUITE_CREDENTIAL_PASSWORD,
    }
    register_resource(state, kind="user", resource_id="user-1", env_id="perf-unit")
    register_resource(state, kind="api_key", resource_id="key-1", env_id="perf-unit")

    class FakeHttp:
        def login(self, _username: str, _password: str) -> str:
            return _PERF_SUITE_TOKEN

    phases: list[set[str]] = []

    def fail_owner_cleanup(_http: object, _state: dict, *, resource_kinds: set[str]) -> list[dict[str, str]]:
        phases.append(resource_kinds)
        if resource_kinds == {"user"}:
            pytest.fail("suite user must remain available when owner cleanup fails")
        return [{"token": "api_key:key-1", "status": "error", "error": "temporary failure"}]

    monkeypatch.setattr(cli, "teardown_state", fail_owner_cleanup)
    results = cli._teardown_provisioned_state(FakeHttp(), state, username="admin", password=None)

    assert phases == [{"api_key"}]
    assert results[0]["status"] == "error"


def test_redact_nested_list() -> None:
    payload = {"resources": [{"api_key": "x", "id": "1"}], "token": "t"}
    out = redact_state_for_log(payload)
    assert out["resources"][0]["api_key"] == "***"
    assert out["token"] == "***"
    assert json.dumps(out)
