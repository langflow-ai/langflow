"""Unit tests for ``lfx init`` — init_command and helpers.

All tests run entirely in-process; no running Langflow instance required.
Filesystem operations use ``tmp_path`` so every test gets a fresh sandbox.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
import typer
from lfx.__main__ import app
from lfx.cli.init import (
    _ENVIRONMENTS_YAML,
    _GITIGNORE,
    _TEMPLATES_DIR,
    _TEST_FLOWS_PY,
    _copy_template,
    _write,
    init_command,
)
from typer.testing import CliRunner

if TYPE_CHECKING:
    from pathlib import Path

runner = CliRunner()

# ---------------------------------------------------------------------------
# Constants / helpers
# ---------------------------------------------------------------------------

_GHA_SRC = _TEMPLATES_DIR / "github-actions"
_SHELL_SRC = _TEMPLATES_DIR / "shell"


def _run_init(
    project_dir: Path,
    *,
    github_actions: bool = False,
    overwrite: bool = False,
    example: bool = False,
) -> None:
    """Thin wrapper around init_command with safe defaults for most tests."""
    init_command(
        project_dir=project_dir,
        github_actions=github_actions,
        overwrite=overwrite,
        example=example,
    )


# ---------------------------------------------------------------------------
# _write() helper
# ---------------------------------------------------------------------------


class TestWriteHelper:
    def test_creates_file_with_content(self, tmp_path: Path) -> None:
        target = tmp_path
        created: list[tuple[str, str]] = []
        dest = tmp_path / "output.txt"
        _write(dest, "hello", "label", created, target=target, overwrite=False)
        assert dest.exists()
        assert dest.read_text(encoding="utf-8") == "hello"

    def test_appends_to_created_list(self, tmp_path: Path) -> None:
        target = tmp_path
        created: list[tuple[str, str]] = []
        dest = tmp_path / "output.txt"
        _write(dest, "content", "my-label", created, target=target, overwrite=False)
        assert len(created) == 1
        assert created[0] == ("output.txt", "my-label")

    def test_skips_if_exists_and_no_overwrite(self, tmp_path: Path) -> None:
        target = tmp_path
        created: list[tuple[str, str]] = []
        dest = tmp_path / "output.txt"
        dest.write_text("original", encoding="utf-8")
        _write(dest, "new-content", "label", created, target=target, overwrite=False)
        assert dest.read_text(encoding="utf-8") == "original"
        assert created == []

    def test_overwrites_if_flag_set(self, tmp_path: Path) -> None:
        target = tmp_path
        created: list[tuple[str, str]] = []
        dest = tmp_path / "output.txt"
        dest.write_text("original", encoding="utf-8")
        _write(dest, "new-content", "label", created, target=target, overwrite=True)
        assert dest.read_text(encoding="utf-8") == "new-content"
        assert len(created) == 1

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        target = tmp_path
        created: list[tuple[str, str]] = []
        dest = tmp_path / "a" / "b" / "c" / "file.txt"
        _write(dest, "content", "label", created, target=target, overwrite=False)
        assert dest.exists()

    def test_relative_path_in_created_list(self, tmp_path: Path) -> None:
        target = tmp_path
        created: list[tuple[str, str]] = []
        dest = tmp_path / "sub" / "file.txt"
        _write(dest, "content", "label", created, target=target, overwrite=False)
        assert created[0][0] == "sub/file.txt"

    def test_empty_content_creates_file(self, tmp_path: Path) -> None:
        target = tmp_path
        created: list[tuple[str, str]] = []
        dest = tmp_path / "empty.txt"
        _write(dest, "", "label", created, target=target, overwrite=False)
        assert dest.exists()
        assert dest.read_text(encoding="utf-8") == ""

    def test_overwrite_on_nonexistent_file_creates_it(self, tmp_path: Path) -> None:
        target = tmp_path
        created: list[tuple[str, str]] = []
        dest = tmp_path / "new.txt"
        _write(dest, "content", "label", created, target=target, overwrite=True)
        assert dest.exists()
        assert len(created) == 1


# ---------------------------------------------------------------------------
# _copy_template() helper
# ---------------------------------------------------------------------------


class TestCopyTemplateHelper:
    def test_copies_content_from_src(self, tmp_path: Path) -> None:
        src = tmp_path / "src.txt"
        src.write_text("template body", encoding="utf-8")
        dest = tmp_path / "output" / "dest.txt"
        target = tmp_path
        created: list[tuple[str, str]] = []
        _copy_template(src, dest, "label", created, target=target, overwrite=False)
        assert dest.read_text(encoding="utf-8") == "template body"

    def test_appends_to_created_list(self, tmp_path: Path) -> None:
        src = tmp_path / "tpl.txt"
        src.write_text("content", encoding="utf-8")
        dest = tmp_path / "out" / "tpl.txt"
        target = tmp_path
        created: list[tuple[str, str]] = []
        _copy_template(src, dest, "my-label", created, target=target, overwrite=False)
        assert len(created) == 1
        assert created[0][1] == "my-label"

    def test_skips_if_dest_exists_and_no_overwrite(self, tmp_path: Path) -> None:
        src = tmp_path / "src.txt"
        src.write_text("new content", encoding="utf-8")
        dest = tmp_path / "dest.txt"
        dest.write_text("original", encoding="utf-8")
        target = tmp_path
        created: list[tuple[str, str]] = []
        _copy_template(src, dest, "label", created, target=target, overwrite=False)
        assert dest.read_text(encoding="utf-8") == "original"
        assert created == []

    def test_overwrites_dest_when_flag_set(self, tmp_path: Path) -> None:
        src = tmp_path / "src.txt"
        src.write_text("new content", encoding="utf-8")
        dest = tmp_path / "dest.txt"
        dest.write_text("original", encoding="utf-8")
        target = tmp_path
        created: list[tuple[str, str]] = []
        _copy_template(src, dest, "label", created, target=target, overwrite=True)
        assert dest.read_text(encoding="utf-8") == "new content"
        assert len(created) == 1

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        src = tmp_path / "src.txt"
        src.write_text("content", encoding="utf-8")
        dest = tmp_path / "deep" / "nested" / "dest.txt"
        target = tmp_path
        created: list[tuple[str, str]] = []
        _copy_template(src, dest, "label", created, target=target, overwrite=False)
        assert dest.exists()

    def test_relative_path_stored_in_created(self, tmp_path: Path) -> None:
        src = tmp_path / "src.txt"
        src.write_text("content", encoding="utf-8")
        dest = tmp_path / "subdir" / "out.txt"
        target = tmp_path
        created: list[tuple[str, str]] = []
        _copy_template(src, dest, "label", created, target=target, overwrite=False)
        assert created[0][0] == "subdir/out.txt"


# ---------------------------------------------------------------------------
# init_command — directory creation
# ---------------------------------------------------------------------------


class TestInitCommandDirectoryCreation:
    def test_creates_flows_directory(self, tmp_path: Path) -> None:
        _run_init(tmp_path / "proj")
        assert (tmp_path / "proj" / "flows").is_dir()

    def test_creates_tests_directory(self, tmp_path: Path) -> None:
        _run_init(tmp_path / "proj")
        assert (tmp_path / "proj" / "tests").is_dir()

    def test_creates_lfx_directory(self, tmp_path: Path) -> None:
        _run_init(tmp_path / "proj")
        assert (tmp_path / "proj" / ".lfx").is_dir()

    def test_creates_project_dir_if_missing(self, tmp_path: Path) -> None:
        target = tmp_path / "brand-new-project"
        assert not target.exists()
        _run_init(target)
        assert target.is_dir()

    def test_creates_nested_project_dir(self, tmp_path: Path) -> None:
        target = tmp_path / "a" / "b" / "c"
        _run_init(target)
        assert target.is_dir()


# ---------------------------------------------------------------------------
# init_command — required files created
# ---------------------------------------------------------------------------


class TestInitCommandRequiredFiles:
    def test_creates_tests_init_py(self, tmp_path: Path) -> None:
        _run_init(tmp_path)
        assert (tmp_path / "tests" / "__init__.py").exists()

    def test_creates_tests_test_flows_py(self, tmp_path: Path) -> None:
        _run_init(tmp_path)
        assert (tmp_path / "tests" / "test_flows.py").exists()

    def test_test_flows_py_has_expected_content(self, tmp_path: Path) -> None:
        _run_init(tmp_path)
        content = (tmp_path / "tests" / "test_flows.py").read_text(encoding="utf-8")
        assert "flow_runner" in content
        assert "pytest.mark.integration" in content

    def test_test_flows_py_content_matches_template(self, tmp_path: Path) -> None:
        _run_init(tmp_path)
        content = (tmp_path / "tests" / "test_flows.py").read_text(encoding="utf-8")
        assert content == _TEST_FLOWS_PY

    def test_creates_environments_yaml(self, tmp_path: Path) -> None:
        _run_init(tmp_path)
        assert (tmp_path / ".lfx" / "environments.yaml").exists()

    def test_environments_yaml_has_expected_content(self, tmp_path: Path) -> None:
        _run_init(tmp_path)
        content = (tmp_path / ".lfx" / "environments.yaml").read_text(encoding="utf-8")
        assert "environments:" in content
        assert "local:" in content
        assert "staging:" in content
        assert "production:" in content

    def test_environments_yaml_content_matches_template(self, tmp_path: Path) -> None:
        _run_init(tmp_path)
        content = (tmp_path / ".lfx" / "environments.yaml").read_text(encoding="utf-8")
        assert content == _ENVIRONMENTS_YAML

    def test_creates_gitignore(self, tmp_path: Path) -> None:
        _run_init(tmp_path)
        assert (tmp_path / ".gitignore").exists()

    def test_gitignore_has_langflow_entry(self, tmp_path: Path) -> None:
        _run_init(tmp_path)
        content = (tmp_path / ".gitignore").read_text(encoding="utf-8")
        assert "langflow-environments.toml" in content


# ---------------------------------------------------------------------------
# init_command — .gitignore behaviour
# ---------------------------------------------------------------------------


class TestInitCommandGitignore:
    def test_creates_new_gitignore_if_missing(self, tmp_path: Path) -> None:
        assert not (tmp_path / ".gitignore").exists()
        _run_init(tmp_path)
        assert (tmp_path / ".gitignore").exists()

    def test_new_gitignore_content_matches_template(self, tmp_path: Path) -> None:
        _run_init(tmp_path)
        content = (tmp_path / ".gitignore").read_text(encoding="utf-8")
        assert content == _GITIGNORE

    def test_appends_rule_to_existing_gitignore_without_entry(self, tmp_path: Path) -> None:
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("*.pyc\n__pycache__/\n", encoding="utf-8")
        # Directory already has .gitignore so use overwrite=True to bypass the non-empty guard
        init_command(project_dir=tmp_path, github_actions=False, overwrite=True, example=False)
        content = gitignore.read_text(encoding="utf-8")
        assert "*.pyc" in content
        assert "__pycache__/" in content
        assert "langflow-environments.toml" in content

    def test_does_not_append_duplicate_rule(self, tmp_path: Path) -> None:
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("langflow-environments.toml\n", encoding="utf-8")
        # Directory already has .gitignore so use overwrite=True to bypass the non-empty guard
        init_command(project_dir=tmp_path, github_actions=False, overwrite=True, example=False)
        content = gitignore.read_text(encoding="utf-8")
        # Should appear exactly once
        assert content.count("langflow-environments.toml") == 1

    def test_existing_gitignore_preserved_and_appended(self, tmp_path: Path) -> None:
        gitignore = tmp_path / ".gitignore"
        original = "node_modules/\ndist/\n"
        gitignore.write_text(original, encoding="utf-8")
        # Directory already has .gitignore so use overwrite=True to bypass the non-empty guard
        init_command(project_dir=tmp_path, github_actions=False, overwrite=True, example=False)
        content = gitignore.read_text(encoding="utf-8")
        # Original content is kept
        assert "node_modules/" in content
        assert "dist/" in content
        # Rule is appended
        assert "langflow-environments.toml" in content

    def test_append_uses_double_newline_separator(self, tmp_path: Path) -> None:
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("*.pyc\n", encoding="utf-8")
        # Directory already has .gitignore so use overwrite=True to bypass the non-empty guard
        init_command(project_dir=tmp_path, github_actions=False, overwrite=True, example=False)
        content = gitignore.read_text(encoding="utf-8")
        # The separator between existing content and appended block should be \n\n
        assert "\n\n" in content


# ---------------------------------------------------------------------------
# init_command — example=True (with seeded hello-world flow)
# ---------------------------------------------------------------------------


class TestInitCommandExampleTrue:
    def test_creates_hello_world_json(self, tmp_path: Path) -> None:
        init_command(project_dir=tmp_path, github_actions=False, overwrite=False, example=True)
        assert (tmp_path / "flows" / "hello-world.json").exists()

    def test_hello_world_is_valid_json(self, tmp_path: Path) -> None:
        import json

        init_command(project_dir=tmp_path, github_actions=False, overwrite=False, example=True)
        content = (tmp_path / "flows" / "hello-world.json").read_text(encoding="utf-8")
        flow = json.loads(content)
        assert isinstance(flow, dict)

    def test_hello_world_has_id_and_name(self, tmp_path: Path) -> None:
        import json

        init_command(project_dir=tmp_path, github_actions=False, overwrite=False, example=True)
        flow = json.loads((tmp_path / "flows" / "hello-world.json").read_text(encoding="utf-8"))
        assert "id" in flow
        assert "name" in flow
        assert flow["name"] == "hello-world"

    def test_no_gitkeep_when_example_is_true(self, tmp_path: Path) -> None:
        init_command(project_dir=tmp_path, github_actions=False, overwrite=False, example=True)
        assert not (tmp_path / "flows" / ".gitkeep").exists()

    def test_other_files_still_created_with_example(self, tmp_path: Path) -> None:
        init_command(project_dir=tmp_path, github_actions=False, overwrite=False, example=True)
        assert (tmp_path / ".lfx" / "environments.yaml").exists()
        assert (tmp_path / "tests" / "test_flows.py").exists()
        assert (tmp_path / "tests" / "__init__.py").exists()

    def test_graceful_fallback_when_template_missing(self, tmp_path: Path) -> None:
        """If create_command raises, init should warn but continue scaffolding."""
        fake_dir = tmp_path / "no-templates"
        with patch("lfx.cli.create._FLOWS_TEMPLATE_DIR", fake_dir):
            # Should not raise — BLE001-guarded except swallows the failure
            init_command(
                project_dir=tmp_path / "proj",
                github_actions=False,
                overwrite=False,
                example=True,
            )
        assert (tmp_path / "proj" / ".lfx" / "environments.yaml").exists()


# ---------------------------------------------------------------------------
# init_command — example=False (with .gitkeep)
# ---------------------------------------------------------------------------


class TestInitCommandExampleFalse:
    def test_creates_gitkeep_in_flows(self, tmp_path: Path) -> None:
        _run_init(tmp_path, example=False)
        assert (tmp_path / "flows" / ".gitkeep").exists()

    def test_no_hello_world_when_example_false(self, tmp_path: Path) -> None:
        _run_init(tmp_path, example=False)
        assert not (tmp_path / "flows" / "hello-world.json").exists()

    def test_gitkeep_is_empty_file(self, tmp_path: Path) -> None:
        _run_init(tmp_path, example=False)
        assert (tmp_path / "flows" / ".gitkeep").read_text(encoding="utf-8") == ""

    def test_other_files_still_created_without_example(self, tmp_path: Path) -> None:
        _run_init(tmp_path, example=False)
        assert (tmp_path / ".lfx" / "environments.yaml").exists()
        assert (tmp_path / "tests" / "test_flows.py").exists()
        assert (tmp_path / "tests" / "__init__.py").exists()
        assert (tmp_path / ".gitignore").exists()


# ---------------------------------------------------------------------------
# init_command — GitHub Actions templates
# ---------------------------------------------------------------------------


class TestInitCommandGitHubActions:
    def test_creates_github_workflows_dir_when_gha_true(self, tmp_path: Path) -> None:
        if not _GHA_SRC.exists():
            pytest.skip("GitHub Actions templates not bundled")
        init_command(project_dir=tmp_path, github_actions=True, overwrite=False, example=False)
        assert (tmp_path / ".github" / "workflows").is_dir()

    def test_copies_all_yml_templates(self, tmp_path: Path) -> None:
        if not _GHA_SRC.exists():
            pytest.skip("GitHub Actions templates not bundled")
        expected = sorted(t.name for t in _GHA_SRC.glob("*.yml"))
        init_command(project_dir=tmp_path, github_actions=True, overwrite=False, example=False)
        created = sorted(p.name for p in (tmp_path / ".github" / "workflows").glob("*.yml"))
        assert created == expected

    def test_workflow_files_are_non_empty(self, tmp_path: Path) -> None:
        if not _GHA_SRC.exists():
            pytest.skip("GitHub Actions templates not bundled")
        init_command(project_dir=tmp_path, github_actions=True, overwrite=False, example=False)
        for yml in (tmp_path / ".github" / "workflows").glob("*.yml"):
            assert yml.stat().st_size > 0, f"{yml.name} should not be empty"

    def test_workflow_file_content_matches_template(self, tmp_path: Path) -> None:
        if not _GHA_SRC.exists():
            pytest.skip("GitHub Actions templates not bundled")
        init_command(project_dir=tmp_path, github_actions=True, overwrite=False, example=False)
        for src_tmpl in _GHA_SRC.glob("*.yml"):
            dest = tmp_path / ".github" / "workflows" / src_tmpl.name
            assert dest.read_text(encoding="utf-8") == src_tmpl.read_text(encoding="utf-8")

    def test_skips_github_workflows_when_gha_false(self, tmp_path: Path) -> None:
        init_command(project_dir=tmp_path, github_actions=False, overwrite=False, example=False)
        assert not (tmp_path / ".github").exists()

    def test_warns_when_gha_templates_dir_missing(self, tmp_path: Path) -> None:
        """When the template directory is absent a warning is printed but no error raised."""
        missing_templates = tmp_path / "no-such-templates"
        with patch("lfx.cli.init._TEMPLATES_DIR", missing_templates):
            # Should not raise
            init_command(project_dir=tmp_path / "proj", github_actions=True, overwrite=False, example=False)
        # The project's other files should still be scaffolded
        assert (tmp_path / "proj" / ".lfx" / "environments.yaml").exists()


# ---------------------------------------------------------------------------
# init_command — shell CI scripts (always scaffolded)
# ---------------------------------------------------------------------------


class TestInitCommandShellScripts:
    def test_creates_ci_directory(self, tmp_path: Path) -> None:
        if not _SHELL_SRC.exists():
            pytest.skip("Shell templates not bundled")
        _run_init(tmp_path)
        assert (tmp_path / "ci").is_dir()

    def test_copies_all_sh_templates(self, tmp_path: Path) -> None:
        if not _SHELL_SRC.exists():
            pytest.skip("Shell templates not bundled")
        expected = sorted(t.name for t in _SHELL_SRC.glob("*.sh"))
        _run_init(tmp_path)
        created = sorted(p.name for p in (tmp_path / "ci").glob("*.sh"))
        assert created == expected

    def test_shell_scripts_are_executable(self, tmp_path: Path) -> None:
        if not _SHELL_SRC.exists():
            pytest.skip("Shell templates not bundled")
        _run_init(tmp_path)
        import stat

        for script in (tmp_path / "ci").glob("*.sh"):
            mode = script.stat().st_mode
            assert mode & stat.S_IXUSR, f"{script.name} should have executable bit set"

    def test_shell_script_content_matches_template(self, tmp_path: Path) -> None:
        if not _SHELL_SRC.exists():
            pytest.skip("Shell templates not bundled")
        _run_init(tmp_path)
        for src_tmpl in _SHELL_SRC.glob("*.sh"):
            dest = tmp_path / "ci" / src_tmpl.name
            assert dest.read_text(encoding="utf-8") == src_tmpl.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# init_command — non-empty directory guard
# ---------------------------------------------------------------------------


class TestInitCommandNonEmptyGuard:
    def test_exits_with_code_1_on_non_empty_dir_without_overwrite(self, tmp_path: Path) -> None:
        (tmp_path / "existing.txt").write_text("data", encoding="utf-8")
        with pytest.raises(typer.Exit) as exc_info:
            init_command(project_dir=tmp_path, github_actions=False, overwrite=False, example=False)
        assert exc_info.value.exit_code == 1

    def test_empty_dir_does_not_raise(self, tmp_path: Path) -> None:
        target = tmp_path / "empty"
        target.mkdir()
        # Should not raise
        init_command(project_dir=target, github_actions=False, overwrite=False, example=False)

    def test_nonexistent_dir_does_not_raise(self, tmp_path: Path) -> None:
        target = tmp_path / "brand-new"
        # Should not raise
        init_command(project_dir=target, github_actions=False, overwrite=False, example=False)

    def test_git_dir_only_is_not_considered_non_empty(self, tmp_path: Path) -> None:
        """A directory containing only .git is treated as empty by the guard."""
        (tmp_path / ".git").mkdir()
        # Should not raise — .git is excluded from the check
        init_command(project_dir=tmp_path, github_actions=False, overwrite=False, example=False)

    def test_overwrite_succeeds_on_non_empty_dir(self, tmp_path: Path) -> None:
        (tmp_path / "existing.txt").write_text("data", encoding="utf-8")
        # Should not raise
        init_command(project_dir=tmp_path, github_actions=False, overwrite=True, example=False)
        assert (tmp_path / ".lfx" / "environments.yaml").exists()


# ---------------------------------------------------------------------------
# init_command — --overwrite re-creates files
# ---------------------------------------------------------------------------


class TestInitCommandOverwrite:
    def test_overwrite_replaces_environments_yaml(self, tmp_path: Path) -> None:
        env_yaml = tmp_path / ".lfx" / "environments.yaml"
        env_yaml.parent.mkdir(parents=True)
        env_yaml.write_text("# old content\n", encoding="utf-8")
        init_command(project_dir=tmp_path, github_actions=False, overwrite=True, example=False)
        content = env_yaml.read_text(encoding="utf-8")
        assert content == _ENVIRONMENTS_YAML

    def test_overwrite_replaces_test_flows_py(self, tmp_path: Path) -> None:
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir(parents=True)
        test_file = tests_dir / "test_flows.py"
        test_file.write_text("# old tests\n", encoding="utf-8")
        init_command(project_dir=tmp_path, github_actions=False, overwrite=True, example=False)
        content = test_file.read_text(encoding="utf-8")
        assert content == _TEST_FLOWS_PY

    def test_no_overwrite_preserves_environments_yaml(self, tmp_path: Path) -> None:
        """_write skips existing files when overwrite=False (tested via the helper directly)."""
        target = tmp_path
        created: list[tuple[str, str]] = []
        dest = tmp_path / ".lfx" / "environments.yaml"
        dest.parent.mkdir(parents=True)
        dest.write_text("# custom content\n", encoding="utf-8")
        _write(dest, _ENVIRONMENTS_YAML, "label", created, target=target, overwrite=False)
        # Original content must be preserved
        assert dest.read_text(encoding="utf-8") == "# custom content\n"
        assert created == []

    def test_overwrite_with_github_actions_replaces_workflows(self, tmp_path: Path) -> None:
        if not _GHA_SRC.exists():
            pytest.skip("GitHub Actions templates not bundled")
        # First init
        init_command(project_dir=tmp_path, github_actions=True, overwrite=False, example=False)
        # Corrupt one workflow file
        wf_dir = tmp_path / ".github" / "workflows"
        first_wf = next(wf_dir.glob("*.yml"))
        first_wf.write_text("# corrupted\n", encoding="utf-8")
        # Overwrite init
        init_command(project_dir=tmp_path, github_actions=True, overwrite=True, example=False)
        # Content should be restored from template
        src_content = (_GHA_SRC / first_wf.name).read_text(encoding="utf-8")
        assert first_wf.read_text(encoding="utf-8") == src_content


# ---------------------------------------------------------------------------
# CLI wrapper via typer CliRunner
# ---------------------------------------------------------------------------


class TestInitCLI:
    def test_basic_init_exits_zero(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["init", str(tmp_path / "proj")])
        assert result.exit_code == 0, result.output

    def test_basic_init_creates_environments_yaml(self, tmp_path: Path) -> None:
        proj = tmp_path / "proj"
        result = runner.invoke(app, ["init", str(proj)])
        assert result.exit_code == 0, result.output
        assert (proj / ".lfx" / "environments.yaml").exists()

    def test_basic_init_creates_test_flows_py(self, tmp_path: Path) -> None:
        proj = tmp_path / "proj"
        result = runner.invoke(app, ["init", str(proj)])
        assert result.exit_code == 0, result.output
        assert (proj / "tests" / "test_flows.py").exists()

    def test_no_github_actions_flag(self, tmp_path: Path) -> None:
        proj = tmp_path / "proj"
        result = runner.invoke(app, ["init", str(proj), "--no-github-actions"])
        assert result.exit_code == 0, result.output
        assert not (proj / ".github").exists()

    def test_github_actions_flag_creates_workflows(self, tmp_path: Path) -> None:
        if not _GHA_SRC.exists():
            pytest.skip("GitHub Actions templates not bundled")
        proj = tmp_path / "proj"
        result = runner.invoke(app, ["init", str(proj), "--github-actions"])
        assert result.exit_code == 0, result.output
        assert (proj / ".github" / "workflows").is_dir()

    def test_no_example_flag_creates_gitkeep(self, tmp_path: Path) -> None:
        proj = tmp_path / "proj"
        result = runner.invoke(app, ["init", str(proj), "--no-github-actions", "--no-example"])
        assert result.exit_code == 0, result.output
        assert (proj / "flows" / ".gitkeep").exists()
        assert not (proj / "flows" / "hello-world.json").exists()

    def test_example_flag_creates_hello_world(self, tmp_path: Path) -> None:
        proj = tmp_path / "proj"
        result = runner.invoke(app, ["init", str(proj), "--no-github-actions", "--example"])
        assert result.exit_code == 0, result.output
        assert (proj / "flows" / "hello-world.json").exists()

    def test_overwrite_flag_reinitialises_non_empty_dir(self, tmp_path: Path) -> None:
        proj = tmp_path / "proj"
        proj.mkdir()
        (proj / "some-file.txt").write_text("existing", encoding="utf-8")
        result = runner.invoke(app, ["init", str(proj), "--no-github-actions", "--no-example", "--overwrite"])
        assert result.exit_code == 0, result.output
        assert (proj / ".lfx" / "environments.yaml").exists()

    def test_non_empty_dir_without_overwrite_exits_nonzero(self, tmp_path: Path) -> None:
        proj = tmp_path / "proj"
        proj.mkdir()
        (proj / "some-file.txt").write_text("existing", encoding="utf-8")
        result = runner.invoke(app, ["init", str(proj), "--no-github-actions"])
        assert result.exit_code != 0

    def test_default_project_dir_is_current_directory(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """When no project_dir argument is given the CLI defaults to '.'."""
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["init", "--no-github-actions", "--no-example"])
        assert result.exit_code == 0, result.output
        assert (tmp_path / ".lfx" / "environments.yaml").exists()

    def test_init_output_mentions_next_steps(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["init", str(tmp_path / "proj"), "--no-github-actions"])
        assert result.exit_code == 0, result.output
        assert "Next steps" in result.output
