"""Tests for shared config discovery helpers."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from lfx.services.config_discovery import resolve_config_dir


class TestResolveConfigDir:
    """Tests for resolve_config_dir resolution branches."""

    def test_explicit_path_is_returned_as_is(self):
        result = resolve_config_dir(Path("/explicit/path"))
        assert result == Path("/explicit/path")

    def test_explicit_string_is_converted_to_path(self):
        result = resolve_config_dir("/explicit/string")
        assert result == Path("/explicit/string")

    def test_settings_service_config_dir_is_used_when_no_explicit(self):
        settings_service = MagicMock()
        settings_service.settings.config_dir = "/from/settings"

        result = resolve_config_dir(None, settings_service=settings_service)

        assert result == Path("/from/settings")

    def test_falls_back_to_cwd_when_no_explicit_and_no_settings(self):
        result = resolve_config_dir(None)
        assert result == Path.cwd()

    def test_falls_back_to_cwd_when_settings_service_is_none(self):
        result = resolve_config_dir(None, settings_service=None)
        assert result == Path.cwd()

    def test_falls_back_to_cwd_when_settings_has_no_settings_attr(self):
        settings_service = object()  # no .settings attribute
        result = resolve_config_dir(None, settings_service=settings_service)
        assert result == Path.cwd()

    def test_falls_back_to_cwd_when_config_dir_is_empty_string(self):
        settings_service = MagicMock()
        settings_service.settings.config_dir = ""

        result = resolve_config_dir(None, settings_service=settings_service)

        assert result == Path.cwd()

    def test_explicit_takes_precedence_over_settings(self):
        settings_service = MagicMock()
        settings_service.settings.config_dir = "/from/settings"

        result = resolve_config_dir(Path("/explicit"), settings_service=settings_service)

        assert result == Path("/explicit")


class TestLoadTomlConfig:
    """Tests for load_toml_config error handling."""

    def test_permission_error_returns_none(self, tmp_path):
        from lfx.services.config_discovery import load_toml_config

        config_file = tmp_path / "lfx.toml"
        config_file.write_text("[section]\nkey = 'value'\n")
        config_file.chmod(0o000)

        try:
            result = load_toml_config(config_file)
            assert result is None
        finally:
            config_file.chmod(0o644)

    def test_valid_toml_is_loaded(self, tmp_path):
        from lfx.services.config_discovery import load_toml_config

        config_file = tmp_path / "lfx.toml"
        config_file.write_text("[section]\nkey = 'value'\n")

        result = load_toml_config(config_file)

        assert result == {"section": {"key": "value"}}
