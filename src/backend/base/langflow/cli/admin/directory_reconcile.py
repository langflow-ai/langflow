"""Deterministic diff, export, and preview-state apply for directory intent."""

from __future__ import annotations

from dataclasses import dataclass
from http import HTTPStatus
from typing import TYPE_CHECKING, Any

from langflow.cli.admin.client import AdminAPIError
from langflow.cli.admin.manifest import (
    DirectoryConnectionTrust,
    DirectoryRoleMapping,
    DirectoryState,
    DirectoryTeamLink,
    ManifestDomain,
)

if TYPE_CHECKING:
    from langflow.cli.admin.client import AdminClient

_TRUST_FIELDS = ("tenant_id", "issuer", "audience", "jwks_url", "allowed_client_id")


@dataclass(frozen=True, slots=True)
class _Operation:
    action: str
    resource: str
    key: str
    payload: dict[str, Any]

    def public(self) -> dict[str, str]:
        return {"action": self.action, "resource": self.resource, "key": self.key}


class DirectoryReconciler:
    """Converge reviewed directory mappings without activating authorization."""

    def __init__(self, client: AdminClient) -> None:
        self.client = client

    def export_state(self) -> DirectoryState:
        connection = self.client.get_directory_connection()
        groups = self.client.list_directory_groups()
        mappings = self.client.list_directory_role_mappings()
        return DirectoryState(
            apiVersion="langflow.ai/v1",
            kind="DirectoryState",
            connection=DirectoryConnectionTrust(**{field: connection[field] for field in _TRUST_FIELDS}),
            teamLinks=sorted(
                [
                    DirectoryTeamLink(
                        group_id=group["id"],
                        team_id=group["team_link"]["team_id"],
                        origin=group["team_link"]["origin"],
                    )
                    for group in groups
                    if (group.get("team_link") or {}).get("active")
                ],
                key=lambda item: str(item.group_id),
            ),
            roleMappings=sorted(
                [
                    DirectoryRoleMapping(
                        group_id=mapping["group_id"],
                        role_id=mapping["role_id"],
                        domain=ManifestDomain(
                            type=mapping["domain_type"],
                            domain_id=mapping.get("domain_id"),
                        ),
                    )
                    for mapping in mappings
                    if mapping.get("active", True)
                ],
                key=lambda item: (str(item.group_id), str(item.role_id), item.domain.type),
            ),
        )

    def diff(self, state: DirectoryState, *, prune: bool = False) -> list[dict[str, str]]:
        return [operation.public() for operation in self._build_plan(state, prune=prune)]

    def apply(self, state: DirectoryState, *, prune: bool = False) -> dict[str, Any]:
        operations = self._build_plan(state, prune=prune)
        report: dict[str, Any] = {"status": "success", "applied": [], "failed": [], "pending": []}
        for index, operation in enumerate(operations):
            try:
                self._execute(operation)
            except Exception as exc:  # noqa: BLE001 - stable stop-at-first-failure report
                failed = operation.public()
                failed["error"] = str(exc)
                report["status"] = "failed"
                report["failed"] = [failed]
                report["pending"] = [item.public() for item in operations[index + 1 :]]
                return report
            report["applied"].append(operation.public())
        return report

    def _current_connection(self) -> dict[str, Any] | None:
        try:
            return self.client.get_directory_connection()
        except AdminAPIError as exc:
            if exc.status_code == HTTPStatus.NOT_FOUND:
                return None
            raise

    def _build_plan(self, state: DirectoryState, *, prune: bool) -> list[_Operation]:
        current_connection = self._current_connection()
        has_desired_mappings = bool(state.team_links or state.role_mappings)
        if current_connection is None:
            if has_desired_mappings:
                msg = "Configure the directory connection and provision its SCIM catalog before applying mappings"
                raise ValueError(msg)
            groups: list[dict[str, Any]] = []
            mappings: list[dict[str, Any]] = []
        else:
            groups = self.client.list_directory_groups()
            mappings = self.client.list_directory_role_mappings()
        group_ids = {str(group["id"]) for group in groups}
        operations: list[_Operation] = []

        if state.connection is not None:
            trust = state.connection.model_dump(mode="json")
            current_trust = (
                {field: current_connection.get(field) for field in _TRUST_FIELDS}
                if current_connection is not None
                else None
            )
            if current_trust != trust:
                operations.extend(
                    [
                        _Operation("configure", "connection", "primary", trust),
                        _Operation("validate", "connection", "primary", {}),
                        _Operation("enable", "connection", "primary", {}),
                    ]
                )

        current_links = {
            str(group["id"]): group["team_link"] for group in groups if (group.get("team_link") or {}).get("active")
        }
        desired_links = {str(link.group_id): link for link in state.team_links}
        unknown_groups = sorted(set(desired_links) - group_ids)
        if unknown_groups:
            msg = f"Directory group {unknown_groups[0]} is not provisioned on this target"
            raise ValueError(msg)
        for group_id, desired in sorted(desired_links.items()):
            current = current_links.get(group_id)
            if current is None or (str(current["team_id"]), current["origin"]) != (
                str(desired.team_id),
                desired.origin,
            ):
                operations.append(
                    _Operation(
                        "upsert",
                        "team_link",
                        group_id,
                        {
                            "group_id": group_id,
                            "team_id": str(desired.team_id),
                            "origin": desired.origin,
                        },
                    )
                )
        if prune:
            operations.extend(
                _Operation("delete", "team_link", group_id, {"group_id": group_id})
                for group_id in sorted(set(current_links) - set(desired_links))
            )

        def mapping_key(mapping: dict[str, Any]) -> tuple[str, str, str, str]:
            return (
                str(mapping["group_id"]),
                str(mapping["role_id"]),
                mapping["domain_type"],
                str(mapping.get("domain_id") or ""),
            )

        current_mappings = {mapping_key(mapping): mapping for mapping in mappings if mapping.get("active", True)}
        desired_mappings = {
            (
                str(mapping.group_id),
                str(mapping.role_id),
                mapping.domain.type,
                str(mapping.domain.domain_id or ""),
            ): mapping
            for mapping in state.role_mappings
        }
        unknown_mapping_groups = sorted({key[0] for key in desired_mappings} - group_ids)
        if unknown_mapping_groups:
            msg = f"Directory group {unknown_mapping_groups[0]} is not provisioned on this target"
            raise ValueError(msg)
        for key, mapping in sorted(desired_mappings.items()):
            if key not in current_mappings:
                operations.append(
                    _Operation(
                        "create",
                        "role_mapping",
                        "/".join(key),
                        {
                            "group_id": str(mapping.group_id),
                            "role_id": str(mapping.role_id),
                            "domain_type": mapping.domain.type,
                            "domain_id": str(mapping.domain.domain_id) if mapping.domain.domain_id else None,
                        },
                    )
                )
        if prune:
            operations.extend(
                _Operation(
                    "delete",
                    "role_mapping",
                    "/".join(key),
                    {"mapping_id": str(current_mappings[key]["id"])},
                )
                for key in sorted(set(current_mappings) - set(desired_mappings))
            )
        return operations

    def _execute(self, operation: _Operation) -> None:
        payload = operation.payload
        if operation.resource == "connection":
            if operation.action == "configure":
                self.client.configure_directory_connection(**payload)
            elif operation.action == "validate":
                self.client.validate_directory_connection()
            else:
                self.client.enable_directory_connection()
        elif operation.resource == "team_link":
            if operation.action == "delete":
                self.client.unlink_directory_group(payload["group_id"])
            else:
                self.client.link_directory_group(
                    payload["group_id"],
                    team_id=payload["team_id"],
                    origin=payload["origin"],
                )
        elif operation.action == "delete":
            self.client.delete_directory_role_mapping(payload["mapping_id"])
        else:
            self.client.create_directory_role_mapping(**payload)


__all__ = ["DirectoryReconciler"]
