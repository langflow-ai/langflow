"""Dependency and native-runtime qualification must reject unsafe release inputs."""

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.no_blockbuster


def load_guard(name):
    """Load a standalone CI script without running its command-line entry point."""
    path = Path(__file__).resolve().parents[6] / "scripts" / "ci" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def inventory(tmp_path, monkeypatch):
    """Keep release inventory tests independent of installed application packages."""
    if sys.version_info < (3, 11):
        pytest.skip("The universal-export CI script runs under Python 3.13 and uses tomllib")
    guard = load_guard("check_chroma_removal")
    (tmp_path / "uv.lock").write_text('[[package]]\nname = "lfx"\n')
    base = tmp_path / "src/backend/base"
    base.mkdir(parents=True)
    (base / "pyproject.toml").write_text('[project]\ndependencies = ["lfx[sqlite]==1.13.0"]\n')
    monkeypatch.setattr(guard.shutil, "which", lambda _: "/qualified/uv")

    def export(command, **kwargs):
        assert command[0] == "/qualified/uv"
        assert {"--frozen", "--all-packages", "--all-extras", "--all-groups"} <= set(command)
        assert kwargs == {"cwd": tmp_path, "check": True, "capture_output": True, "text": True}
        return SimpleNamespace(stdout="apsw==3.53.4.0\nsqlite-vec==0.1.9\n")

    monkeypatch.setattr(guard.subprocess, "run", export)
    return guard, tmp_path


def test_clean_universal_inventory_includes_required_runtime(inventory, capsys):
    guard, root = inventory
    guard.check_inventory(root)
    assert "contain no retired" in capsys.readouterr().out


@pytest.mark.parametrize("package", ["ChromaDB", "langchain_chroma", "agent-lifecycle-toolkit"])
@pytest.mark.parametrize("location", ["lock", "export"])
def test_retired_package_is_rejected_from_either_inventory(inventory, monkeypatch, package, location):
    guard, root = inventory
    if location == "lock":
        (root / "uv.lock").write_text(f'[[package]]\nname = "{package}"\n')
    else:
        monkeypatch.setattr(
            guard.subprocess,
            "run",
            lambda *_args, **_kwargs: SimpleNamespace(stdout=f"apsw==3.53.4.0\nsqlite-vec==0.1.9\n{package}==1.0\n"),
        )
    with pytest.raises(RuntimeError, match="Retired dependencies remain"):
        guard.check_inventory(root)


@pytest.mark.parametrize("export", ["apsw==3.53.4.0\n", "sqlite-vec==0.1.9\n", ""])
def test_missing_native_dependency_fails_inventory(inventory, monkeypatch, export):
    guard, root = inventory
    monkeypatch.setattr(guard.subprocess, "run", lambda *_args, **_kwargs: SimpleNamespace(stdout=export))
    with pytest.raises(RuntimeError, match="runtime is absent"):
        guard.check_inventory(root)


def test_base_package_must_enable_sqlite_extra(inventory):
    guard, root = inventory
    (root / "src/backend/base/pyproject.toml").write_text('[project]\ndependencies = ["lfx==1.13.0"]\n')
    with pytest.raises(RuntimeError, match="must install the SQLite runtime"):
        guard.check_inventory(root)


def test_missing_export_tool_and_failed_export_cannot_pass(inventory, monkeypatch):
    guard, root = inventory
    with monkeypatch.context() as patch:
        patch.setattr(guard.shutil, "which", lambda _: None)
        with pytest.raises(RuntimeError, match="uv is required"):
            guard.check_inventory(root)

    def failed_export(*_args, **_kwargs):
        raise subprocess.CalledProcessError(1, "uv")

    monkeypatch.setattr(guard.subprocess, "run", failed_export)
    with pytest.raises(subprocess.CalledProcessError):
        guard.check_inventory(root)


@pytest.fixture
def runtime():
    """Exercise qualification against the installed native wheels."""
    pytest.importorskip("apsw")
    pytest.importorskip("sqlite_vec")
    return load_guard("check_sqlite_runtime")


def test_native_qualification_verifies_extension_and_wal_persistence(runtime):
    result = runtime.qualify_runtime()
    assert result["apsw"] == "3.53.4.0"
    assert result["sqlite"] == "3.53.4"
    assert result["sqlite_vec"] == "v0.1.9"


@pytest.mark.parametrize("version", ["apswversion", "sqlitelibversion"])
def test_unqualified_native_version_is_rejected(runtime, monkeypatch, version):
    monkeypatch.setattr(runtime.apsw, version, lambda: "unqualified")
    with pytest.raises(RuntimeError, match="Unexpected APSW/SQLite version"):
        runtime.qualify_runtime()


def test_extension_load_failure_closes_native_connection(runtime, tmp_path, monkeypatch):
    connections = []
    native_connection = runtime.apsw.Connection

    def capture_connection(path):
        connection = native_connection(path)
        connections.append(connection)
        return connection

    monkeypatch.setattr(runtime.apsw, "Connection", capture_connection)
    monkeypatch.setattr(runtime.sqlite_vec, "loadable_path", lambda: str(tmp_path / "missing-extension"))
    with pytest.raises(runtime.apsw.ExtensionLoadingError):
        runtime.open_connection(tmp_path / "vectors.sqlite3")
    assert len(connections) == 1
    with pytest.raises(runtime.apsw.ConnectionClosedError):
        connections[0].execute("SELECT 1")
