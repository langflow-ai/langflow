"""Default custom-code policy and the explicit trusted-deployment opt-out."""

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
