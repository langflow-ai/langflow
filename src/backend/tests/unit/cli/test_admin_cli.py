"""Contract tests for the ``langflow admin`` automation surface."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import httpx
import pytest
from langflow.__main__ import app
from langflow.cli.admin.client import AdminClient
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
