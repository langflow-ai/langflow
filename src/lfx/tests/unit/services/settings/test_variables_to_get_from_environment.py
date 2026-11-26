"""`LANGFLOW_VARIABLES_TO_GET_FROM_ENVIRONMENT` is a comma-separated list of variable names.

The names are looked up verbatim in `os.environ`, so a space after a comma must not become part
of the name, and an empty value must not add an empty name to the list.
"""

import pytest
from lfx.services.settings.base import Settings
from lfx.services.settings.constants import VARIABLES_TO_GET_FROM_ENVIRONMENT

ENV_NAME = "LANGFLOW_VARIABLES_TO_GET_FROM_ENVIRONMENT"


def _extra_names(settings: Settings) -> set[str]:
    return set(settings.variables_to_get_from_environment) - set(VARIABLES_TO_GET_FROM_ENVIRONMENT)


@pytest.fixture(autouse=True)
def _disable_agentic_variables(monkeypatch):
    # Keeps the Assistant's own variables out of the list so only the custom names remain.
    monkeypatch.setenv("LANGFLOW_AGENTIC_EXPERIENCE", "false")


@pytest.mark.parametrize(
    "env_value",
    ["MY_KEY,OTHER_KEY", "MY_KEY, OTHER_KEY", " MY_KEY ,\tOTHER_KEY ", "MY_KEY,OTHER_KEY,", "MY_KEY,,OTHER_KEY"],
)
def test_should_strip_names_and_drop_empty_entries_from_the_environment(monkeypatch, env_value):
    monkeypatch.setenv(ENV_NAME, env_value)

    settings = Settings()

    assert _extra_names(settings) == {"MY_KEY", "OTHER_KEY"}
    assert "" not in settings.variables_to_get_from_environment


@pytest.mark.parametrize("env_value", ["", " ", ","])
def test_should_not_add_an_empty_name_for_an_empty_environment_value(monkeypatch, env_value):
    monkeypatch.setenv(ENV_NAME, env_value)

    settings = Settings()

    assert _extra_names(settings) == set()


def test_should_keep_the_baseline_names_when_custom_names_are_given(monkeypatch):
    monkeypatch.setenv(ENV_NAME, "MY_KEY, OTHER_KEY")

    settings = Settings()

    assert set(VARIABLES_TO_GET_FROM_ENVIRONMENT) <= set(settings.variables_to_get_from_environment)
