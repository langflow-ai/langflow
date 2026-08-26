"""Contract tests for the ``langflow admin`` automation surface."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import httpx
import pytest
from langflow.__main__ import app
from langflow.cli.admin.client import AdminAPIError, AdminClient
from langflow.cli.admin.config import ConnectionConfigurationError, resolve_connection
from langflow.cli.admin.manifest import AdminState
from pydantic import ValidationError
from typer.testing import CliRunner

if TYPE_CHECKING:
    from pathlib import Path


def test_admin_and_groups_commands_are_registered() -> None:
    runner = CliRunner()

    admin = runner.invoke(app, ["admin", "--help"])
    groups = runner.invoke(app, ["admin", "groups", "--help"])

    assert admin.exit_code == 0
    assert "users" in admin.output
    assert "teams" in admin.output
    assert "role-assignments" in admin.output
    assert "export" in admin.output
    assert "diff" in admin.output
    assert "apply" in admin.output
    assert groups.exit_code == 0
    assert "Alias for teams" in groups.output


def test_connection_precedence_and_profile_secret_indirection(tmp_path: Path) -> None:
    profile_file = tmp_path / "profiles.json"
    profile_file.write_text(
        json.dumps(
            {
                "profiles": {
                    "prod": {
                        "url": "https://profile.example",
                        "api_key_env": "PROD_LANGFLOW_KEY",  # pragma: allowlist secret
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    environment = {
        "LANGFLOW_URL": "https://environment.example",
        "LANGFLOW_API_KEY": "environment-secret",  # pragma: allowlist secret
        "PROD_LANGFLOW_KEY": "profile-secret",
    }

    profile = resolve_connection(profile="prod", profile_file=profile_file, environ=environment)
    explicit = resolve_connection(
        url="https://explicit.example",
        api_key="explicit-secret",  # pragma: allowlist secret
        profile="prod",
        profile_file=profile_file,
        environ=environment,
    )

    assert profile.url == "https://profile.example"
    assert profile.api_key == "profile-secret"  # pragma: allowlist secret
    assert explicit.url == "https://explicit.example"
    assert explicit.api_key == "explicit-secret"  # pragma: allowlist secret
    assert "profile-secret" not in profile_file.read_text(encoding="utf-8")


def test_selected_profile_requires_credential_environment_variable(tmp_path: Path) -> None:
    profile_file = tmp_path / "profiles.json"
    profile_file.write_text(
        '{"profiles":{"prod":{"url":"https://example.test","api_key_env":"MISSING_KEY"}}}',  # pragma: allowlist secret
        encoding="utf-8",
    )

    with pytest.raises(ConnectionConfigurationError, match="MISSING_KEY"):
        resolve_connection(profile="prod", profile_file=profile_file, environ={})


def test_invalid_profile_does_not_echo_secret_like_values(tmp_path: Path) -> None:
    profile_file = tmp_path / "profiles.json"
    profile_file.write_text(
        json.dumps(
            {
                "profiles": {
                    "prod": {
                        "url": "https://example.test",
                        "api_key_env": "PROD_KEY",  # pragma: allowlist secret
                        "api_key": "never-echo",  # pragma: allowlist secret
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ConnectionConfigurationError) as exc_info:
        resolve_connection(profile="prod", profile_file=profile_file, environ={})

    assert "never-echo" not in str(exc_info.value)
    assert "profiles.prod.api_key" in str(exc_info.value)


def test_admin_client_sends_api_key_and_operation_id_and_paginates() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        skip = int(request.url.params.get("skip", "0"))
        users = [{"id": str(index), "username": f"user-{index}"} for index in range(skip, min(skip + 200, 205))]
        return httpx.Response(200, json={"total_count": 205, "users": users})

    client = AdminClient(
        url="https://langflow.example/",
        api_key="secret-key",  # pragma: allowlist secret
        operation_id="cli-test-operation",
        transport=httpx.MockTransport(handler),
    )

    users = client.list_users()

    assert len(users) == 205
    assert len(requests) == 2
    assert all(request.headers["X-API-Key"] == "secret-key" for request in requests)
    assert all(request.headers["X-Langflow-Operation-ID"] == "cli-test-operation" for request in requests)
    assert requests[0].url.path == "/api/v1/users/"
    assert requests[0].url.params["limit"] == "200"


def test_admin_client_uses_enterprise_team_assignment_contract() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/api/v1/authz/teams":
            return httpx.Response(200, json=[{"id": "team-1", "adom_name": "ops"}])
        if request.url.path == "/api/v1/authz/admin/team-role-assignments":
            return httpx.Response(
                200,
                json=[
                    {"id": "assignment-1", "team_id": "team-1", "role_id": "role-1"},
                    {"id": "assignment-2", "team_id": "team-2", "role_id": "role-1"},
                ],
            )
        raise AssertionError(request.url)

    client = AdminClient(
        url="https://langflow.example",
        api_key="test-key",  # pragma: allowlist secret
        operation_id="cli-contract",
        transport=httpx.MockTransport(handler),
    )

    assignments = client.list_role_assignments(team="ops")

    assert [item["id"] for item in assignments] == ["assignment-1"]
    assert requests[-1].url.path == "/api/v1/authz/admin/team-role-assignments"
    assert not requests[-1].url.params


def test_api_validation_errors_do_not_reflect_secret_inputs() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            422,
            json={
                "detail": [
                    {
                        "type": "string_too_short",
                        "loc": ["body", "password"],
                        "msg": "String should have at least 6 characters",
                        "input": "secret-value",
                    }
                ]
            },
        )

    client = AdminClient(
        url="https://langflow.example",
        api_key="test-key",  # pragma: allowlist secret
        operation_id="cli-contract",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(AdminAPIError) as exc_info:
        client.create_user(username="alice", password="secret-value")  # noqa: S106  # pragma: allowlist secret

    assert "secret-value" not in exc_info.value.detail
    assert exc_info.value.detail == "body.password: String should have at least 6 characters"


def test_manifest_rejects_plaintext_passwords_and_invalid_domains() -> None:
    with pytest.raises(ValidationError):
        AdminState.model_validate(
            {
                "apiVersion": "langflow.ai/v1",
                "kind": "AdminState",
                "users": [
                    {"username": "alice", "state": "active", "password": "do-not-store"}  # pragma: allowlist secret
                ],
            }
        )

    with pytest.raises(ValidationError, match="domain_id"):
        AdminState.model_validate(
            {
                "apiVersion": "langflow.ai/v1",
                "kind": "AdminState",
                "assignments": [
                    {
                        "subject": {"type": "user", "name": "alice"},
                        "role": "viewer",
                        "domain": {"type": "workspace"},
                    }
                ],
            }
        )


def test_invalid_manifest_does_not_echo_plaintext_password(tmp_path: Path) -> None:
    manifest = tmp_path / "unsafe.yaml"
    manifest.write_text(
        "apiVersion: langflow.ai/v1\nkind: AdminState\nusers:\n  - username: alice\n    password: never-echo\n",
        encoding="utf-8",
    )

    result = CliRunner().invoke(app, ["admin", "apply", str(manifest)])

    assert result.exit_code == 2
    assert "never-echo" not in result.output
    assert "users.0.password" in result.output


def test_manifest_accepts_portable_natural_keys_and_password_env() -> None:
    state = AdminState.model_validate(
        {
            "apiVersion": "langflow.ai/v1",
            "kind": "AdminState",
            "users": [
                {"username": "alice", "state": "active", "password_env": "ALICE_PASSWORD"}  # pragma: allowlist secret
            ],
            "teams": [
                {
                    "adom_name": "operators",
                    "display_name": "Operators",
                    "state": "active",
                    "members": ["alice"],
                }
            ],
            "roles": [
                {
                    "name": "user-operator",
                    "permissions": ["user:manage"],
                }
            ],
            "assignments": [
                {
                    "subject": {"type": "user", "name": "alice"},
                    "role": "user-operator",
                    "domain": {"type": "global"},
                }
            ],
        }
    )

    assert state.api_version == "langflow.ai/v1"
    assert state.teams[0].members == ["alice"]
    assert state.assignments[0].domain.type == "global"


def test_manifest_rejects_unknown_permission_before_any_api_call() -> None:
    with pytest.raises(ValidationError, match="unknown action"):
        AdminState.model_validate(
            {
                "apiVersion": "langflow.ai/v1",
                "kind": "AdminState",
                "roles": [{"name": "unsafe", "permissions": ["file:deploy"]}],
            }
        )


def test_password_is_read_from_stdin_and_never_rendered(monkeypatch) -> None:
    captured: dict = {}

    class FakeClient:
        def create_user(self, *, username: str, password: str) -> dict:
            captured.update(username=username, password=password)
            return {"id": "user-id", "username": username, "is_active": True}

        def close(self) -> None:
            return None

    monkeypatch.setattr("langflow.cli.admin.commands._client_from_context", lambda _ctx: FakeClient())
    result = CliRunner().invoke(
        app,
        [
            "admin",
            "--url",
            "https://langflow.example",
            "--api-key",
            "test-key",
            "--output",
            "json",
            "users",
            "create",
            "alice",
            "--password-stdin",
        ],
        input="supersensitive\n",
    )

    assert result.exit_code == 0
    assert captured == {"username": "alice", "password": "supersensitive"}  # pragma: allowlist secret
    assert "supersensitive" not in result.output
    assert json.loads(result.output)["username"] == "alice"


def test_json_output_is_written_as_complete_canonical_json(monkeypatch) -> None:
    payload = {"id": "user-id", "username": "x" * 1000}

    class FakeClient:
        def get_user(self, _user: str) -> dict:
            return payload

    monkeypatch.setattr("langflow.cli.admin.commands._client_from_context", lambda _ctx: FakeClient())

    result = CliRunner().invoke(app, ["admin", "--output", "json", "users", "get", "alice"])

    assert result.exit_code == 0
    assert result.output == f"{json.dumps(payload, default=str, sort_keys=True)}\n"


def test_team_assignment_capability_failures_use_api_error_handling(monkeypatch) -> None:
    class FakeClient:
        def capabilities(self) -> dict:
            raise AdminAPIError(
                status_code=503,
                detail="Capabilities are temporarily unavailable",
                error_code="capabilities_unavailable",
            )

    monkeypatch.setattr("langflow.cli.admin.commands._client_from_context", lambda _ctx: FakeClient())

    result = CliRunner().invoke(
        app,
        ["admin", "role-assignments", "grant", "--role", "viewer", "--team", "operators"],
    )

    assert result.exit_code == 1
    assert result.output == "Error [capabilities_unavailable]: Capabilities are temporarily unavailable\n"


def test_update_commands_can_explicitly_clear_nullable_and_collection_fields(monkeypatch) -> None:
    captured: list[tuple[str, str, dict]] = []

    class FakeClient:
        def update_team(self, identifier: str, **changes) -> dict:
            captured.append(("team", identifier, changes))
            return {"id": "team-id", "adom_name": identifier, "description": changes.get("description")}

        def update_role(self, identifier: str, **changes) -> dict:
            captured.append(("role", identifier, changes))
            return {"id": "role-id", "name": identifier, **changes}

    client = FakeClient()
    monkeypatch.setattr("langflow.cli.admin.commands._client_from_context", lambda _ctx: client)
    runner = CliRunner()

    team_result = runner.invoke(
        app,
        ["admin", "--output", "json", "teams", "update", "ops", "--clear-description"],
    )
    role_result = runner.invoke(
        app,
        [
            "admin",
            "--output",
            "json",
            "roles",
            "update",
            "operator",
            "--clear-description",
            "--clear-parent",
            "--clear-permissions",
        ],
    )

    assert team_result.exit_code == 0
    assert role_result.exit_code == 0
    assert captured == [
        ("team", "ops", {"description": None}),
        ("role", "operator", {"permissions": [], "description": None, "parent": None}),
    ]


def test_connection_configuration_failures_use_usage_exit_code_for_multistep_commands(tmp_path: Path) -> None:
    manifest = tmp_path / "admin-state.yaml"
    manifest.write_text("apiVersion: langflow.ai/v1\nkind: AdminState\n", encoding="utf-8")
    runner = CliRunner(env={"LANGFLOW_URL": "", "LANGFLOW_API_KEY": ""})

    commands = [
        ["admin", "users", "delete", "alice", "--hard", "--confirm", "alice"],
        ["admin", "role-assignments", "grant", "--role", "viewer", "--user", "alice"],
        ["admin", "apply", str(manifest)],
    ]

    for command in commands:
        result = runner.invoke(app, command)
        assert result.exit_code == 2, result.output
        assert "Langflow URL is required" in result.output


def test_diff_uses_exit_three_when_drift_exists(monkeypatch, tmp_path: Path) -> None:
    manifest = tmp_path / "admin-state.yaml"
    manifest.write_text(
        "apiVersion: langflow.ai/v1\nkind: AdminState\nusers:\n  - username: alice\n    state: disabled\n",
        encoding="utf-8",
    )

    class FakeReconciler:
        def diff(self, _state, *, prune: bool = False):
            assert prune is False
            return [{"action": "update", "resource": "user", "key": "alice", "changes": ["state"]}]

    monkeypatch.setattr("langflow.cli.admin.commands._reconciler_from_context", lambda _ctx: FakeReconciler())
    result = CliRunner().invoke(
        app,
        [
            "admin",
            "--url",
            "https://langflow.example",
            "--api-key",
            "test-key",
            "--output",
            "json",
            "diff",
            str(manifest),
        ],
    )

    assert result.exit_code == 3
    assert json.loads(result.output)[0]["resource"] == "user"


def test_apply_reports_partial_failure_without_losing_pending_operations(monkeypatch, tmp_path: Path) -> None:
    manifest = tmp_path / "admin-state.json"
    manifest.write_text(
        json.dumps(
            {
                "apiVersion": "langflow.ai/v1",
                "kind": "AdminState",
                "users": [
                    {
                        "username": "alice",
                        "state": "active",
                        "password_env": "ALICE_PASSWORD",  # pragma: allowlist secret
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    class FakeReconciler:
        def apply(self, _state, *, prune: bool = False):
            assert prune is False
            return {
                "status": "failed",
                "applied": [{"resource": "role", "key": "operator"}],
                "skipped": [],
                "failed": [{"resource": "user", "key": "alice", "error": "conflict"}],
                "pending": [{"resource": "team", "key": "operators"}],
            }

    monkeypatch.setattr("langflow.cli.admin.commands._reconciler_from_context", lambda _ctx: FakeReconciler())
    result = CliRunner().invoke(
        app,
        [
            "admin",
            "--url",
            "https://langflow.example",
            "--api-key",
            "test-key",
            "--output",
            "json",
            "apply",
            str(manifest),
        ],
    )

    assert result.exit_code == 1
    report = json.loads(result.output)
    assert report["failed"][0]["key"] == "alice"
    assert report["pending"][0]["key"] == "operators"


def test_pruning_preview_maps_api_errors_to_stable_cli_output(monkeypatch, tmp_path: Path) -> None:
    manifest = tmp_path / "admin-state.yaml"
    manifest.write_text("apiVersion: langflow.ai/v1\nkind: AdminState\n", encoding="utf-8")

    class FakeReconciler:
        def diff(self, _state, *, prune: bool = False):
            assert prune is True
            raise AdminAPIError(
                status_code=503,
                detail="Directory catalog is unavailable",
                error_code="directory_unavailable",
            )

        def apply(self, _state, **_kwargs):
            raise AssertionError

    monkeypatch.setattr("langflow.cli.admin.commands._reconciler_from_context", lambda _ctx: FakeReconciler())
    result = CliRunner().invoke(
        app,
        [
            "admin",
            "--url",
            "https://langflow.example",
            "--api-key",
            "test-key",
            "apply",
            str(manifest),
            "--prune",
            "--yes",
        ],
    )

    assert result.exit_code == 1
    assert "Error [directory_unavailable]: Directory catalog is unavailable" in result.output
    assert "Traceback" not in result.output
