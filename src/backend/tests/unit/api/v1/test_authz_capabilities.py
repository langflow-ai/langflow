"""Caller-specific authorization capability discovery contracts."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from langflow.api.v1 import authz_capabilities


class _CapabilityService:
    async def can_administer(self, *, user_id: UUID, resource: str) -> bool:
        del user_id
        return resource == "team"

    async def supports_team_role_assignments(self) -> bool:
        return True

    async def get_feature_capabilities(self, *, user_id: UUID, is_superuser: bool) -> dict:
        del user_id
        return {
            "directory": {
                "enabled": True,
                "provider": "entra",
                "actions": {
                    "configure_connection": is_superuser,
                    "read_groups": True,
                },
            }
        }


@pytest.mark.asyncio
async def test_capabilities_include_plugin_owned_directory_actions(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(authz_capabilities, "get_authorization_service", _CapabilityService)
    user = SimpleNamespace(id=uuid4(), is_superuser=False)

    result = await authz_capabilities.get_authorization_capabilities(user)

    assert result.model_dump() == {
        "administration": {"user": False, "team": True, "role": False},
        "features": {
            "team_role_assignments": True,
            "directory": {
                "enabled": True,
                "provider": "entra",
                "actions": {"configure_connection": False, "read_groups": True},
            },
        },
    }
