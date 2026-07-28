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


def test_project_names_remain_unique_after_mcp_name_truncation() -> None:
    from lfx.base.mcp.constants import MAX_MCP_SERVER_NAME_LENGTH
    from lfx.base.mcp.util import sanitize_mcp_name

    from tests.locust.langflow_runtime.provision.projects import project_name

    env_id = "perf-smoke-check"
    fixture_ids = [
        "perf_passthrough",
        "perf_webhook_passthrough-copy-0",
        "perf_webhook_passthrough-copy-1",
        "human_input_flow",
        "perf_chat_db_agent",
    ]
    names = [project_name(env_id, fixture_id) for fixture_id in fixture_ids]
    server_names = {f"lf-{sanitize_mcp_name(name)[: (MAX_MCP_SERVER_NAME_LENGTH - 4)]}" for name in names}

    assert len(server_names) == len(fixture_ids)
    assert all(env_id in name for name in names)


def test_resolve_flow_ids_default_and_omitted_select_every_fixture() -> None:
    from tests.locust.langflow_runtime.provision.flows import load_fixture_index, resolve_flow_ids

    index = load_fixture_index()
    expected = [str(flow["id"]) for flow in index["flows"]]

    assert resolve_flow_ids(None, index) == expected
    assert resolve_flow_ids(["default"], index) == expected


def test_resolve_flow_ids_smoke_selects_only_smoke_set() -> None:
    from tests.locust.langflow_runtime.provision import SMOKE_FLOW_IDS
    from tests.locust.langflow_runtime.provision.flows import load_fixture_index, resolve_flow_ids

    assert resolve_flow_ids(["smoke"], load_fixture_index()) == list(SMOKE_FLOW_IDS)


def test_resolve_flow_ids_full_includes_ensemble_fixtures() -> None:
    from tests.locust.langflow_runtime.provision.flows import load_fixture_index, resolve_flow_ids

    index = load_fixture_index()
    full = resolve_flow_ids(["full"], index)

    assert full
    assert set(full) == {str(flow["id"]) for flow in index["flows"]}
    assert {"perf_ensemble_journey", "perf_ensemble_journey_hitl"} <= set(full)
    assert resolve_flow_ids(["all"], index) == full


def test_resolve_flow_ids_rejects_removed_v1_alias() -> None:
    from tests.locust.langflow_runtime.provision.flows import load_fixture_index, resolve_flow_ids

    with pytest.raises(RuntimeError, match="unknown fixture ids"):
        resolve_flow_ids(["v1"], load_fixture_index())


def test_provision_cli_uses_auth_mode_name_with_legacy_alias() -> None:
    from tests.locust.langflow_runtime.provision.cli import build_parser

    parser = build_parser()
    assert parser.parse_args(["apply"]).mode == "superuser-pool"
    assert parser.parse_args(["apply", "--auth-mode", "existing-user"]).mode == "existing-user"
    assert parser.parse_args(["apply", "--mode", "existing-user"]).mode == "existing-user"


def test_cli_validate_authenticates_as_suite_resource_owner(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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
    state["api_key"] = "perf-unit-key"  # pragma: allowlist secret
    state["flows"] = {"fixture": {"flow_id": "flow-1", "mcp_action_name": None}}
    state_path = tmp_path / "perf-unit.json"
    identities: list[str] = []

    class FakeHttp:
        identity = ""

        def __enter__(self):
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def login(self, username: str, password: str) -> str:
            assert password == _SUITE_CREDENTIAL_PASSWORD
            self.identity = username
            identities.append(username)
            return _PERF_SUITE_TOKEN

        def get_flow(self, flow_id: str) -> dict[str, str] | None:
            assert self.identity == "perf-unit-user"
            return {"id": flow_id}

    fake_http = FakeHttp()
    monkeypatch.setattr(cli, "ProvisionHttp", lambda *_args, **_kwargs: fake_http)
    monkeypatch.setattr(cli, "load_state", lambda _env_id: state)
    monkeypatch.setattr(cli, "save_state", lambda _state: state_path)
    monkeypatch.setattr(cli, "state_path_for", lambda _env_id: state_path)

    result = cli.cmd_validate(
        SimpleNamespace(
            env_id="perf-unit",
            host=None,
            mode="superuser-pool",
            username=None,
            password=None,
        )
    )

    assert result == 0
    assert identities == ["perf-unit-user"]


def test_mcp_validation_normalizes_configured_action_name(monkeypatch: pytest.MonkeyPatch) -> None:
    from types import SimpleNamespace

    from tests.locust.langflow_runtime.provision import mcp

    class FakeMcpClient:
        def __init__(self, **_kwargs: object) -> None:
            pass

        def initialize(self) -> None:
            pass

        def notify_initialized(self) -> None:
            pass

        def list_tools(self) -> list[dict[str, str]]:
            return [{"name": "perf_chat_db_agent"}]

    monkeypatch.setattr(mcp, "McpStreamableClient", FakeMcpClient)
    http = SimpleNamespace(api_client=lambda **_kwargs: object())
    state = {
        "api_key": "perf-unit-key",  # pragma: allowlist secret
        "flows": {
            "perf_chat_db_agent": {
                "project_id": "project-1",
                "mcp_action_name": "perf_chat_db_agent",
            }
        },
        "mcp": {},
        "flags": {},
    }

    assert mcp.validate_mcp_tools_listable(http, state) is True
    assert state["mcp"]["discovered"] == ["perf_chat_db_agent"]
