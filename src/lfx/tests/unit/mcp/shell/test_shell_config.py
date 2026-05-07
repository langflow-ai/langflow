"""Tests for ShellServerConfig — env var reading and clamping."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest
from lfx.mcp.shell.shell_config import ShellMode, ShellServerConfig


class TestShellServerConfigDefaults:
    def test_should_raise_when_working_directory_env_unset(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
        """PR review #1: Path.cwd() fallback exposes user files when langflow is started from $HOME.

        Refuse to boot without an explicit LANGFLOW_SHELL_WORKING_DIR — the security model
        leans entirely on the working dir being a deliberate sandbox.
        """
        monkeypatch.delenv("LANGFLOW_SHELL_WORKING_DIR", raising=False)
        monkeypatch.chdir(tmp_path)
        with pytest.raises(ValueError, match="LANGFLOW_SHELL_WORKING_DIR"):
            ShellServerConfig.from_environment()

    def test_should_default_to_read_only_mode(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
        """PR review #2: read_write default is too wide a door.

        Allows git/pip/npm/curl as the langflow process user. Default to
        read_only; read_write is an explicit opt-in.
        """
        monkeypatch.setenv("LANGFLOW_SHELL_WORKING_DIR", str(tmp_path))
        monkeypatch.delenv("LANGFLOW_SHELL_MODE", raising=False)
        config = ShellServerConfig.from_environment()
        assert config.mode == ShellMode.READ_ONLY

    def test_should_default_max_timeout_to_30_seconds(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
        # 30s is web-proxy-friendly: stays under Heroku's 30s, ALB 60s,
        # Cloudflare 100s, nginx default 60s. Operators with longer-running
        # commands raise LANGFLOW_SHELL_MAX_TIMEOUT explicitly.
        monkeypatch.setenv("LANGFLOW_SHELL_WORKING_DIR", str(tmp_path))
        monkeypatch.delenv("LANGFLOW_SHELL_MAX_TIMEOUT", raising=False)
        config = ShellServerConfig.from_environment()
        assert config.max_timeout == 30

    def test_should_default_max_output_bytes_to_16kb(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
        monkeypatch.setenv("LANGFLOW_SHELL_WORKING_DIR", str(tmp_path))
        monkeypatch.delenv("LANGFLOW_SHELL_MAX_OUTPUT_BYTES", raising=False)
        config = ShellServerConfig.from_environment()
        assert config.max_output_bytes == 16 * 1024

    def test_should_default_max_command_length_to_4kb(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
        monkeypatch.setenv("LANGFLOW_SHELL_WORKING_DIR", str(tmp_path))
        monkeypatch.delenv("LANGFLOW_SHELL_MAX_COMMAND_LENGTH", raising=False)
        config = ShellServerConfig.from_environment()
        assert config.max_command_length == 4 * 1024

    def test_should_default_max_concurrent_to_4(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
        monkeypatch.setenv("LANGFLOW_SHELL_WORKING_DIR", str(tmp_path))
        monkeypatch.delenv("LANGFLOW_SHELL_MAX_CONCURRENT", raising=False)
        config = ShellServerConfig.from_environment()
        assert config.max_concurrent == 4

    def test_should_default_queue_timeout_to_10_seconds(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
        monkeypatch.setenv("LANGFLOW_SHELL_WORKING_DIR", str(tmp_path))
        monkeypatch.delenv("LANGFLOW_SHELL_QUEUE_TIMEOUT", raising=False)
        config = ShellServerConfig.from_environment()
        assert config.queue_timeout == 10

    def test_should_default_isolation_to_shared(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
        from lfx.mcp.shell.shell_config import IsolationMode

        # ``shared`` is the historical behaviour; ephemeral is opt-in so
        # operators upgrading do not see a sudden state-loss change.
        monkeypatch.setenv("LANGFLOW_SHELL_WORKING_DIR", str(tmp_path))
        monkeypatch.delenv("LANGFLOW_SHELL_ISOLATION", raising=False)
        config = ShellServerConfig.from_environment()
        assert config.isolation is IsolationMode.SHARED

    def test_should_read_ephemeral_isolation_from_env(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
        from lfx.mcp.shell.shell_config import IsolationMode

        monkeypatch.setenv("LANGFLOW_SHELL_WORKING_DIR", str(tmp_path))
        monkeypatch.setenv("LANGFLOW_SHELL_ISOLATION", "ephemeral")
        config = ShellServerConfig.from_environment()
        assert config.isolation is IsolationMode.EPHEMERAL

    def test_should_reject_unknown_isolation_value(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
        monkeypatch.setenv("LANGFLOW_SHELL_WORKING_DIR", str(tmp_path))
        monkeypatch.setenv("LANGFLOW_SHELL_ISOLATION", "container")
        with pytest.raises(ValueError, match="LANGFLOW_SHELL_ISOLATION"):
            ShellServerConfig.from_environment()


class TestShellServerConfigEnvOverrides:
    @pytest.fixture(autouse=True)
    def _set_working_dir(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
        # WORKING_DIR is now mandatory (PR review #1); every test in this class
        # asserts behaviour orthogonal to it.
        monkeypatch.setenv("LANGFLOW_SHELL_WORKING_DIR", str(tmp_path))

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
    @pytest.fixture(autouse=True)
    def _set_working_dir(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
        # Same rationale as TestShellServerConfigEnvOverrides: each test below
        # exercises a *non*-WORKING_DIR validation path.
        monkeypatch.setenv("LANGFLOW_SHELL_WORKING_DIR", str(tmp_path))

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
    def test_should_be_frozen(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
        monkeypatch.setenv("LANGFLOW_SHELL_WORKING_DIR", str(tmp_path))
        config = ShellServerConfig.from_environment()
        with pytest.raises(dataclasses.FrozenInstanceError):
            config.max_timeout = 99  # type: ignore[misc]


class TestShellServerConfigClamping:
    def test_clamp_timeout_should_return_min_of_requested_and_max(self):
        from lfx.mcp.shell.shell_config import IsolationMode

        config = ShellServerConfig(
            working_directory=str(Path.cwd()),
            mode=ShellMode.READ_WRITE,
            max_timeout=60,
            max_output_bytes=1024,
            max_command_length=4096,
            max_concurrent=4,
            queue_timeout=10,
            isolation=IsolationMode.SHARED,
        )
        assert config.clamp_timeout(30) == 30
        assert config.clamp_timeout(60) == 60
        assert config.clamp_timeout(120) == 60

    def test_clamp_timeout_should_reject_non_positive(self):
        from lfx.mcp.shell.shell_config import IsolationMode

        config = ShellServerConfig(
            working_directory=str(Path.cwd()),
            mode=ShellMode.READ_WRITE,
            max_timeout=60,
            max_output_bytes=1024,
            max_command_length=4096,
            max_concurrent=4,
            queue_timeout=10,
            isolation=IsolationMode.SHARED,
        )
        with pytest.raises(ValueError, match="timeout"):
            config.clamp_timeout(0)
        with pytest.raises(ValueError, match="timeout"):
            config.clamp_timeout(-5)
