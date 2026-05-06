"""Unit tests for the isolation config layer of the FileSystem tool."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path


class TestResolveIsolationMode:
    """Slice B1 — env var → IsolationMode enum (case-insensitive, defaults to AUTO)."""

    def test_should_default_to_auto_when_value_is_none(self) -> None:
        from lfx.components.tools._filesystem_isolation import (
            IsolationMode,
            resolve_isolation_mode,
        )

        assert resolve_isolation_mode(None) is IsolationMode.AUTO

    def test_should_default_to_auto_when_value_is_empty_string(self) -> None:
        from lfx.components.tools._filesystem_isolation import (
            IsolationMode,
            resolve_isolation_mode,
        )

        assert resolve_isolation_mode("") is IsolationMode.AUTO

    @pytest.mark.parametrize("raw", ["off", "OFF", " off ", "Off"])
    def test_should_accept_off_case_insensitively(self, raw: str) -> None:
        from lfx.components.tools._filesystem_isolation import (
            IsolationMode,
            resolve_isolation_mode,
        )

        assert resolve_isolation_mode(raw) is IsolationMode.OFF

    @pytest.mark.parametrize("raw", ["on", "ON", " on "])
    def test_should_accept_on_case_insensitively(self, raw: str) -> None:
        from lfx.components.tools._filesystem_isolation import (
            IsolationMode,
            resolve_isolation_mode,
        )

        assert resolve_isolation_mode(raw) is IsolationMode.ON

    def test_should_reject_when_value_is_invalid(self) -> None:
        from lfx.components.tools._filesystem_isolation import resolve_isolation_mode

        with pytest.raises(ValueError, match="LANGFLOW_FS_TOOL_USER_ISOLATION"):
            resolve_isolation_mode("strict")


class TestLoadIsolationConfig:
    """Slice B2 — read env vars into a frozen IsolationConfig."""

    def test_should_default_paths_under_default_config_dir(self, tmp_path: Path) -> None:
        from lfx.components.tools._filesystem_isolation import (
            IsolationMode,
            load_isolation_config,
        )

        config = load_isolation_config(env={}, default_config_dir=tmp_path)

        assert config.mode is IsolationMode.AUTO
        assert config.base_dir == (tmp_path / "fs_sandbox").resolve()
        assert config.pepper_path == (tmp_path / ".fs_pepper").resolve()
        assert config.audit_log_path is None

    def test_should_override_base_dir_when_env_var_set(self, tmp_path: Path) -> None:
        from lfx.components.tools._filesystem_isolation import load_isolation_config

        custom_base = tmp_path / "custom_root"
        env = {"LANGFLOW_FS_TOOL_BASE_DIR": str(custom_base)}

        config = load_isolation_config(env=env, default_config_dir=tmp_path)

        assert config.base_dir == custom_base.resolve()

    def test_should_override_audit_log_path_when_env_var_set(self, tmp_path: Path) -> None:
        from lfx.components.tools._filesystem_isolation import load_isolation_config

        audit_log = tmp_path / "audit.jsonl"
        env = {"LANGFLOW_FS_TOOL_AUDIT_LOG": str(audit_log)}

        config = load_isolation_config(env=env, default_config_dir=tmp_path)

        assert config.audit_log_path == audit_log.resolve()

    def test_should_treat_empty_audit_log_env_var_as_disabled(self, tmp_path: Path) -> None:
        from lfx.components.tools._filesystem_isolation import load_isolation_config

        env = {"LANGFLOW_FS_TOOL_AUDIT_LOG": ""}

        config = load_isolation_config(env=env, default_config_dir=tmp_path)

        assert config.audit_log_path is None

    def test_should_apply_isolation_mode_from_env(self, tmp_path: Path) -> None:
        from lfx.components.tools._filesystem_isolation import (
            IsolationMode,
            load_isolation_config,
        )

        env = {"LANGFLOW_FS_TOOL_USER_ISOLATION": "on"}

        config = load_isolation_config(env=env, default_config_dir=tmp_path)

        assert config.mode is IsolationMode.ON

    def test_should_be_immutable(self, tmp_path: Path) -> None:
        # Why this test: the config is read once and threaded through every
        # tool call; mutation would invite TOCTOU bugs where one operation sees
        # one mode and another sees a different one mid-flight.
        from lfx.components.tools._filesystem_isolation import load_isolation_config

        config = load_isolation_config(env={}, default_config_dir=tmp_path)

        with pytest.raises((AttributeError, TypeError)):
            config.mode = "off"  # type: ignore[misc]
