"""Tests for AuthorizationServiceFactory."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from langflow.services.authorization.casbin.service import CasbinAuthorizationService
from langflow.services.authorization.factory import AuthorizationServiceFactory
from lfx.services.authorization.base import BaseAuthorizationService
from lfx.services.settings.auth import AuthSettings


def _make_settings_service(*, authz_enabled: bool = False, superuser_bypass: bool = True) -> SimpleNamespace:
    return SimpleNamespace(
        auth_settings=SimpleNamespace(
            AUTHZ_ENABLED=authz_enabled,
            AUTHZ_SUPERUSER_BYPASS=superuser_bypass,
        )
    )


def test_create_returns_base_authorization_service():
    """Factory produces an instance conforming to the BaseAuthorizationService contract."""
    factory = AuthorizationServiceFactory()
    service = factory.create(_make_settings_service())
    assert isinstance(service, BaseAuthorizationService)
    assert isinstance(service, CasbinAuthorizationService)


def test_create_uses_injected_settings_service():
    """The created service reads its configuration from the injected SettingsService."""
    settings = _make_settings_service(authz_enabled=True)
    factory = AuthorizationServiceFactory()
    service = factory.create(settings)
    assert service.settings_service is settings


def test_factory_name_matches_service_type():
    """Factory exposes the canonical authorization service type name."""
    from langflow.services.schema import ServiceType

    factory = AuthorizationServiceFactory()
    assert factory.name == ServiceType.AUTHORIZATION_SERVICE.value


@pytest.mark.asyncio
async def test_default_install_enables_casbin_without_configuration(monkeypatch, tmp_path):
    """A fresh fork install enforces without an extra or an opt-in environment flag."""
    monkeypatch.delenv("LANGFLOW_AUTHZ_ENABLED", raising=False)
    settings = SimpleNamespace(auth_settings=AuthSettings(CONFIG_DIR=str(tmp_path)))
    service = AuthorizationServiceFactory().create(settings)
    assert await service.is_enabled() is True
    assert await service.supports_team_roles() is True
    assert await service.supports_user_team_sharing() is True
    # Readiness must still wait for the database reconciliation.
    assert service.ready is False


@pytest.mark.asyncio
async def test_explicit_disable_is_respected(monkeypatch, tmp_path):
    monkeypatch.setenv("LANGFLOW_AUTHZ_ENABLED", "false")
    settings = SimpleNamespace(auth_settings=AuthSettings(CONFIG_DIR=str(tmp_path)))
    service = AuthorizationServiceFactory().create(settings)
    assert await service.is_enabled() is False


@pytest.mark.asyncio
async def test_standalone_lfx_remains_provider_free_and_disabled():
    from lfx.services.authorization.service import AuthorizationService

    assert await AuthorizationService().is_enabled() is False


def test_default_package_metadata_includes_casbin():
    from importlib.metadata import requires

    from packaging.requirements import Requirement

    backend = [Requirement(value) for value in requires("langflow-base") or []]
    assert any(requirement.name == "casbin" and requirement.marker is None for requirement in backend)
    assert not any(Requirement(value).name == "casbin" for value in requires("lfx") or [])


@pytest.mark.parametrize("explicit", [False, True])
def test_application_registration_selects_default_but_preserves_an_override(monkeypatch, explicit):
    from langflow.services import utils
    from langflow.services.authorization.service import LangflowAuthorizationService
    from lfx.services import manager as manager_module
    from lfx.services.manager import ServiceManager
    from lfx.services.schema import ServiceType

    manager = ServiceManager()
    if explicit:
        manager.register_service_class(ServiceType.AUTHORIZATION_SERVICE, LangflowAuthorizationService)
    monkeypatch.setattr(manager_module, "get_service_manager", lambda: manager)
    utils.register_all_service_factories()
    expected = LangflowAuthorizationService if explicit else CasbinAuthorizationService
    assert manager.service_classes[ServiceType.AUTHORIZATION_SERVICE] is expected


def test_factory_does_not_fall_back_if_casbin_initialization_fails(monkeypatch):
    from langflow.services.authorization.casbin import store

    def broken_dependency(_rules):
        message = "casbin is unavailable"
        raise ModuleNotFoundError(message)

    monkeypatch.setattr(store, "enforcer_for", broken_dependency)
    with pytest.raises(ModuleNotFoundError, match="casbin is unavailable"):
        AuthorizationServiceFactory().create(_make_settings_service(authz_enabled=True))
