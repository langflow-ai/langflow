"""Unit tests for the custom-component execution security-posture warning (LE-2533)."""

from types import SimpleNamespace

import pytest
from langflow.utils.security_posture import (
    CUSTOM_COMPONENT_EXECUTION_WARNING,
    custom_component_execution_warning,
)


def _settings_service(*, auto_login: bool, allow_custom_components: bool, admin_only: bool):
    return SimpleNamespace(
        auth_settings=SimpleNamespace(AUTO_LOGIN=auto_login),
        settings=SimpleNamespace(
            allow_custom_components=allow_custom_components,
            custom_component_admin_only=admin_only,
        ),
    )


def test_warns_multi_user_permissive():
    """The exposed posture: multi-user, custom components on, not admin-only."""
    svc = _settings_service(auto_login=False, allow_custom_components=True, admin_only=False)
    assert custom_component_execution_warning(svc) == CUSTOM_COMPONENT_EXECUTION_WARNING


def test_warning_names_both_lockdowns():
    """Remediation must point at both settings so operators can pick either."""
    warning = custom_component_execution_warning(
        _settings_service(auto_login=False, allow_custom_components=True, admin_only=False)
    )
    assert "LANGFLOW_CUSTOM_COMPONENT_ADMIN_ONLY=true" in warning
    assert "LANGFLOW_ALLOW_CUSTOM_COMPONENTS=false" in warning


def test_silent_single_user_default():
    """AUTO_LOGIN=true is the single-superuser default: no non-admin exists, so no warning."""
    svc = _settings_service(auto_login=True, allow_custom_components=True, admin_only=False)
    assert custom_component_execution_warning(svc) is None


def test_silent_when_admin_only():
    svc = _settings_service(auto_login=False, allow_custom_components=True, admin_only=True)
    assert custom_component_execution_warning(svc) is None


def test_silent_when_custom_components_disabled():
    svc = _settings_service(auto_login=False, allow_custom_components=False, admin_only=False)
    assert custom_component_execution_warning(svc) is None


@pytest.mark.parametrize("svc", [None, SimpleNamespace(), SimpleNamespace(auth_settings=None, settings=None)])
def test_missing_settings_never_raises(svc):
    """A partial/None settings service must degrade to no-warning, never raise at startup."""
    assert custom_component_execution_warning(svc) is None


def test_missing_attributes_use_model_defaults():
    """Absent attributes fall back to declared (permissive) defaults, so a bare multi-user object still warns."""
    svc = SimpleNamespace(auth_settings=SimpleNamespace(AUTO_LOGIN=False), settings=SimpleNamespace())
    assert custom_component_execution_warning(svc) == CUSTOM_COMPONENT_EXECUTION_WARNING
