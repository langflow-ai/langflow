"""Caller-specific authorization capability discovery contracts."""

from __future__ import annotations

from typing import TYPE_CHECKING

from langflow.api.v1 import authz_capabilities

from tests.unit.services.authorization import test_collaboration_management as collaboration_tests
from tests.unit.services.authorization.test_collaboration_management import (
    _seed_users,
    _user,
)

collaboration_db = collaboration_tests.collaboration_db

if TYPE_CHECKING:
    from uuid import UUID

    import pytest


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


async def test_capabilities_include_plugin_owned_directory_actions(
    monkeypatch: pytest.MonkeyPatch, collaboration_db
) -> None:
    service = collaboration_db.service
    plugin = _CapabilityService()
    for method in ("can_administer", "supports_team_role_assignments", "get_feature_capabilities"):
        monkeypatch.setattr(service, method, getattr(plugin, method))
    user, superuser = _user("delegated"), _user("platform", is_superuser=True)
    await _seed_users(collaboration_db, user, superuser)
    async with collaboration_db.session() as session:
        result = await authz_capabilities.get_authorization_capabilities(user, session)
        superuser_result = await authz_capabilities.get_authorization_capabilities(superuser, session)

    assert result.can_create_team is True
    assert result.can_administer_platform is False
    assert result.model_dump(include={"administration", "features"}) == {
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
    assert superuser_result.model_dump()["features"]["directory"]["actions"]["configure_connection"] is True
