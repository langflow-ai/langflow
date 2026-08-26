"""Contracts for ``langflow admin directory`` and ``DirectoryState``."""

from __future__ import annotations

from copy import deepcopy
from http import HTTPStatus
from typing import Any

import httpx
import pytest
from langflow.__main__ import app
from langflow.cli.admin.client import AdminAPIError, AdminClient
from langflow.cli.admin.directory_reconcile import DirectoryReconciler
from langflow.cli.admin.manifest import DirectoryState
from pydantic import ValidationError
from typer.testing import CliRunner


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
    with pytest.raises(ValidationError):
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
    with pytest.raises(ValidationError):
        DirectoryState.model_validate(
            {
                "apiVersion": "langflow.ai/v1",
                "kind": "DirectoryState",
                "users": [{"external_id": "entra-alice"}],
            }
        )


def test_directory_client_uses_v1_contract_and_page_totals() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/users"):
            offset = int(request.url.params["offset"])
            items = [{"id": str(index)} for index in range(offset, min(offset + 200, 205))]
            return httpx.Response(200, json={"items": items, "total": 205, "offset": offset, "limit": 200})
        if request.url.path.endswith("/groups/group-1/team-link"):
            request.read()
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
