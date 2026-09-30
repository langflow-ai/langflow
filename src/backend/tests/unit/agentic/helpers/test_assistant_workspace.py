"""Tests for resolve_assistant_fs_root — assistant workspace path resolution.

Forward-compatible with PR #13031 (per-user FileSystemTool isolation):
- Env var name (LANGFLOW_FS_TOOL_BASE_DIR) and default path (~/.langflow/fs_tool/fs_sandbox)
  match the contract that PR #13031 introduces.
- When PR #13031 ships its isolation module, this resolver returns None so the
  flow_preparation injector skips writing root_path and lets the component
  resolve its own per-user namespace.
"""

import importlib.machinery
import importlib.util
import sys

import pytest
from langflow.agentic.helpers.assistant_workspace import (
    BASE_DIR_ENV,
    DEFAULT_BASE_SUBPATH,
    ISOLATION_MODULE,
    resolve_assistant_fs_root,
)


class TestResolveAssistantFsRoot:
    """Resolution order: skip if isolation module is present →
    env var (expanded, stripped) → ~/.langflow/fs_tool/fs_sandbox default.
    Always mkdir when a path is returned.
    """  # noqa: D205

    @pytest.fixture(autouse=True)
    def _isolate_env(self, monkeypatch, tmp_path):
        monkeypatch.delenv(BASE_DIR_ENV, raising=False)
        # Pin HOME so the default path test is portable.
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.setenv("HOME", str(fake_home))
        monkeypatch.setenv("USERPROFILE", str(fake_home))
        # Make sure the isolation module is NOT importable by default
        # (so we test the legacy path; one test below puts it back).
        # The module ships on disk once PR #13031 lands, so `find_spec`
        # would discover it via the filesystem — stub it out to force
        # the legacy resolution path.
        monkeypatch.delitem(sys.modules, ISOLATION_MODULE, raising=False)
        original_find_spec = importlib.util.find_spec
        monkeypatch.setattr(
            importlib.util,
            "find_spec",
            lambda name, *a, **kw: (None if name == ISOLATION_MODULE else original_find_spec(name, *a, **kw)),
        )
        return fake_home

    def test_should_resolve_to_default_when_env_unset(self, _isolate_env):  # noqa: PT019
        result = resolve_assistant_fs_root()

        assert result == (_isolate_env / DEFAULT_BASE_SUBPATH).resolve()

    def test_should_resolve_to_env_var_when_set(self, tmp_path, monkeypatch):
        target = tmp_path / "custom"
        monkeypatch.setenv(BASE_DIR_ENV, str(target))

        result = resolve_assistant_fs_root()

        assert result == target.resolve()

    def test_should_expanduser_in_env_var(self, _isolate_env, monkeypatch):  # noqa: PT019
        monkeypatch.setenv(BASE_DIR_ENV, "~/my-workspace")

        result = resolve_assistant_fs_root()

        assert result == (_isolate_env / "my-workspace").resolve()

    def test_should_create_workspace_dir_if_missing(self, tmp_path, monkeypatch):
        target = tmp_path / "new-dir"
        assert not target.exists()
        monkeypatch.setenv(BASE_DIR_ENV, str(target))

        resolve_assistant_fs_root()

        assert target.exists()
        assert target.is_dir()

    def test_should_be_idempotent_when_workspace_already_exists(self, tmp_path, monkeypatch):
        target = tmp_path / "existing"
        target.mkdir()
        sentinel = target / "sentinel.txt"
        sentinel.write_text("keep me", encoding="utf-8")
        monkeypatch.setenv(BASE_DIR_ENV, str(target))

        result = resolve_assistant_fs_root()

        assert result == target.resolve()
        assert sentinel.read_text(encoding="utf-8") == "keep me"

    def test_should_strip_whitespace_from_env_var(self, tmp_path, monkeypatch):
        target = tmp_path / "padded"
        monkeypatch.setenv(BASE_DIR_ENV, f"  {target}  ")

        result = resolve_assistant_fs_root()

        assert result == target.resolve()

    def test_should_fall_back_to_default_when_env_var_is_blank(self, _isolate_env, monkeypatch):  # noqa: PT019
        monkeypatch.setenv(BASE_DIR_ENV, "   ")

        result = resolve_assistant_fs_root()

        assert result == (_isolate_env / DEFAULT_BASE_SUBPATH).resolve()

    def test_should_create_parent_dirs_when_missing(self, tmp_path, monkeypatch):
        target = tmp_path / "deep" / "nested" / "workspace"
        monkeypatch.setenv(BASE_DIR_ENV, str(target))

        result = resolve_assistant_fs_root()

        assert result == target.resolve()
        assert target.is_dir()

    def test_should_return_none_when_isolation_module_is_present(self, monkeypatch, tmp_path):
        """When PR #13031 lands the FileSystemTool self-resolves a per-user namespace.

        We detect that by importing the isolation module shipped in #13031 and,
        if it's present, return None — telling the flow_preparation injector
        to skip writing root_path so the component handles its own resolution.
        """
        # Even with the env var set we must skip — once isolation is active,
        # any injected root_path would be misinterpreted as a sub_path.
        monkeypatch.setenv(BASE_DIR_ENV, str(tmp_path / "ignored"))
        # Simulate the isolation module being importable.
        fake_module = type(sys)(ISOLATION_MODULE)
        monkeypatch.setitem(sys.modules, ISOLATION_MODULE, fake_module)
        # Patch importlib.util.find_spec to report the module as available.
        original = importlib.util.find_spec
        monkeypatch.setattr(
            importlib.util,
            "find_spec",
            lambda name, *a, **kw: (
                importlib.machinery.ModuleSpec(name, None) if name == ISOLATION_MODULE else original(name, *a, **kw)
            ),
        )

        result = resolve_assistant_fs_root()

        assert result is None
