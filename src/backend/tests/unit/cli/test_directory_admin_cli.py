"""Contracts for ``langflow admin directory`` and ``DirectoryState``."""

from __future__ import annotations

import json
from copy import deepcopy
from http import HTTPStatus
from stat import S_IMODE
from typing import TYPE_CHECKING, Any

import httpx
import pytest
from langflow.__main__ import app
from langflow.cli.admin.client import AdminAPIError, AdminClient
from langflow.cli.admin.directory_reconcile import DirectoryReconciler, DirectoryResolutionError
from langflow.cli.admin.manifest import DirectoryState, dump_directory_state, load_directory_state
from pydantic import ValidationError
from typer.testing import CliRunner

if TYPE_CHECKING:
    from pathlib import Path


def _state() -> DirectoryState:
    return DirectoryState.model_validate(
        {
            "apiVersion": "langflow.ai/v1",
            "kind": "DirectoryState",
            "connection": {
                "tenant_id": "tenant-a",
                "issuer": "https://issuer.example.com",
                "audience": "api://langflow-scim",
                "jwks_url": "https://issuer.example.com/jwks",
                "allowed_client_id": "client-a",
            },
            "teamLinks": [
                {
                    "group_id": "00000000-0000-0000-0000-000000000001",
                    "team_id": "00000000-0000-0000-0000-000000000002",
                    "origin": "linked",
                }
            ],
            "roleMappings": [
                {
                    "group_id": "00000000-0000-0000-0000-000000000001",
                    "role_id": "00000000-0000-0000-0000-000000000003",
                    "domain": {"type": "global"},
                }
            ],
        }
    )


def test_directory_command_tree_is_registered() -> None:
    runner = CliRunner()

    root = runner.invoke(app, ["admin", "directory", "--help"])
    groups = runner.invoke(app, ["admin", "directory", "groups", "--help"])
    reconcile = runner.invoke(app, ["admin", "directory", "reconcile", "--help"])

    assert root.exit_code == groups.exit_code == reconcile.exit_code == 0
    assert all(command in root.output for command in ("connection", "users", "groups", "role-mappings", "export"))
    assert all(command in groups.output for command in ("list", "get", "members", "link", "unlink"))
    assert all(command in reconcile.output for command in ("preview", "activate", "status", "retry"))


def test_directory_manifest_is_credential_free_and_excludes_catalog_state() -> None:
    with pytest.raises(ValidationError, match="client_secret"):
        DirectoryState.model_validate(
            {
                "apiVersion": "langflow.ai/v1",
                "kind": "DirectoryState",
                "connection": {
                    **_state().connection.model_dump(),
                    "client_secret": "do-not-store",  # pragma: allowlist secret
                },
            }
        )
    with pytest.raises(ValidationError, match="users"):
        DirectoryState.model_validate(
            {
                "apiVersion": "langflow.ai/v1",
                "kind": "DirectoryState",
                "users": [{"external_id": "entra-alice"}],
            }
        )


def test_directory_client_uses_v1_contract_and_page_totals() -> None:
    requests: list[httpx.Request] = []
    bodies: list[bytes] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/users"):
            offset = int(request.url.params["offset"])
            items = [{"id": str(index)} for index in range(offset, min(offset + 200, 205))]
            return httpx.Response(200, json={"items": items, "total": 205, "offset": offset, "limit": 200})
        if request.url.path.endswith("/groups/group-1/team-link"):
            bodies.append(request.read())
            return httpx.Response(200, json={"id": "link-1"})
        raise AssertionError(request.url)

    client = AdminClient(
        url="https://langflow.example",
        api_key="test-key",  # pragma: allowlist secret
        operation_id="directory-contract",
        transport=httpx.MockTransport(handler),
    )

    assert len(client.list_directory_users()) == 205
    client.link_directory_group("group-1", team_id="team-1", origin="linked")

    assert [request.url.path for request in requests[:2]] == [
        "/api/v1/authz/directory/users",
        "/api/v1/authz/directory/users",
    ]
    assert requests[-1].method == "PUT"
    assert requests[-1].url.path == "/api/v1/authz/directory/groups/group-1/team-link"
    assert json.loads(bodies[-1]) == {"team_id": "team-1", "origin": "linked"}


