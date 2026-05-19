"""End-to-end CLI tests for ``lfx extension validate`` and ``lfx extension schema``."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from lfx.__main__ import app
from typer.testing import CliRunner

if TYPE_CHECKING:
    from pathlib import Path

_BASE_MANIFEST = {
    "id": "lfx-openai",
    "version": "1.2.3",
    "name": "OpenAI Bundle",
    "lfx": {"compat": ["1"]},
    "bundles": [{"name": "openai", "path": "openai"}],
}


_COMPONENT_SRC = (
    "class Component:\n"
    "    pass\n"
    "\n"
    "class OpenAIThing(Component):\n"
    "    display_name = 'X'\n"
    "    def build(self):\n"
    "        return None\n"
)


@pytest.fixture
def runner() -> CliRunner:
    # ``mix_stderr=False`` is the historical signature; newer click versions
    # emit a deprecation and changed the default behavior.  We accept either.
    try:
        return CliRunner(mix_stderr=False)  # type: ignore[call-arg]
    except TypeError:
        return CliRunner()


@pytest.fixture
def good_extension(tmp_path: Path) -> Path:
    (tmp_path / "extension.json").write_text(json.dumps(_BASE_MANIFEST), encoding="utf-8")
    bundle = tmp_path / "openai"
    bundle.mkdir()
    (bundle / "text.py").write_text(_COMPONENT_SRC, encoding="utf-8")
    return tmp_path


def test_validate_returns_zero_on_success(runner: CliRunner, good_extension: Path) -> None:
    result = runner.invoke(app, ["extension", "validate", str(good_extension)])
    assert result.exit_code == 0
    assert "ok" in result.stdout.lower()


def test_validate_returns_nonzero_on_failure(runner: CliRunner, tmp_path: Path) -> None:
    result = runner.invoke(app, ["extension", "validate", str(tmp_path)])
    assert result.exit_code == 1
    # Errors render to stderr per the design.
    assert "manifest-not-found" in result.stderr


def test_validate_json_output(runner: CliRunner, good_extension: Path) -> None:
    result = runner.invoke(app, ["extension", "validate", str(good_extension), "--format", "json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["manifest"]["id"] == "lfx-openai"
    assert payload["bundle_files_scanned"] == 1
    assert payload["errors"] == []


def test_validate_json_output_failure(runner: CliRunner, tmp_path: Path) -> None:
    result = runner.invoke(app, ["extension", "validate", str(tmp_path), "--format", "json"])
    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert any(e["code"] == "manifest-not-found" for e in payload["errors"])


def test_schema_command_writes_to_stdout(runner: CliRunner) -> None:
    result = runner.invoke(app, ["extension", "schema"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["$id"].endswith("/extension/v1.json")


def test_schema_command_writes_to_file(runner: CliRunner, tmp_path: Path) -> None:
    out = tmp_path / "schema.json"
    result = runner.invoke(app, ["extension", "schema", "-o", str(out)])
    assert result.exit_code == 0
    assert out.exists()
    parsed = json.loads(out.read_text(encoding="utf-8"))
    assert parsed["$id"].endswith("/extension/v1.json")


def test_extension_app_help_smoke(runner: CliRunner) -> None:
    """Ensure the sub-app is mounted and the help renders."""
    result = runner.invoke(app, ["extension", "--help"])
    assert result.exit_code == 0
    assert "validate" in result.stdout
    assert "schema" in result.stdout
    # Authoring commands also appear in help.
    assert "init" in result.stdout
    assert "dev" in result.stdout


# ---------------------------------------------------------------------------
# init
# ---------------------------------------------------------------------------


@pytest.fixture
def isolated_dev_registry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Force the dev registry under a tmp_path subdir so tests don't leak.

    Reused by the ``dev`` command tests below; defined here so the same
    fixture name is available in both sections.
    """
    state_dir = tmp_path / "_dev_state"
    state_dir.mkdir()
    monkeypatch.setenv("LANGFLOW_DEV_EXTENSIONS_DIR", str(state_dir))
    return state_dir


def test_init_then_validate_passes_clean(runner: CliRunner, tmp_path: Path) -> None:
    """AC #1: ``extension init my-ext && extension validate ./my-ext`` is clean."""
    target = tmp_path / "my-ext"
    init_result = runner.invoke(app, ["extension", "init", str(target)])
    assert init_result.exit_code == 0, init_result.stderr or init_result.stdout

    validate_result = runner.invoke(app, ["extension", "validate", str(target)])
    assert validate_result.exit_code == 0, validate_result.stderr or validate_result.stdout
    assert "ok" in validate_result.stdout.lower()


