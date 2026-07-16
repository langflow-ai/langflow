"""The agentic global variables must follow the `agentic_experience` gate.

`variables_to_get_from_environment` is populated by a field validator, which cannot read the
sibling `agentic_experience` field and therefore re-reads `LANGFLOW_AGENTIC_EXPERIENCE` from the
environment. These tests pin the two defaults together: a drift between them silently imports
FLOW_ID / COMPONENT_ID / FIELD_NAME / ASTRA_TOKEN while the assistant experience is off.
"""

import pytest
from lfx.services.settings.base import Settings
from lfx.services.settings.constants import AGENTIC_VARIABLES, VARIABLES_TO_GET_FROM_ENVIRONMENT


@pytest.fixture(autouse=True)
def _clear_agentic_env(monkeypatch):
    monkeypatch.delenv("LANGFLOW_AGENTIC_EXPERIENCE", raising=False)


def test_should_not_import_agentic_variables_when_experience_is_off_by_default():
    settings = Settings()

    assert settings.agentic_experience is False
    assert not set(AGENTIC_VARIABLES) & set(settings.variables_to_get_from_environment)


def test_should_import_agentic_variables_when_experience_is_enabled(monkeypatch):
    monkeypatch.setenv("LANGFLOW_AGENTIC_EXPERIENCE", "true")

    settings = Settings()

    assert settings.agentic_experience is True
    assert set(AGENTIC_VARIABLES) <= set(settings.variables_to_get_from_environment)


def test_should_not_import_agentic_variables_when_experience_is_explicitly_disabled(monkeypatch):
    monkeypatch.setenv("LANGFLOW_AGENTIC_EXPERIENCE", "false")

    settings = Settings()

    assert settings.agentic_experience is False
    assert not set(AGENTIC_VARIABLES) & set(settings.variables_to_get_from_environment)


@pytest.mark.parametrize("enabled", ["true", "false"])
def test_should_always_keep_the_baseline_environment_variables(monkeypatch, enabled):
    monkeypatch.setenv("LANGFLOW_AGENTIC_EXPERIENCE", enabled)

    settings = Settings()

    assert set(VARIABLES_TO_GET_FROM_ENVIRONMENT) <= set(settings.variables_to_get_from_environment)