class _FakeDirectoryClient:
    def __init__(self) -> None:
        self.connection = {
            "tenant_id": "tenant-a",
            "issuer": "https://issuer.example.com",
            "audience": "api://langflow-scim",
            "jwks_url": "https://issuer.example.com/jwks",
            "allowed_client_id": "client-a",
            "state": "preview",
        }
        self.groups = [
            {
                "id": "00000000-0000-0000-0000-000000000001",
                "team_link": None,
            }
        ]
        self.mappings: list[dict[str, Any]] = []
        self.calls: list[str] = []

    def get_directory_connection(self) -> dict[str, Any]:
        return deepcopy(self.connection)

    def configure_directory_connection(self, **trust: str) -> dict[str, Any]:
        self.calls.append("connection:configure")
        self.connection.update(trust)
        return deepcopy(self.connection)

    def validate_directory_connection(self) -> dict[str, Any]:
        self.calls.append("connection:validate")
        return deepcopy(self.connection)

    def enable_directory_connection(self) -> dict[str, Any]:
        self.calls.append("connection:enable")
        self.connection["state"] = "preview"
        return deepcopy(self.connection)

    def list_directory_groups(self) -> list[dict[str, Any]]:
        return deepcopy(self.groups)

    def list_directory_role_mappings(self) -> list[dict[str, Any]]:
        return deepcopy(self.mappings)

    def link_directory_group(self, group_id: str, *, team_id: str, origin: str) -> dict[str, Any]:
        self.calls.append(f"link:{group_id}:{team_id}")
        link = {"id": "link-1", "group_id": group_id, "team_id": team_id, "origin": origin, "active": True}
        self.groups[0]["team_link"] = link
        return deepcopy(link)

    def unlink_directory_group(self, group_id: str) -> None:
        self.calls.append(f"unlink:{group_id}")
        self.groups[0]["team_link"] = None

    def create_directory_role_mapping(self, **payload: Any) -> dict[str, Any]:
        self.calls.append(f"mapping:create:{payload['group_id']}")
        mapping = {"id": "mapping-1", "active": True, **payload}
        self.mappings.append(mapping)
        return deepcopy(mapping)

    def delete_directory_role_mapping(self, mapping_id: str) -> None:
        self.calls.append(f"mapping:delete:{mapping_id}")
        self.mappings = [mapping for mapping in self.mappings if mapping["id"] != mapping_id]


def test_directory_diff_is_read_only_and_apply_stages_preview_intent() -> None:
    client = _FakeDirectoryClient()
    reconciler = DirectoryReconciler(client)

    drift = reconciler.diff(_state())
    assert client.calls == []
    assert [item["resource"] for item in drift] == ["team_link", "role_mapping"]

    report = reconciler.apply(_state())

    assert report["status"] == "success"
    assert client.calls == [
        "link:00000000-0000-0000-0000-000000000001:00000000-0000-0000-0000-000000000002",
        "mapping:create:00000000-0000-0000-0000-000000000001",
    ]
    assert reconciler.diff(_state()) == []


def test_directory_prune_unlinks_only_directory_mappings() -> None:
    client = _FakeDirectoryClient()
    desired = _state()
    DirectoryReconciler(client).apply(desired)
    empty = DirectoryState(apiVersion="langflow.ai/v1", kind="DirectoryState", connection=desired.connection)

    drift = DirectoryReconciler(client).diff(empty, prune=True)
    report = DirectoryReconciler(client).apply(empty, prune=True)

    assert {item["resource"] for item in drift} == {"team_link", "role_mapping"}
    assert report["status"] == "success"
    assert client.calls[-2:] == ["unlink:00000000-0000-0000-0000-000000000001", "mapping:delete:mapping-1"]


def test_directory_export_rejects_incomplete_trust_without_key_error() -> None:
    client = _FakeDirectoryClient()
    del client.connection["issuer"]

    with pytest.raises(AdminAPIError) as exc_info:
        DirectoryReconciler(client).export_state()

    assert exc_info.value.status_code == HTTPStatus.BAD_GATEWAY
    assert exc_info.value.error_code == "invalid_directory_connection"
    assert exc_info.value.detail == "Directory connection response is missing trust fields: issuer"


