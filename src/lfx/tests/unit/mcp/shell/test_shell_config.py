"""Tests for ShellServerConfig — env var reading and clamping."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest
from lfx.mcp.shell.shell_config import ShellMode, ShellServerConfig


class TestShellServerConfigDefaults:
    def test_should_use_cwd_as_default_working_directory(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
        monkeypatch.delenv("LANGFLOW_SHELL_WORKING_DIR", raising=False)
        monkeypatch.chdir(tmp_path)
        config = ShellServerConfig.from_environment()
        assert Path(config.working_directory) == tmp_path.resolve()

    def test_should_default_to_read_write_mode(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv("LANGFLOW_SHELL_MODE", raising=False)
        config = ShellServerConfig.from_environment()
        assert config.mode == ShellMode.READ_WRITE

    def test_should_default_max_timeout_to_120_seconds(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv("LANGFLOW_SHELL_MAX_TIMEOUT", raising=False)
        config = ShellServerConfig.from_environment()
        assert config.max_timeout == 120

    def test_should_default_max_output_bytes_to_16kb(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv("LANGFLOW_SHELL_MAX_OUTPUT_BYTES", raising=False)
        config = ShellServerConfig.from_environment()
        assert config.max_output_bytes == 16 * 1024

    def test_should_default_max_command_length_to_4kb(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv("LANGFLOW_SHELL_MAX_COMMAND_LENGTH", raising=False)
        config = ShellServerConfig.from_environment()
        assert config.max_command_length == 4 * 1024


class TestShellServerConfigEnvOverrides:
    def test_should_read_working_directory_from_env(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
        monkeypatch.setenv("LANGFLOW_SHELL_WORKING_DIR", str(tmp_path))
        config = ShellServerConfig.from_environment()
        assert Path(config.working_directory) == tmp_path.resolve()

    def test_should_read_mode_read_only_from_env(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("LANGFLOW_SHELL_MODE", "read_only")
        config = ShellServerConfig.from_environment()
        assert config.mode == ShellMode.READ_ONLY

    def test_should_be_case_insensitive_for_mode(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("LANGFLOW_SHELL_MODE", "READ_ONLY")
        config = ShellServerConfig.from_environment()
        assert config.mode == ShellMode.READ_ONLY

    def test_should_read_max_timeout_from_env(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("LANGFLOW_SHELL_MAX_TIMEOUT", "60")
        config = ShellServerConfig.from_environment()
        assert config.max_timeout == 60

    def test_should_read_max_output_bytes_from_env(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("LANGFLOW_SHELL_MAX_OUTPUT_BYTES", "2048")
        config = ShellServerConfig.from_environment()
        assert config.max_output_bytes == 2048


class TestShellServerConfigValidation:
    def test_should_reject_unknown_mode(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("LANGFLOW_SHELL_MODE", "anything_else")
        with pytest.raises(ValueError, match="LANGFLOW_SHELL_MODE"):
            ShellServerConfig.from_environment()

    def test_should_reject_negative_max_timeout(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("LANGFLOW_SHELL_MAX_TIMEOUT", "-1")
        with pytest.raises(ValueError, match="LANGFLOW_SHELL_MAX_TIMEOUT"):
            ShellServerConfig.from_environment()

    def test_should_reject_zero_max_timeout(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("LANGFLOW_SHELL_MAX_TIMEOUT", "0")
        with pytest.raises(ValueError, match="LANGFLOW_SHELL_MAX_TIMEOUT"):
            ShellServerConfig.from_environment()

    def test_should_reject_non_integer_max_timeout(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("LANGFLOW_SHELL_MAX_TIMEOUT", "abc")
        with pytest.raises(ValueError, match="LANGFLOW_SHELL_MAX_TIMEOUT"):
            ShellServerConfig.from_environment()

    def test_should_reject_zero_max_output_bytes(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("LANGFLOW_SHELL_MAX_OUTPUT_BYTES", "0")
        with pytest.raises(ValueError, match="LANGFLOW_SHELL_MAX_OUTPUT_BYTES"):
            ShellServerConfig.from_environment()

    def test_should_reject_nonexistent_working_directory(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("LANGFLOW_SHELL_WORKING_DIR", "/path/does/not/exist/xyz")
        with pytest.raises(ValueError, match="LANGFLOW_SHELL_WORKING_DIR"):
            ShellServerConfig.from_environment()

    def test_should_reject_working_directory_that_is_a_file(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ):
        target_file = tmp_path / "afile.txt"
        target_file.write_text("hello")
        monkeypatch.setenv("LANGFLOW_SHELL_WORKING_DIR", str(target_file))
        with pytest.raises(ValueError, match="LANGFLOW_SHELL_WORKING_DIR"):
            ShellServerConfig.from_environment()


class TestShellServerConfigImmutability:
    def test_should_be_frozen(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv("LANGFLOW_SHELL_WORKING_DIR", raising=False)
        config = ShellServerConfig.from_environment()
        with pytest.raises(dataclasses.FrozenInstanceError):
            config.max_timeout = 99  # type: ignore[misc]


class TestShellServerConfigClamping:
    def test_clamp_timeout_should_return_min_of_requested_and_max(self):
        config = ShellServerConfig(
            working_directory=str(Path.cwd()),
            mode=ShellMode.READ_WRITE,
            max_timeout=60,
            max_output_bytes=1024,
            max_command_length=4096,
        )
        assert config.clamp_timeout(30) == 30
        assert config.clamp_timeout(60) == 60
        assert config.clamp_timeout(120) == 60

    def test_clamp_timeout_should_reject_non_positive(self):
        config = ShellServerConfig(
            working_directory=str(Path.cwd()),
            mode=ShellMode.READ_WRITE,
            max_timeout=60,
            max_output_bytes=1024,
            max_command_length=4096,
        )
        with pytest.raises(ValueError, match="timeout"):
            config.clamp_timeout(0)
        with pytest.raises(ValueError, match="timeout"):
            config.clamp_timeout(-5)
