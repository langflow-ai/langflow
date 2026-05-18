"""Tests for the config_dir validator: ~ expansion and file-path rejection.

config_dir is exercised through the LANGFLOW_CONFIG_DIR env var because
Settings only honors env-sourced values for these fields.
"""

from pathlib import Path

import pytest
from lfx.services.settings.base import Settings


def test_config_dir_expands_tilde(monkeypatch, tmp_path):
    """A ~ in LANGFLOW_CONFIG_DIR is expanded to $HOME, not taken literally."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("LANGFLOW_CONFIG_DIR", "~/langflow-test")
    settings = Settings()
    expected = (tmp_path / "langflow-test").resolve()
    assert settings.config_dir == str(expected)
    assert expected.is_dir()


def test_config_dir_rejects_file_path(monkeypatch, tmp_path):
    """A config_dir pointing to an existing file (not directory) is rejected."""
    file_path = tmp_path / "not-a-dir"
    file_path.write_text("placeholder")
    monkeypatch.setenv("LANGFLOW_CONFIG_DIR", str(file_path))
    with pytest.raises(ValueError, match="must be a directory"):
        Settings()


def test_config_dir_creates_missing_directory(monkeypatch, tmp_path):
    """A non-existent config_dir is created on validation."""
    target = tmp_path / "new-dir" / "nested"
    assert not target.exists()
    monkeypatch.setenv("LANGFLOW_CONFIG_DIR", str(target))
    settings = Settings()
    assert Path(settings.config_dir).is_dir()