def test_initial_connection_only_apply_does_not_require_a_provisioned_catalog() -> None:
    class EmptyTarget:
        def __init__(self) -> None:
            self.calls: list[str] = []

        def get_directory_connection(self) -> dict[str, Any]:
            raise AdminAPIError(status_code=HTTPStatus.NOT_FOUND, detail="not configured")

        def list_directory_groups(self) -> list[dict[str, Any]]:
            raise AssertionError

        def list_directory_role_mappings(self) -> list[dict[str, Any]]:
            raise AssertionError

        def configure_directory_connection(self, **_trust: str) -> dict[str, Any]:
            self.calls.append("connection:configure")
            return {}

        def validate_directory_connection(self) -> dict[str, Any]:
            self.calls.append("connection:validate")
            return {}

        def enable_directory_connection(self) -> dict[str, Any]:
            self.calls.append("connection:enable")
            return {"state": "preview"}

    client = EmptyTarget()
    desired = _state().model_copy(update={"team_links": [], "role_mappings": []})
    reconciler = DirectoryReconciler(client)

    assert [item["action"] for item in reconciler.diff(desired)] == ["configure", "validate", "enable"]
    assert reconciler.apply(desired)["status"] == "success"
    assert client.calls == ["connection:configure", "connection:validate", "connection:enable"]


@pytest.mark.parametrize("command", ["diff", "apply"])
def test_directory_resolution_errors_use_stable_cli_output(monkeypatch, tmp_path, command: str) -> None:
    manifest = tmp_path / "directory-state.json"
    manifest.write_text(
        json.dumps(_state().model_dump(mode="json", by_alias=True, exclude_none=True)),
        encoding="utf-8",
    )

    error_message = "Directory group is not provisioned on this target"

    class UnresolvedDirectory:
        def diff(self, _state, *, prune: bool = False):  # noqa: ARG002
            raise DirectoryResolutionError(error_message)

        def apply(self, _state, *, prune: bool = False):  # noqa: ARG002
            raise DirectoryResolutionError(error_message)

    monkeypatch.setattr(
        "langflow.cli.admin.commands._directory_reconciler_from_context",
        lambda _ctx: UnresolvedDirectory(),
    )

    result = CliRunner().invoke(app, ["admin", "directory", command, str(manifest)])

    assert result.exit_code == 2
    assert error_message in result.output
    assert "Traceback" not in result.output


@pytest.mark.parametrize("command", [["users", "list"], ["groups", "list"], ["role-mappings", "list"], ["export"]])
@pytest.mark.parametrize("capability_status", [200, 404])
def test_directory_commands_explain_missing_enterprise_plugin(monkeypatch, capsys, command, capability_status):
    def handler(request):
        if request.url.path.endswith("/authz/capabilities") and capability_status == 200:
            return httpx.Response(200, json={"features": {"team_role_assignments": False}})
        return httpx.Response(404, json={"detail": "Not Found"})

    client = AdminClient(
        url="https://langflow.example",
        api_key="test-key",  # pragma: allowlist secret
        operation_id="missing-plugin",
        transport=httpx.MockTransport(handler),
    )
    monkeypatch.setattr("langflow.cli.admin.commands._client_from_context", lambda _ctx: client)
    result = CliRunner().invoke(app, ["admin", "directory", *command])
    assert result.exit_code == 1
    assert "requires the Enterprise directory plugin on the target server" in result.output + capsys.readouterr().err
    assert "Traceback" not in result.output
    client.close()


@pytest.mark.parametrize(
    ("status", "detail", "code"),
    [
        (404, "Directory connection not found", "directory_connection_not_found"),
        (404, "User not found", "directory_user_not_found"),
        (404, "directory synchronization is not enabled", "directory_sync_disabled"),
        (403, "Forbidden", None),
        (401, "Unauthorized", None),
        (503, "Directory trust validation is unavailable", "directory_trust_unavailable"),
    ],
)
def test_directory_client_preserves_typed_resource_and_access_errors(status, detail, code):
    def handler(request):
        assert request.url.path.endswith("/authz/directory/connection")
        return httpx.Response(status, json={"detail": detail}, headers={"X-Langflow-Error-Code": code} if code else {})

    with (
        AdminClient(
            url="https://langflow.example",
            api_key="test-key",  # pragma: allowlist secret
            operation_id="error-contract",
            transport=httpx.MockTransport(handler),
        ) as client,
        pytest.raises(AdminAPIError) as error,
    ):
        client.get_directory_connection()
    assert error.value.status_code == status
    assert error.value.detail == detail
    assert error.value.error_code == code