def test_init_full_template_fails_cleanly(runner: CliRunner, tmp_path: Path) -> None:
    """AC #3: ``--template full`` emits typed error and exits non-zero."""
    target = tmp_path / "my-ext"
    result = runner.invoke(app, ["extension", "init", str(target), "--template", "full"])
    assert result.exit_code == 1
    assert "template-deferred-in-this-milestone" in result.stderr
    # Nothing scaffolded.
    assert not target.exists() or not any(target.iterdir())


def test_init_refuses_existing_non_empty_directory(runner: CliRunner, tmp_path: Path) -> None:
    target = tmp_path / "my-ext"
    target.mkdir()
    (target / "existing.txt").write_text("hi", encoding="utf-8")
    result = runner.invoke(app, ["extension", "init", str(target)])
    assert result.exit_code == 1
    assert "extension-target-exists" in result.stderr
    # Existing file untouched.
    assert (target / "existing.txt").read_text(encoding="utf-8") == "hi"


def test_init_accepts_explicit_id_and_name(runner: CliRunner, tmp_path: Path) -> None:
    target = tmp_path / "anything-here"
    result = runner.invoke(
        app,
        [
            "extension",
            "init",
            str(target),
            "--id",
            "custom-id",
            "--name",
            "My Custom Extension",
        ],
    )
    assert result.exit_code == 0, result.stderr or result.stdout
    payload = json.loads((target / "extension.json").read_text(encoding="utf-8"))
    assert payload["id"] == "custom-id"
    assert payload["name"] == "My Custom Extension"


# ---------------------------------------------------------------------------
# dev
# ---------------------------------------------------------------------------


def _scaffold_via_cli(runner: CliRunner, tmp_path: Path, name: str = "my-ext") -> Path:
    target = tmp_path / name
    result = runner.invoke(app, ["extension", "init", str(target)])
    assert result.exit_code == 0, result.stderr or result.stdout
    return target


def test_dev_skip_launch_registers_extension(
    runner: CliRunner,
    tmp_path: Path,
    isolated_dev_registry: Path,
) -> None:
    """``extension dev --skip-launch`` registers the path and exits cleanly."""
    target = _scaffold_via_cli(runner, tmp_path)
    result = runner.invoke(app, ["extension", "dev", str(target), "--skip-launch"])
    assert result.exit_code == 0, result.stderr or result.stdout
    assert "Registered dev extension" in result.stdout
    # State file written under the isolated dir.
    state_file = isolated_dev_registry / "dev_extensions.json"
    assert state_file.is_file()
    payload = json.loads(state_file.read_text(encoding="utf-8"))
    assert payload["extensions"][0]["path"] == str(target.resolve())


def test_dev_aborts_on_invalid_extension(
    runner: CliRunner,
    tmp_path: Path,
    isolated_dev_registry: Path,
) -> None:
    """A directory missing a manifest is rejected before registration."""
    bogus = tmp_path / "bogus"
    bogus.mkdir()
    result = runner.invoke(app, ["extension", "dev", str(bogus), "--skip-launch"])
    assert result.exit_code == 1
    assert "manifest-not-found" in result.stderr
    # Nothing registered.
    state_file = isolated_dev_registry / "dev_extensions.json"
    assert not state_file.is_file() or json.loads(state_file.read_text(encoding="utf-8"))["extensions"] == []


def test_dev_skip_validate_registers_anyway(
    runner: CliRunner,
    tmp_path: Path,
    isolated_dev_registry: Path,
) -> None:
    """``--skip-validate`` lets the author register a known-broken manifest.

    Useful when the author wants to see the loader's runtime error rather
    than the static one; tested here to confirm the flag short-circuits
    the pre-flight pass.
    """
    target = _scaffold_via_cli(runner, tmp_path)
    # Break the manifest so validate would fail.
    (target / "extension.json").write_text("{ not json }", encoding="utf-8")
    result = runner.invoke(app, ["extension", "dev", str(target), "--skip-validate", "--skip-launch"])
    assert result.exit_code == 0, result.stderr or result.stdout
    state_file = isolated_dev_registry / "dev_extensions.json"
    assert state_file.is_file()


