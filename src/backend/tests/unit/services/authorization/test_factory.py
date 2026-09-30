"""Tests for AuthorizationServiceFactory."""

from __future__ import annotations

from types import SimpleNamespace

from langflow.services.authorization.factory import AuthorizationServiceFactory
from langflow.services.authorization.service import LangflowAuthorizationService
from lfx.services.authorization.base import BaseAuthorizationService


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
    assert isinstance(service, LangflowAuthorizationService)


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