def test_directory_client_preserves_bare_resource_404_when_plugin_is_available():
    def handler(request):
        if request.url.path.endswith("/authz/capabilities"):
            return httpx.Response(200, json={"features": {"directory": {"enabled": True}}})
        return httpx.Response(404, json={"detail": "Not Found"})

    with (
        AdminClient(
            url="https://langflow.example",
            api_key="test-key",  # pragma: allowlist secret
            operation_id="resource-404",
            transport=httpx.MockTransport(handler),
        ) as client,
        pytest.raises(AdminAPIError) as error,
    ):
        client.get_directory_user("missing-user")
    assert error.value.status_code == 404
    assert error.value.detail == "Not Found"


def _generic_connection() -> dict[str, str]:
    return {
        "auth_mode": "bearer_token",
        "display_name": "Corporate directory",
        "sso_provider_key": "okta",
        "sso_issuer": "https://identity.example.com",
        "subject_claim": "sub",
    }


def _connection_state(connection: dict[str, Any]) -> DirectoryState:
    return DirectoryState.model_validate(
        {"apiVersion": "langflow.ai/v1", "kind": "DirectoryState", "connection": connection}
    )


@pytest.mark.parametrize(
    "extra",
    [
        {"tenant_id": "mixed"},
        {"issuer": "https://mixed.example"},
        {"token": "private-value"},
        {"bearer_token_hash": "private-value"},
        {"bearer_token_expires_at": "2099-01-01"},
        {"token_configured": True},
        {"state": "enabled"},
    ],
)
def test_generic_manifest_rejects_mixed_trust_and_server_state(extra: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        _connection_state({**_generic_connection(), **extra})


@pytest.mark.parametrize("mode", ["unknown", "", None])
def test_directory_manifest_rejects_unknown_auth_modes(mode: str | None) -> None:
    with pytest.raises(ValidationError):
        _connection_state({**_generic_connection(), "auth_mode": mode})


def test_generic_export_round_trip_and_apply_are_public_and_idempotent(tmp_path: Path) -> None:
    client = _FakeDirectoryClient()
    client.connection = {
        **_generic_connection(),
        "state": "disabled",
        "token_configured": True,
        "bearer_token_expires_at": "2099-01-01T00:00:00Z",
        "token": "never-export-this-token",
        "bearer_token_hash": "never-export-this-hash",
    }
    reconciler = DirectoryReconciler(client)
    exported = reconciler.export_state()
    text = dump_directory_state(exported, format_name="json")
    path = tmp_path / "directory.json"
    path.write_text(text)
    loaded = load_directory_state(path)

    assert json.loads(text)["connection"] == _generic_connection()
    assert "never-export" not in text
    assert reconciler.diff(loaded) == []
    assert reconciler.apply(loaded)["applied"] == []
    assert client.calls == []


@pytest.mark.parametrize("operation", ["export", "diff", "apply"])
def test_directory_unknown_api_mode_fails_before_mutations(operation: str) -> None:
    client = _FakeDirectoryClient()
    client.connection["auth_mode"] = "future-provider"
    reconciler = DirectoryReconciler(client)
    args = [] if operation == "export" else [_state()]
    method = reconciler.export_state if operation == "export" else getattr(reconciler, operation)
    with pytest.raises(AdminAPIError, match="unsupported authentication mode") as exc_info:
        method(*args)
    assert exc_info.value.error_code == "invalid_directory_connection"
    assert client.calls == []


def test_generic_apply_only_configures_public_intent() -> None:
    client = _FakeDirectoryClient()
    client.connection["state"] = "disabled"
    desired = _connection_state(_generic_connection())
    reconciler = DirectoryReconciler(client)

    assert [item["action"] for item in reconciler.diff(desired)] == ["configure"]
    assert reconciler.apply(desired)["status"] == "success"
    assert client.calls == ["connection:configure"]
    assert client.connection["state"] == "disabled"
    assert "token" not in client.connection
    assert reconciler.diff(desired) == []


def test_legacy_manifest_omits_default_mode_and_preserves_optional_display_name() -> None:
    original = json.loads(dump_directory_state(_state(), format_name="json"))["connection"]
    assert set(original) == {"tenant_id", "issuer", "audience", "jwks_url", "allowed_client_id"}
    desired = _connection_state({**original, "auth_mode": "entra_jwt", "display_name": "Existing Entra"})
    client = _FakeDirectoryClient()
    client.connection["display_name"] = "Existing Entra"
    assert DirectoryReconciler(client).diff(desired) == []
    connection = json.loads(dump_directory_state(desired, format_name="json"))["connection"]
    assert connection["display_name"] == "Existing Entra"


def _mock_cli_client(monkeypatch, handler) -> AdminClient:
    client = AdminClient(
        url="https://langflow.example",
        api_key="test-key",  # pragma: allowlist secret
        operation_id="generic-directory-contract",
        transport=httpx.MockTransport(handler),
    )
    monkeypatch.setattr("langflow.cli.admin.commands._client_from_context", lambda _ctx: client)
    return client


@pytest.mark.parametrize("generic", [False, True])
def test_directory_configure_sends_mode_specific_payload(monkeypatch, *, generic: bool) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"state": "disabled"})

    _mock_cli_client(monkeypatch, handler)
    if generic:
        flags = [
            "--auth-mode",
            "bearer_token",
            "--display-name",
            "Corporate directory",
            "--sso-provider-key",
            "okta",
            "--sso-issuer",
            "https://identity.example.com",
        ]
        expected = _generic_connection()
    else:
        expected = json.loads(dump_directory_state(_state(), format_name="json"))["connection"]
        flags = [argument for key, value in expected.items() for argument in (f"--{key.replace('_', '-')}", value)]

    result = CliRunner().invoke(app, ["admin", "directory", "connection", "configure", *flags])

    assert result.exit_code == 0, result.output
    assert len(requests) == 1
    assert requests[0].method == "PUT"
    assert requests[0].url.path == "/api/v1/authz/directory/connection"
    assert json.loads(requests[0].read()) == expected


