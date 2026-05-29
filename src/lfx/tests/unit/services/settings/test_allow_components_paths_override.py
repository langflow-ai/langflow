"""Tests for allow_components_paths_override enforcement in Settings."""

import tempfile

from lfx.services.settings.base import Settings


def _clear_env(monkeypatch):
    for var in (
        "LANGFLOW_ALLOW_CUSTOM_COMPONENTS",
        "LANGFLOW_ALLOW_COMPONENTS_PATHS_OVERRIDE",
        "LANGFLOW_COMPONENTS_PATH",
        "LANGFLOW_COMPONENTS_INDEX_PATH",
    ):
        monkeypatch.delenv(var, raising=False)


def test_defaults_are_permissive(monkeypatch):
    _clear_env(monkeypatch)
    settings = Settings()
    assert settings.allow_custom_components is True
    assert settings.allow_components_paths_override is True


def test_env_paths_bypass_when_override_true(monkeypatch):
    """Existing behavior: env-var paths act as an allow-list even when custom is False."""
    _clear_env(monkeypatch)
    with tempfile.TemporaryDirectory() as tmp:
        monkeypatch.setenv("LANGFLOW_ALLOW_CUSTOM_COMPONENTS", "false")
        monkeypatch.setenv("LANGFLOW_ALLOW_COMPONENTS_PATHS_OVERRIDE", "true")
        monkeypatch.setenv("LANGFLOW_COMPONENTS_PATH", tmp)
        monkeypatch.setenv("LANGFLOW_COMPONENTS_INDEX_PATH", "/nonexistent/index.json")

        settings = Settings()
        assert tmp in settings.components_path
        assert settings.components_index_path == "/nonexistent/index.json"


def test_env_paths_stripped_when_override_false(monkeypatch):
    """When both flags are off, env-var paths must not bypass the restriction."""
    _clear_env(monkeypatch)
    with tempfile.TemporaryDirectory() as tmp:
        monkeypatch.setenv("LANGFLOW_ALLOW_CUSTOM_COMPONENTS", "false")
        monkeypatch.setenv("LANGFLOW_ALLOW_COMPONENTS_PATHS_OVERRIDE", "false")
        monkeypatch.setenv("LANGFLOW_COMPONENTS_PATH", tmp)
        monkeypatch.setenv("LANGFLOW_COMPONENTS_INDEX_PATH", "/nonexistent/index.json")

        settings = Settings()
        assert tmp not in settings.components_path
        assert settings.components_index_path is None


def test_override_false_has_no_effect_when_custom_allowed(monkeypatch):
    """If allow_custom_components is True, the override flag is a no-op — nothing to bypass."""
    _clear_env(monkeypatch)
    with tempfile.TemporaryDirectory() as tmp:
        monkeypatch.setenv("LANGFLOW_ALLOW_CUSTOM_COMPONENTS", "true")
        monkeypatch.setenv("LANGFLOW_ALLOW_COMPONENTS_PATHS_OVERRIDE", "false")
        monkeypatch.setenv("LANGFLOW_COMPONENTS_PATH", tmp)
        monkeypatch.setenv("LANGFLOW_COMPONENTS_INDEX_PATH", "/nonexistent/index.json")

        settings = Settings()
        assert tmp in settings.components_path
        assert settings.components_index_path == "/nonexistent/index.json"


def test_index_path_preserved_when_env_var_unset(monkeypatch):
    """The index path is only stripped when it came from LANGFLOW_COMPONENTS_INDEX_PATH.

    If that env var is unset, the enforcer must not touch components_index_path even
    when both flags are off.
    """
    _clear_env(monkeypatch)
    monkeypatch.setenv("LANGFLOW_ALLOW_CUSTOM_COMPONENTS", "false")
    monkeypatch.setenv("LANGFLOW_ALLOW_COMPONENTS_PATHS_OVERRIDE", "false")

    settings = Settings()
    # No env var set, so the default (built-in index) must be left intact.
    assert settings.components_index_path is None


def test_multi_path_env_var_stripped_when_override_false(monkeypatch):
    """Comma-separated LANGFLOW_COMPONENTS_PATH entries are each stripped when override is off."""
    _clear_env(monkeypatch)
    with tempfile.TemporaryDirectory() as tmp1, tempfile.TemporaryDirectory() as tmp2:
        monkeypatch.setenv("LANGFLOW_ALLOW_CUSTOM_COMPONENTS", "false")
        monkeypatch.setenv("LANGFLOW_ALLOW_COMPONENTS_PATHS_OVERRIDE", "false")
        monkeypatch.setenv("LANGFLOW_COMPONENTS_PATH", f"{tmp1},{tmp2}")

        settings = Settings()
        assert tmp1 not in settings.components_path
        assert tmp2 not in settings.components_path
