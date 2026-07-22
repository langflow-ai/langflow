"""Tests for release-wheel selection used by Docker builds."""

from __future__ import annotations

import json
import zipfile
from typing import TYPE_CHECKING

import pytest

from scripts.ci.install_release_wheels import _restore_frontend, _select_wheels, install_release_wheels

if TYPE_CHECKING:
    from pathlib import Path


def _write_wheel(directory: Path, name: str, version: str) -> None:
    normalized_name = name.replace("-", "_")
    wheel_path = directory / f"{normalized_name}-{version}-py3-none-any.whl"
    metadata_path = f"{normalized_name}-{version}.dist-info/METADATA"
    with zipfile.ZipFile(wheel_path, "w") as archive:
        archive.writestr(metadata_path, f"Metadata-Version: 2.4\nName: {name}\nVersion: {version}\n")


def test_main_installs_every_release_artifact(tmp_path: Path) -> None:
    _write_wheel(tmp_path, "langflow", "1.11.0rc5")
    _write_wheel(tmp_path, "langflow-base", "0.11.0rc5")
    _write_wheel(tmp_path, "lfx", "1.11.0rc5")
    _write_wheel(tmp_path, "langflow-sdk", "0.3.0rc5")
    _write_wheel(tmp_path, "lfx-arxiv", "0.1.3rc5")

    wheels = _select_wheels(tmp_path, "main")

    assert {wheel.name: wheel.version for wheel in wheels} == {
        "langflow": "1.11.0rc5",
        "langflow-base": "0.11.0rc5",
        "langflow-sdk": "0.3.0rc5",
        "lfx": "1.11.0rc5",
        "lfx-arxiv": "0.1.3rc5",
    }


def test_base_excludes_main_and_bundle_wheels(tmp_path: Path) -> None:
    _write_wheel(tmp_path, "langflow", "1.11.0rc5")
    _write_wheel(tmp_path, "langflow-base", "0.11.0rc5")
    _write_wheel(tmp_path, "lfx", "1.11.0rc5")
    _write_wheel(tmp_path, "langflow-sdk", "0.3.0rc5")
    _write_wheel(tmp_path, "lfx-arxiv", "0.1.3rc5")

    wheels = _select_wheels(tmp_path, "base")

    assert {wheel.name for wheel in wheels} == {"langflow-base", "langflow-sdk", "lfx"}


def test_missing_required_wheel_fails_closed(tmp_path: Path) -> None:
    _write_wheel(tmp_path, "langflow-base", "0.11.0rc5")

    with pytest.raises(ValueError, match="missing required main wheels"):
        _select_wheels(tmp_path, "main")


def test_install_release_wheels_installs_verifies_and_checks(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_wheel(tmp_path, "langflow", "1.11.0rc5")
    _write_wheel(tmp_path, "langflow-base", "0.11.0rc5")
    _write_wheel(tmp_path, "lfx", "1.11.0rc5")
    python = tmp_path / "venv" / "bin" / "python"
    uv = tmp_path / "bin" / "uv"
    commands: list[tuple[list[object], bool]] = []

    def record_run(command: list[object], *, check: bool) -> None:
        commands.append((command, check))

    monkeypatch.setattr("scripts.ci.install_release_wheels._find_uv", lambda: str(uv))
    monkeypatch.setattr("scripts.ci.install_release_wheels.subprocess.run", record_run)

    install_release_wheels(tmp_path, python, "main")

    assert len(commands) == 3
    assert all(check for _, check in commands)
    install_command, verify_command, check_command = (command for command, _ in commands)
    assert install_command[:7] == [
        str(uv),
        "pip",
        "install",
        "--python",
        str(python),
        "--no-deps",
        "--force-reinstall",
    ]
    assert {str(path) for path in install_command[7:]} == {str(path) for path in tmp_path.glob("*.whl")}
    assert verify_command[:2] == [python, "-c"]
    assert "assert actual == expected" in str(verify_command[2])
    assert json.loads(str(verify_command[3])) == {
        "langflow": "1.11.0rc5",
        "langflow-base": "0.11.0rc5",
        "lfx": "1.11.0rc5",
    }
    assert check_command == [str(uv), "pip", "check", "--python", str(python)]


def test_install_release_wheels_without_artifacts_is_a_noop(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    commands: list[list[object]] = []
    monkeypatch.setattr(
        "scripts.ci.install_release_wheels.subprocess.run",
        lambda command, **_kwargs: commands.append(command),
    )

    install_release_wheels(tmp_path, tmp_path / "python", "main")

    assert commands == []


def test_restore_frontend_replaces_wheel_assets(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    frontend_source = tmp_path / "built-frontend"
    frontend_source.mkdir()
    (frontend_source / "index.html").write_text("docker build", encoding="utf-8")
    package_dir = tmp_path / "site-packages" / "langflow"
    installed_frontend = package_dir / "frontend"
    installed_frontend.mkdir(parents=True)
    (installed_frontend / "index.html").write_text("wheel build", encoding="utf-8")
    monkeypatch.setattr(
        "scripts.ci.install_release_wheels.subprocess.check_output",
        lambda *_args, **_kwargs: str(package_dir),
    )

    _restore_frontend(tmp_path / "python", frontend_source)

    assert (installed_frontend / "index.html").read_text(encoding="utf-8") == "docker build"