@pytest.mark.parametrize(
    "flags",
    [
        [],
        ["--auth-mode", "unknown"],
        ["--auth-mode", "bearer_token"],
        ["--auth-mode", "bearer_token", "--tenant-id", "mixed"],
        ["--sso-provider-key", "okta", "--sso-issuer", "https://identity.example.com"],
    ],
)
def test_directory_configure_invalid_mode_fields_fail_before_http(monkeypatch, flags: list[str]) -> None:
    def no_client(_ctx):
        pytest.fail("Invalid configuration reached HTTP")

    monkeypatch.setattr("langflow.cli.admin.commands._client_from_context", no_client)
    result = CliRunner().invoke(app, ["admin", "directory", "connection", "configure", *flags])
    assert result.exit_code == 2
    assert "Traceback" not in result.output


@pytest.mark.parametrize("output", ["table", "json"])
def test_directory_token_goes_only_to_new_private_file(monkeypatch, capsys, tmp_path: Path, output: str) -> None:
    path = tmp_path / "token.json"
    requests: list[httpx.Request] = []
    response = {"token": "only-in-private-file", "expires_at": "2099-01-01T00:00:00Z"}

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert path.exists()
        assert S_IMODE(path.stat().st_mode) == 0o600
        return httpx.Response(200, json=response)

    _mock_cli_client(monkeypatch, handler)
    result = CliRunner().invoke(
        app, ["admin", "--output", output, "directory", "connection", "token", "--yes", "--output-file", str(path)]
    )

    assert result.exit_code == 0, result.output
    assert [(request.method, request.url.path) for request in requests] == [
        ("POST", "/api/v1/authz/directory/connection/token")
    ]
    assert json.loads(path.read_text()) == response
    assert S_IMODE(path.stat().st_mode) == 0o600
    captured = capsys.readouterr()
    output_text = result.output + captured.out + captured.err
    assert response["token"] not in output_text
    assert str(path) in output_text
    assert response["expires_at"] in output_text


