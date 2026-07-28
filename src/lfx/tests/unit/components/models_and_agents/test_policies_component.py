from types import SimpleNamespace

from lfx.components.models_and_agents.policies_component import PoliciesComponent


def test_code_execution_denied_when_allow_custom_components_setting_is_missing(monkeypatch):
    settings_service = SimpleNamespace(settings=SimpleNamespace())
    monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: settings_service)

    assert PoliciesComponent._code_execution_allowed() is False
