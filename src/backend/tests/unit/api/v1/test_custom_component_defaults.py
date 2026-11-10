"""Default custom-code policy and the explicit trusted-deployment opt-out."""

from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from langflow.api.v1.custom_component_policy import resolve_component_code_for_action
from langflow.services.database.models.user.model import User
from lfx.interface.components import component_cache
from lfx.services.catalog_policy.base import CatalogPolicySnapshot
from lfx.services.settings.groups.security import SecuritySettings


@pytest.mark.parametrize(
    ("is_superuser", "settings_overrides", "allowed"),
    [(False, {}, False), (True, {}, True), (False, {"custom_component_admin_only": False}, True)],
)
def test_custom_code_requires_an_administrator_by_default(monkeypatch, is_superuser, settings_overrides, allowed):
    settings = SecuritySettings(**settings_overrides)
    user = User(username="author", password="", is_active=True, is_superuser=is_superuser)
    monkeypatch.setattr(
        "langflow.api.v1.custom_component_policy.get_component_hash_lookups_for_validation",
        dict,
    )
    monkeypatch.setattr(component_cache, "all_known_hashes", set())

    def resolve():
        return resolve_component_code_for_action(
            "untrusted custom source",
            user=user,
            settings=settings,
            snapshot=CatalogPolicySnapshot(),
            disabled_detail="Custom code is disabled",
            admin_only_detail="Custom code requires an administrator",
        )

    if allowed:
        assert resolve() == "untrusted custom source"
    else:
        with pytest.raises(HTTPException) as exc_info:
            resolve()
        assert exc_info.value.status_code == 403
        assert exc_info.value.detail == "Custom code requires an administrator"


@pytest.mark.parametrize(
    ("is_superuser", "admin_only", "registered"),
    [(False, True, False), (True, True, True), (False, False, True)],
)
async def test_project_creation_respects_stdio_policy_without_blocking_projects(
    client, logged_in_headers, active_user, monkeypatch, is_superuser, admin_only, registered
):
    from langflow.api.v1 import projects
    from langflow.services.deps import get_settings_service, session_scope

    settings = get_settings_service().settings
    monkeypatch.setattr(settings, "custom_component_admin_only", admin_only)
    monkeypatch.setattr(settings, "add_projects_to_mcp_servers", True)
    async with session_scope() as session:
        actor = await session.get(User, active_user.id)
        actor.is_superuser = is_superuser
        session.add(actor)
    register = AsyncMock(return_value=True)
    monkeypatch.setattr(projects, "register_mcp_servers_for_project", register)
    response = await client.post("api/v1/projects/", json={"name": "policy project"}, headers=logged_in_headers)

    assert response.status_code == 201, response.text
    assert register.await_count == int(registered)