@pytest.mark.parametrize("failure", ["no-confirmation", "no-file", "existing", "unwritable"])
def test_directory_token_preflight_rejects_before_http(monkeypatch, tmp_path: Path, failure: str) -> None:
    def no_client(_ctx):
        pytest.fail("Unsafe token command reached HTTP")

    monkeypatch.setattr("langflow.cli.admin.commands._client_from_context", no_client)
    path = tmp_path / "token.json"
    flags = ["--yes", "--output-file", str(path)]
    if failure == "no-confirmation":
        flags = ["--output-file", str(path)]
    elif failure == "no-file":
        flags = ["--yes"]
    elif failure == "existing":
        path.write_text("preserve-existing")
    else:
        flags[-1] = str(tmp_path / "missing-parent" / "token.json")

    result = CliRunner().invoke(app, ["admin", "directory", "connection", "token", *flags])
    assert result.exit_code == 2
    if failure == "existing":
        assert path.read_text() == "preserve-existing"
    else:
        assert not path.exists()


def test_directory_token_failure_never_prints_secret_response(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "token.json"
    _mock_cli_client(monkeypatch, lambda _request: httpx.Response(500, json={"detail": "private-error-token"}))
    result = CliRunner().invoke(app, ["admin", "directory", "connection", "token", "--yes", "--output-file", str(path)])
    assert result.exit_code == 1
    assert "private-error-token" not in result.output
    assert not path.exists()


def test_generic_manifest_supplies_default_subject_claim() -> None:
    connection = _generic_connection()
    del connection["subject_claim"]
    desired = _connection_state(connection)
    assert desired.connection.subject_claim == "sub"
    assert json.loads(dump_directory_state(desired, format_name="json"))["connection"] == _generic_connection()


@pytest.mark.parametrize(
    "response",
    [
        [],
        {"expires_at": "2099-01-01T00:00:00Z"},
        {"token": "private-token", "expires_at": "private-invalid-expiry"},
    ],
)
def test_directory_token_rejects_malformed_response_without_secret_output(
    monkeypatch, capsys, tmp_path: Path, response: Any
) -> None:
    path = tmp_path / "token.json"
    _mock_cli_client(monkeypatch, lambda _request: httpx.Response(200, json=response))
    result = CliRunner().invoke(app, ["admin", "directory", "connection", "token", "--yes", "--output-file", str(path)])
    captured = capsys.readouterr()
    assert result.exit_code == 1
    assert "private-" not in result.output + captured.out + captured.err
    assert not path.exists()


def test_directory_token_preflight_rejects_unwritable_file_before_http(monkeypatch, tmp_path: Path) -> None:
    def no_client(_ctx):
        pytest.fail("Unwritable token command reached HTTP")

    def permission_denied(*_args, **_kwargs):
        raise PermissionError

    monkeypatch.setattr("langflow.cli.admin.commands._client_from_context", no_client)
    monkeypatch.setattr("langflow.cli.admin.commands.os.open", permission_denied)
    result = CliRunner().invoke(
        app, ["admin", "directory", "connection", "token", "--yes", "--output-file", str(tmp_path / "token.json")]
    )
    assert result.exit_code == 2


def test_directory_token_requires_private_posix_file_support(monkeypatch, capsys, tmp_path: Path) -> None:
    path = tmp_path / "token.json"

    def no_client(_ctx):
        pytest.fail("Unsupported private-file creation reached HTTP")

    monkeypatch.setattr("langflow.cli.admin.commands._client_from_context", no_client)
    monkeypatch.delattr("langflow.cli.admin.commands.os.fchmod")
    result = CliRunner().invoke(app, ["admin", "directory", "connection", "token", "--yes", "--output-file", str(path)])
    captured = capsys.readouterr()
    assert result.exit_code == 2
    assert "requires POSIX" in result.output + captured.out + captured.err
    assert not path.exists()
