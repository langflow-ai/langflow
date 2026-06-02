"""End-to-end CLI tests for ``lfx extension list``.

The list command reads from the live importlib metadata + the
seed-directory environment.  We override the seed directory through the
``--seed-dir`` flag and avoid touching ``importlib.metadata`` because the
unit tests for :mod:`lfx.extension.discovery` already exercise the
installed-distribution scan with a fake iterator.

A separate end-to-end suite (``test_e2e_install.py``) builds real wheels
and invokes ``pip install`` to cover the genuine production install
path.  This file pins the CLI surface contract; the e2e suite pins the
distribution-discovery contract.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from lfx.__main__ import app
from typer.testing import CliRunner

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def runner() -> CliRunner:
    try:
        return CliRunner(mix_stderr=False)  # type: ignore[call-arg]
    except TypeError:
        return CliRunner()


def _manifest(extension_id: str, bundle_name: str, version: str = "1.0.0") -> dict[str, object]:
    return {
        "id": extension_id,
        "version": version,
        "name": f"{extension_id} bundle",
        "lfx": {"compat": ["1"]},
        "bundles": [{"name": bundle_name, "path": bundle_name}],
    }


def _seed_subdir(seed_root: Path, extension_id: str, bundle_name: str, version: str = "1.0.0") -> None:
    sub = seed_root / extension_id.replace("-", "_")
    sub.mkdir(parents=True, exist_ok=True)
    (sub / bundle_name).mkdir(exist_ok=True)
    (sub / "extension.json").write_text(
        json.dumps(_manifest(extension_id, bundle_name, version)),
        encoding="utf-8",
    )


def test_list_text_output_with_three_seed_bundles(runner: CliRunner, tmp_path: Path) -> None:
    """Acceptance: three seed bundles all show at @official."""
    seed = tmp_path / "seed"
    seed.mkdir()
    for index, bundle in enumerate(("openai", "anthropic", "qdrant")):
        _seed_subdir(seed, f"lfx-{bundle}", bundle, version=f"1.{index}.0")

    result = runner.invoke(app, ["extension", "list", "--seed-dir", str(seed)])

    assert result.exit_code == 0, result.stderr
    stdout = result.stdout
    # Header is present.
    assert "ID" in stdout
    assert "VERSION" in stdout
    assert "BUNDLE" in stdout
    assert "SLOT" in stdout
    # All three Extensions render at @official.
    for bundle in ("lfx-openai", "lfx-anthropic", "lfx-qdrant"):
        assert bundle in stdout
    assert stdout.count("@official") >= 3


def test_list_json_output_with_three_seed_bundles(runner: CliRunner, tmp_path: Path) -> None:
    seed = tmp_path / "seed"
    seed.mkdir()
    for bundle in ("openai", "anthropic", "qdrant"):
        _seed_subdir(seed, f"lfx-{bundle}", bundle)

    result = runner.invoke(app, ["extension", "list", "--seed-dir", str(seed), "--format", "json"])

    assert result.exit_code == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["errors"] == []
    ids = sorted(ext["id"] for ext in payload["extensions"])
    assert ids == ["lfx-anthropic", "lfx-openai", "lfx-qdrant"]
    for ext in payload["extensions"]:
        assert ext["slot"] == "@official"
        assert ext["source_kind"] == "seed"
        assert ext["auto_update"] is False
        assert ext["load_status"] == "discovered"


def test_list_empty_when_no_extensions(runner: CliRunner, tmp_path: Path) -> None:
    """An empty seed dir + no installed Extensions emits a helpful message.

    Note: The current process may have other distributions on the path;
    we cannot fully isolate ``importlib.metadata.distributions()``
    without monkeypatching, which the CLI surface intentionally does not
    expose.  We use ``--seed-dir`` to point at an empty directory and
    accept that some pre-existing site-packages distributions may show
    up; we only check that the seed pass produced nothing.
    """
    empty = tmp_path / "empty_seed"
    empty.mkdir()
    result = runner.invoke(app, ["extension", "list", "--seed-dir", str(empty), "--format", "json"])
    assert result.exit_code == 0, result.stderr
    payload = json.loads(result.stdout)
    # The seed pass yielded zero entries.
    assert all(ext["source_kind"] != "seed" for ext in payload["extensions"])


def test_list_reports_seed_directory_not_found(runner: CliRunner, tmp_path: Path) -> None:
    """Configured but missing seed dir produces a typed error and non-zero exit."""
    missing = tmp_path / "does_not_exist"

    result = runner.invoke(app, ["extension", "list", "--seed-dir", str(missing)])
    assert result.exit_code == 1
    assert "seed-directory-not-found" in result.stderr


def test_list_reports_malformed_manifest(runner: CliRunner, tmp_path: Path) -> None:
    """A malformed seed-directory manifest surfaces ``manifest-invalid``."""
    seed = tmp_path / "seed"
    bad = seed / "lfx_broken"
    bad.mkdir(parents=True)
    (bad / "extension.json").write_text("{ not json", encoding="utf-8")
    # Healthy neighbour to confirm partial output still works.
    _seed_subdir(seed, "lfx-openai", "openai")

    result = runner.invoke(app, ["extension", "list", "--seed-dir", str(seed)])
    assert result.exit_code == 1
    assert "lfx-openai" in result.stdout
    assert "manifest-invalid" in result.stderr


def test_list_rejects_invalid_format(runner: CliRunner, tmp_path: Path) -> None:
    result = runner.invoke(app, ["extension", "list", "--seed-dir", str(tmp_path), "--format", "yaml"])
    assert result.exit_code == 2
    assert "Invalid --format" in result.stderr


def test_list_appears_in_extension_help(runner: CliRunner) -> None:
    result = runner.invoke(app, ["extension", "--help"])
    assert result.exit_code == 0
    assert "list" in result.stdout


def test_list_text_output_includes_interpreter_info(runner: CliRunner, tmp_path: Path) -> None:
    """Operators hit the wrong-venv footgun when ``lfx`` and ``langflow run`` diverge.

    Printing the interpreter at the top of the listing turns "my bundle didn't
    install" into a one-glance fix.
    """
    import sys

    seed = tmp_path / "seed"
    seed.mkdir()
    _seed_subdir(seed, "lfx-openai", "openai")

    result = runner.invoke(app, ["extension", "list", "--seed-dir", str(seed)])
    assert result.exit_code == 0, result.stderr
    assert "python:" in result.stdout
    assert sys.executable in result.stdout
    assert "sys.prefix:" in result.stdout


def test_list_json_output_includes_interpreter_info(runner: CliRunner, tmp_path: Path) -> None:
    import sys

    empty = tmp_path / "empty_seed"
    empty.mkdir()
    result = runner.invoke(app, ["extension", "list", "--seed-dir", str(empty), "--format", "json"])
    assert result.exit_code == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["interpreter"]["executable"] == sys.executable
    assert payload["interpreter"]["prefix"] == sys.prefix


def test_list_exits_zero_when_only_warning_is_seed_bundle_shadowed(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``seed-bundle-shadowed`` is a warning, not a discovery failure.

    Any CI script doing ``lfx extension list && ...`` would otherwise break
    the moment an operator pip-installs a bundle that also ships in a seed
    directory.  The warning still appears on stderr; the exit code stays 0.
    """
    from lfx.extension.errors import ExtensionError

    seed = tmp_path / "seed"
    seed.mkdir()
    _seed_subdir(seed, "lfx-openai", "openai")

    real_discover_all = __import__("lfx.extension", fromlist=["discover_all_extensions"]).discover_all_extensions

    def _shadowed_discovery(seed_dir_env: str | None = None):
        extensions, errors = real_discover_all(seed_dir_env=seed_dir_env)
        errors = [
            *errors,
            ExtensionError(
                code="seed-bundle-shadowed",
                message="seed bundle 'openai' is shadowed by an installed Extension of the same name",
                location=str(seed / "lfx_openai"),
                content="openai",
                hint="remove the seed copy or uninstall the pip distribution",
            ),
        ]
        return extensions, errors

    # The CLI command imports ``discover_all_extensions`` from ``lfx.extension``
    # at call time, so patching that name suffices.
    monkeypatch.setattr("lfx.extension.discover_all_extensions", _shadowed_discovery)

    result = runner.invoke(app, ["extension", "list", "--seed-dir", str(seed)])
    assert result.exit_code == 0, result.stderr
    assert "seed-bundle-shadowed" in result.stderr
