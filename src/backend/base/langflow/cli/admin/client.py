"""HTTP client used by the Langflow administration CLI."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

import httpx

if TYPE_CHECKING:
    from collections.abc import Iterable

    from typing_extensions import Self

_PAGE_SIZE = 200


class AdminAPIError(RuntimeError):
    """A stable, non-secret representation of an administration API failure."""

    def __init__(self, *, status_code: int, detail: str, error_code: str | None = None) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail
        self.error_code = error_code


class AdminClient:
    """Synchronous v1 administration client with complete pagination."""

    def __init__(
        self,
        *,
        url: str,
        api_key: str,
        operation_id: str,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        headers = {
            "Accept": "application/json",
            "X-API-Key": api_key,
            "X-Langflow-Operation-ID": operation_id,
        }
        self._client = httpx.Client(
            base_url=f"{url.rstrip('/')}/api/v1/",
            headers=headers,
            timeout=httpx.Timeout(30.0),
            transport=transport,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def request(self, method: str, path: str, **kwargs: Any) -> Any:
        response = self._client.request(method, path.lstrip("/"), **kwargs)
        if response.is_error:
            try:
                body = response.json()
                detail_value = body.get("detail", response.text) if isinstance(body, dict) else response.text
                detail = _safe_api_detail(detail_value)
            except ValueError:
                detail = response.text or response.reason_phrase
            raise AdminAPIError(
                status_code=response.status_code,
                detail=detail,
                error_code=response.headers.get("X-Langflow-Error-Code"),
            )
        if response.status_code == httpx.codes.NO_CONTENT or not response.content:
            return None
        return response.json()

    def _list_collection(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        result_key: str | None = None,
        offset_name: str = "offset",
    ) -> list[dict[str, Any]]:
        query = {key: value for key, value in (params or {}).items() if value is not None}
        output: list[dict[str, Any]] = []
        offset = 0
        while True:
            page_query = {**query, offset_name: offset, "limit": _PAGE_SIZE}
            result = self.request("GET", path, params=page_query)
            if result_key is not None:
                page = result[result_key]
                total = int(result.get("total_count", len(page)))
            else:
                page = result
                total = None
            output.extend(page)
            if not page or (total is not None and len(output) >= total) or len(page) < _PAGE_SIZE:
                return output
            offset += len(page)

    def capabilities(self) -> dict[str, Any]:
        return self.request("GET", "authz/capabilities")

    def list_users(
        self,
        *,
        search: str | None = None,
        username: str | None = None,
        role_name: str | None = None,
    ) -> list[dict[str, Any]]:
        return self._list_collection(
            "users/",
            params={"search": search, "username": username, "role_name": role_name},
            result_key="users",
            offset_name="skip",
        )

    def get_user(self, identifier: str) -> dict[str, Any]:
        if _is_uuid(identifier):
            return self.request("GET", f"users/{identifier}")
        matches = self.list_users(username=identifier)
        if not matches:
            raise AdminAPIError(status_code=404, detail=f"User {identifier!r} was not found")
        return matches[0]

    def create_user(self, *, username: str, password: str) -> dict[str, Any]:
        return self.request("POST", "users/", json={"username": username, "password": password})

    def update_user(self, identifier: str, **changes: Any) -> dict[str, Any]:
        user = self.get_user(identifier)
        return self.request("PATCH", f"users/{user['id']}", json=_without_none(changes))

    def delete_user(self, identifier: str) -> dict[str, Any] | None:
        user = self.get_user(identifier)
        return self.request("DELETE", f"users/{user['id']}")

    def list_teams(self, *, search: str | None = None, adom_name: str | None = None) -> list[dict[str, Any]]:
        return self._list_collection("authz/teams", params={"search": search, "adom_name": adom_name})

    def get_team(self, identifier: str) -> dict[str, Any]:
        if _is_uuid(identifier):
            return self.request("GET", f"authz/teams/{identifier}")
        matches = self.list_teams(adom_name=identifier)
        if not matches:
            raise AdminAPIError(status_code=404, detail=f"Team {identifier!r} was not found")
        return matches[0]

    def create_team(
        self,
        *,
        adom_name: str,
        display_name: str,
        description: str | None = None,
        active: bool = True,
    ) -> dict[str, Any]:
        return self.request(
            "POST",
            "authz/teams",
            json={
                "adom_name": adom_name,
                "team_name": display_name,
                "description": description,
                "is_active": active,
            },
        )

    def update_team(self, identifier: str, **changes: Any) -> dict[str, Any]:
        team = self.get_team(identifier)
        payload = dict(changes)
        if "display_name" in payload:
            payload["team_name"] = payload.pop("display_name")
        if "active" in payload:
            payload["is_active"] = payload.pop("active")
        return self.request("PATCH", f"authz/teams/{team['id']}", json=payload)

    def delete_team(self, identifier: str) -> None:
        team = self.get_team(identifier)
        self.request("DELETE", f"authz/teams/{team['id']}")

    def list_team_members(self, team_identifier: str) -> list[dict[str, Any]]:
        team = self.get_team(team_identifier)
        return self._list_collection(f"authz/teams/{team['id']}/members")

    def add_team_member(self, team_identifier: str, user_identifier: str) -> dict[str, Any]:
        team = self.get_team(team_identifier)
        user = self.get_user(user_identifier)
        return self.request(
            "POST",
            f"authz/teams/{team['id']}/members",
            json={"user_id": user["id"], "source": "manual"},
        )

    def remove_team_member(self, team_identifier: str, user_identifier: str) -> dict[str, Any] | None:
        team = self.get_team(team_identifier)
        user = self.get_user(user_identifier)
        return self.request("DELETE", f"authz/teams/{team['id']}/members/{user['id']}")

    def list_roles(self, *, search: str | None = None, name: str | None = None) -> list[dict[str, Any]]:
        return self._list_collection("authz/roles", params={"search": search, "exact_name": name})

    def get_role(self, identifier: str) -> dict[str, Any]:
        if _is_uuid(identifier):
            return self.request("GET", f"authz/roles/{identifier}")
        matches = self.list_roles(name=identifier)
        if not matches:
            raise AdminAPIError(status_code=404, detail=f"Role {identifier!r} was not found")
        return matches[0]

    def create_role(
        self,
        *,
        name: str,
        permissions: Iterable[str],
        description: str | None = None,
        parent: str | None = None,
    ) -> dict[str, Any]:
        parent_id = self.get_role(parent)["id"] if parent else None
        return self.request(
            "POST",
            "authz/roles",
            json={
                "name": name,
                "description": description,
                "permissions": list(permissions),
                "parent_role_id": parent_id,
            },
        )

    def update_role(self, identifier: str, **changes: Any) -> dict[str, Any]:
        role = self.get_role(identifier)
        payload = dict(changes)
        if "parent" in payload:
            parent = payload.pop("parent")
            payload["parent_role_id"] = self.get_role(parent)["id"] if parent else None
        return self.request("PATCH", f"authz/roles/{role['id']}", json=payload)

    def delete_role(self, identifier: str) -> None:
        role = self.get_role(identifier)
        self.request("DELETE", f"authz/roles/{role['id']}")

    def list_role_assignments(
        self,
        *,
        user: str | None = None,
        team: str | None = None,
        role: str | None = None,
    ) -> list[dict[str, Any]]:
        role_id = self.get_role(role)["id"] if role else None
        if team is not None:
            team_id = self.get_team(team)["id"]
            # Enterprise PR #280 exposes this compatibility collection as one
            # unpaginated list and ignores unknown query parameters. Sending
            # offset/limit through the generic paginator would repeat the same
            # page forever once it contains 200 or more assignments.
            rows = self.request("GET", "authz/admin/team-role-assignments")
            return [
                row
                for row in rows
                if str(row["team_id"]) == str(team_id) and (role_id is None or str(row["role_id"]) == str(role_id))
            ]
        user_id = self.get_user(user)["id"] if user is not None else None
        return self._list_collection(
            "authz/role-assignments",
            params={"user_id": user_id, "role_id": role_id},
        )

    def grant_role(
        self,
        *,
        role: str,
        user: str | None = None,
        team: str | None = None,
        domain_type: str = "global",
        domain_id: str | None = None,
    ) -> dict[str, Any]:
        role_id = self.get_role(role)["id"]
        payload = {"role_id": role_id, "domain_type": domain_type, "domain_id": domain_id}
        if team is not None:
            payload["team_id"] = self.get_team(team)["id"]
            return self.request("POST", "authz/admin/team-role-assignments", json=payload)
        if user is None:
            msg = "Exactly one of user or team is required"
            raise ValueError(msg)
        payload["user_id"] = self.get_user(user)["id"]
        return self.request("POST", "authz/role-assignments", json=payload)

    def revoke_role_assignment(self, assignment_id: str, *, team: bool = False) -> dict[str, Any] | None:
        collection = "team-role-assignments" if team else "role-assignments"
        prefix = "authz/admin" if team else "authz"
        return self.request("DELETE", f"{prefix}/{collection}/{assignment_id}")


def _without_none(values: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in values.items() if value is not None}


def _safe_api_detail(detail: Any) -> str:
    """Render API errors without reflecting request inputs such as passwords."""
    if isinstance(detail, str):
        return detail
    if isinstance(detail, list):
        rendered = []
        for error in detail:
            if not isinstance(error, dict):
                rendered.append("Request validation failed")
                continue
            location = ".".join(str(part) for part in error.get("loc", []))
            validation_message = str(error.get("msg", "Request validation failed"))
            rendered.append(f"{location}: {validation_message}" if location else validation_message)
        return "; ".join(rendered) or "Request validation failed"
    if isinstance(detail, dict):
        code = detail.get("code") or detail.get("error_code")
        api_message = detail.get("message") or detail.get("detail")
        if isinstance(api_message, str):
            return f"{code}: {api_message}" if code else api_message
    return "Administration request failed"


def _is_uuid(value: str) -> bool:
    try:
        UUID(value)
    except ValueError:
        return False
    return True
