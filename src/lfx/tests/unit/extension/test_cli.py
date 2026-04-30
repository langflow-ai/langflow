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
    "lfx": {"bundle_api": [1]},
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