@pytest.mark.usefixtures("isolated_dev_registry")
def test_dev_refuses_non_directory(
    runner: CliRunner,
    tmp_path: Path,
) -> None:
    bogus = tmp_path / "not-a-dir"
    bogus.write_text("file", encoding="utf-8")
    result = runner.invoke(app, ["extension", "dev", str(bogus), "--skip-launch"])
    assert result.exit_code == 1
    assert "not a directory" in (result.stderr or result.stdout)


# ---------------------------------------------------------------------------
# dev launch env: contract for the env vars handed to ``langflow run``
# ---------------------------------------------------------------------------


def test_dev_launch_env_enables_reload_and_eager_loading() -> None:
    """The launched langflow inherits flags that make 'edit -> Reload' work.

    Without ``LANGFLOW_ENABLE_EXTENSION_RELOAD=true`` the backend reload
    handler returns 404 (the runtime guard reads
    ``settings.enable_extension_reload``) AND the ``/config`` payload
    reports the flag as off, which keeps the packaged frontend from
    showing the Reload button.  Without ``LANGFLOW_LAZY_LOAD_COMPONENTS=false``
    dev components miss the palette's 5-second budget.
    """
    from lfx.cli._extension_commands import _build_dev_launch_env

    env = _build_dev_launch_env({})

    assert env["LANGFLOW_LAZY_LOAD_COMPONENTS"] == "false"
    assert env["LANGFLOW_ENABLE_EXTENSION_RELOAD"] == "true"


def test_dev_launch_env_overrides_author_lazy_loading() -> None:
    """``LANGFLOW_LAZY_LOAD_COMPONENTS=true`` in the author shell must not win.

    The dev workflow always wants eager loading; an author whose shell
    exports lazy loading for normal langflow use should not silently
    lose dev components from the palette.
    """
    from lfx.cli._extension_commands import _build_dev_launch_env

    env = _build_dev_launch_env({"LANGFLOW_LAZY_LOAD_COMPONENTS": "true"})
    assert env["LANGFLOW_LAZY_LOAD_COMPONENTS"] == "false"


def test_dev_launch_env_respects_author_reload_off_path() -> None:
    """An author testing the off path can pre-export the disable flag.

    The reload flag uses setdefault so an explicit ``=false`` exported
    in the shell survives the helper's defaulting.
    """
    from lfx.cli._extension_commands import _build_dev_launch_env

    env = _build_dev_launch_env({"LANGFLOW_ENABLE_EXTENSION_RELOAD": "false"})
    assert env["LANGFLOW_ENABLE_EXTENSION_RELOAD"] == "false"


# ---------------------------------------------------------------------------
# extension reload -- argument validation
# ---------------------------------------------------------------------------


def test_reload_with_neither_id_nor_all_exits_2(runner: CliRunner) -> None:
    """No positional id AND no ``--all`` is a usage error."""
    result = runner.invoke(app, ["extension", "reload"])
    assert result.exit_code == 2
    msg = result.stderr or result.stdout
    # The error message should mention both alternatives so the user
    # knows what to do next.
    assert "--all" in msg
    assert "extension id" in msg


def test_reload_all_rejects_extra_args(runner: CliRunner) -> None:
    """``--all`` is mutually exclusive with an explicit id / bundle name."""
    result = runner.invoke(app, ["extension", "reload", "--all", "lfx-pilot"])
    assert result.exit_code == 2
    msg = result.stderr or result.stdout
    assert "--all" in msg


def test_reload_id_not_in_local_discovery_errors_clean(runner: CliRunner, monkeypatch: pytest.MonkeyPatch) -> None:
    """Error cleanly when the extension is not locally installed.

    With --bundle omitted, the CLI exits 1 with a typed message rather
    than POSTing with a guessed bundle name.
    """
    # Force discovery to return nothing.
    from lfx.cli import _extension_commands as commands

    monkeypatch.setattr(
        "lfx.extension.discover_all_extensions",
        lambda: ([], []),
    )
    # Defensive: prevent the module-cached reference if any.
    monkeypatch.setattr(
        commands,
        "_post_reload",
        lambda **_kwargs: pytest.fail("should not POST when discovery fails"),
    )
    result = runner.invoke(app, ["extension", "reload", "lfx-not-installed"])
    assert result.exit_code == 1
    msg = result.stderr or result.stdout
    assert "lfx-not-installed" in msg
    assert "--bundle" in msg
