"""Tests for the components_path validator's LANGFLOW_COMPONENTS_PATH handling.

The validator's only job for env paths is to avoid appending one that
pydantic-settings has already loaded into the list. pydantic-settings does
the primary load; the validator just guards against duplicates.
"""

from lfx.constants import BASE_COMPONENTS_PATH
from lfx.services.settings.base import Settings


def test_components_path_env_loaded(monkeypatch, tmp_path):
    """LANGFLOW_COMPONENTS_PATH pointing to an existing dir ends up in components_path."""
    monkeypatch.setenv("LANGFLOW_COMPONENTS_PATH", str(tmp_path))
    settings = Settings()
    assert str(tmp_path) in settings.components_path


def test_components_path_env_no_duplicate(monkeypatch, tmp_path):
    """The env path appears exactly once even though the validator also inspects it."""
    monkeypatch.setenv("LANGFLOW_COMPONENTS_PATH", str(tmp_path))
    settings = Settings()
    assert settings.components_path.count(str(tmp_path)) == 1


def test_components_path_default_when_unset(monkeypatch):
    """With no env var and no explicit list, the default base path is used."""
    monkeypatch.delenv("LANGFLOW_COMPONENTS_PATH", raising=False)
    settings = Settings()
    assert BASE_COMPONENTS_PATH in settings.components_path
