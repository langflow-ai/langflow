"""Smoke tests for scripts/migrate/check_bare_names.py.

Exercise the script as a black-box subprocess so the test catches
SystemExit / argparse drift the same way CI would.  Uses a synthetic
components root so we don't depend on the real lfx component tree.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[6]
SCRIPT = REPO_ROOT / "scripts" / "migrate" / "check_bare_names.py"


def _write_table(path: Path, entries: list[dict]) -> None:
    path.write_text(
        json.dumps({"schema_version": 1, "entries": entries}, indent=2),
        encoding="utf-8",
    )


def _make_component(root: Path, bundle: str, filename: str, class_name: str) -> Path:
    bundle_dir = root / bundle
    bundle_dir.mkdir(parents=True, exist_ok=True)
    file_path = bundle_dir / filename
    file_path.write_text(
        f"class {class_name}:\n    pass\n",
        encoding="utf-8",
    )
    return file_path


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 - test harness invoking our own script
        [sys.executable, str(SCRIPT), *args],
        check=False,
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )


@pytest.mark.unit
def test_script_exists() -> None:
    assert SCRIPT.is_file(), f"missing CI guard script at {SCRIPT}"


@pytest.mark.unit
def test_empty_table_passes(tmp_path: Path) -> None:
    table = tmp_path / "table.json"
    _write_table(table, [])
    proc = _run("--table", str(table), "--components-root", str(tmp_path))
    assert proc.returncode == 0, proc.stderr


@pytest.mark.unit
def test_table_without_bare_names_passes(tmp_path: Path) -> None:
    """Entries that only declare import_path or legacy_slot are not bare-name guarded."""
    table = tmp_path / "table.json"
    _write_table(
        table,
        [
            {
                "import_path": "lfx.components.foo.Foo",
                "target": "ext:foo:Foo@official",
                "added_in": "1.10.0",
            },
        ],
    )
    proc = _run("--table", str(table), "--components-root", str(tmp_path))
    assert proc.returncode == 0, proc.stderr


@pytest.mark.unit
def test_unique_bare_name_passes(tmp_path: Path) -> None:
    components = tmp_path / "components"
    _make_component(components, "duckduckgo", "search.py", "DuckDuckGoSearchComponent")

    table = tmp_path / "table.json"
    _write_table(
        table,
        [
            {
                "bare_class_name": "DuckDuckGoSearchComponent",
                "target": "ext:duckduckgo:DuckDuckGoSearchComponent@official",
                "added_in": "1.10.0",
            },
        ],
    )

    proc = _run("--table", str(table), "--components-root", str(components))
    assert proc.returncode == 0, proc.stderr


@pytest.mark.unit
def test_ambiguous_bare_name_fails(tmp_path: Path) -> None:
    """A class declared in two bundle folders must not have a bare-name entry.

    This is the canonical regression case: MergeDataComponent / SplitTextComponent /
    SubFlowComponent all live in both ``processing/`` and ``deactivated/`` in
    the real tree.  Adding a bare-name entry for any of them would let saved
    flows silently load into the wrong bundle.
    """
    components = tmp_path / "components"
    _make_component(components, "processing", "merge_data.py", "MergeDataComponent")
    _make_component(components, "deactivated", "merge_data.py", "MergeDataComponent")

    table = tmp_path / "table.json"
    _write_table(
        table,
        [
            {
                "bare_class_name": "MergeDataComponent",
                "target": "ext:processing:MergeDataComponent@official",
                "added_in": "1.10.0",
            },
        ],
    )

    proc = _run("--table", str(table), "--components-root", str(components))
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "ambiguous" in proc.stderr.lower()
    assert "MergeDataComponent" in proc.stderr
    # The error must name BOTH offending bundles so the engineer can resolve it.
    assert "processing" in proc.stderr
    assert "deactivated" in proc.stderr


@pytest.mark.unit
def test_unknown_bare_name_fails(tmp_path: Path) -> None:
    """A bare-name entry referring to a class no bundle declares is a typo or stale."""
    components = tmp_path / "components"
    _make_component(components, "duckduckgo", "search.py", "DuckDuckGoSearchComponent")

    table = tmp_path / "table.json"
    _write_table(
        table,
        [
            {
                "bare_class_name": "TypoComponent",
                "target": "ext:duckduckgo:TypoComponent@official",
                "added_in": "1.10.0",
            },
        ],
    )

    proc = _run("--table", str(table), "--components-root", str(components))
    assert proc.returncode == 1
    assert "TypoComponent" in proc.stderr
    assert "no class named" in proc.stderr.lower()


@pytest.mark.unit
def test_dunder_init_files_not_counted(tmp_path: Path) -> None:
    """A class re-exported from __init__.py must not double-count the bundle.

    Without this guard, every package that re-exports its component would
    show up as TWO bundle folders for the same class name, breaking the
    uniqueness check.
    """
    components = tmp_path / "components"
    _make_component(components, "duckduckgo", "search.py", "DuckDuckGoSearchComponent")
    # __init__ that re-exports the class via a class declaration would falsely
    # double-register it.  The script skips __init__.py entirely.
    (components / "duckduckgo" / "__init__.py").write_text("class DuckDuckGoSearchComponent: pass\n", encoding="utf-8")

    table = tmp_path / "table.json"
    _write_table(
        table,
        [
            {
                "bare_class_name": "DuckDuckGoSearchComponent",
                "target": "ext:duckduckgo:DuckDuckGoSearchComponent@official",
                "added_in": "1.10.0",
            },
        ],
    )

    proc = _run("--table", str(table), "--components-root", str(components))
    assert proc.returncode == 0, proc.stderr


@pytest.mark.unit
def test_missing_table_is_usage_error(tmp_path: Path) -> None:
    proc = _run("--table", str(tmp_path / "does-not-exist.json"))
    assert proc.returncode == 2
    assert "not found" in proc.stderr.lower()


@pytest.mark.unit
def test_invalid_table_json_is_usage_error(tmp_path: Path) -> None:
    table = tmp_path / "table.json"
    table.write_text("not valid json{", encoding="utf-8")
    proc = _run("--table", str(table))
    assert proc.returncode == 2
    assert "json" in proc.stderr.lower()
