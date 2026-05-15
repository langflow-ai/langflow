"""Tests for the agentic-variables fallback in the variables_to_get_from_environment validator."""

from lfx.services.settings.base import Settings
from lfx.services.settings.constants import AGENTIC_VARIABLES, VARIABLES_TO_GET_FROM_ENVIRONMENT


def test_agentic_variables_excluded_by_default(monkeypatch):
    """When LANGFLOW_AGENTIC_EXPERIENCE is unset, AGENTIC_VARIABLES are not loaded.

    This matches the documented agentic_experience=False field default.
    """
    monkeypatch.delenv("LANGFLOW_AGENTIC_EXPERIENCE", raising=False)
    settings = Settings()
    for var in AGENTIC_VARIABLES:
        assert var not in settings.variables_to_get_from_environment


def test_agentic_variables_included_when_explicitly_enabled(monkeypatch):
    """LANGFLOW_AGENTIC_EXPERIENCE=true includes AGENTIC_VARIABLES in the env-fallback list."""
    monkeypatch.setenv("LANGFLOW_AGENTIC_EXPERIENCE", "true")
    settings = Settings()
    for var in AGENTIC_VARIABLES:
        assert var in settings.variables_to_get_from_environment


def test_agentic_variables_excluded_when_explicitly_disabled(monkeypatch):
    monkeypatch.setenv("LANGFLOW_AGENTIC_EXPERIENCE", "false")
    settings = Settings()
    for var in AGENTIC_VARIABLES:
        assert var not in settings.variables_to_get_from_environment


def test_baseline_variables_always_present(monkeypatch):
    """The non-agentic VARIABLES_TO_GET_FROM_ENVIRONMENT list is always loaded."""
    monkeypatch.delenv("LANGFLOW_AGENTIC_EXPERIENCE", raising=False)
    settings = Settings()
    for var in VARIABLES_TO_GET_FROM_ENVIRONMENT:
        assert var in settings.variables_to_get_from_environment
