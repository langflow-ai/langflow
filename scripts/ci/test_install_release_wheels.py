"""Tests for release-wheel selection used by Docker builds."""

from __future__ import annotations

import zipfile
from typing import TYPE_CHECKING

import pytest

from scripts.ci.install_release_wheels import _restore_frontend, _select_wheels

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
