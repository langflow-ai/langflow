import pytest
from lfx.services.settings.feature_flags import FeatureFlags


def test_should_enable_evals_when_env_var_is_unset(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("LANGFLOW_FEATURE_EVALS", raising=False)

    flags = FeatureFlags()

    assert flags.evals is True


def test_should_disable_evals_when_env_var_is_false(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("LANGFLOW_FEATURE_EVALS", "false")

    flags = FeatureFlags()

    assert flags.evals is False
