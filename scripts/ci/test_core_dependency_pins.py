"""Prevent core package versions from drifting during release preparation."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest
import tomllib
from packaging.requirements import Requirement

ROOT = Path(__file__).resolve().parents[2]


def write_wheel(tmp_path: Path, name: str, version: str, requirements: list[str]) -> Path:
    wheel = tmp_path / f"{name.replace('-', '_')}-{version}-py3-none-any.whl"
    metadata = f"Metadata-Version: 2.4\nName: {name}\nVersion: {version}\n"
    metadata += "".join(f"Requires-Dist: {requirement}\n" for requirement in requirements)
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr(f"{name}.dist-info/METADATA", metadata)
    return wheel


@pytest.mark.parametrize(("name", "dependency"), [("langflow", "langflow-base"), ("langflow-base", "lfx")])
@pytest.mark.parametrize("version", ["1.13.1", "1.13.0.rc2", "1.13.0.dev26"])
def test_wheel_accepts_exact_core_pins(tmp_path: Path, name: str, dependency: str, version: str) -> None:
    from scripts.ci.check_core_dependency_pins import verify_core_dependency_pins

    wheel = write_wheel(
        tmp_path,
        name,
        version,
        [f"{dependency}=={version}", f'{dependency}[sqlite]=={version}; extra == "optional"'],
    )
    verify_core_dependency_pins(wheel, version)


@pytest.mark.parametrize(
    "requirement",
    ["lfx~=1.13.0", "lfx>=1.13.0rc1,<1.14.dev0", "lfx==1.13.*", "lfx==1.13.1", "lfx"],
)
def test_wheel_rejects_drift_even_in_optional_extras(tmp_path: Path, requirement: str) -> None:
    from scripts.ci.check_core_dependency_pins import verify_core_dependency_pins

    wheel = write_wheel(tmp_path, "langflow-base", "1.13.0", ["lfx==1.13.0", f'{requirement}; extra == "test"'])
    with pytest.raises(ValueError, match="exactly pinned"):
        verify_core_dependency_pins(wheel, "1.13.0")


@pytest.mark.parametrize("requirements", [[], ['lfx==1.13.0; extra == "test"']])
def test_wheel_requires_unconditional_runtime_dependency(tmp_path: Path, requirements: list[str]) -> None:
    from scripts.ci.check_core_dependency_pins import verify_core_dependency_pins

    wheel = write_wheel(tmp_path, "langflow-base", "1.13.0", requirements)
    with pytest.raises(ValueError, match="runtime dependency"):
        verify_core_dependency_pins(wheel, "1.13.0")


def test_wheel_allows_separate_nightly_lfx_counter(tmp_path: Path) -> None:
    from scripts.ci.check_core_dependency_pins import verify_core_dependency_pins

    wheel = write_wheel(tmp_path, "langflow-base", "1.13.0.dev26", ["lfx==1.13.0.dev7", "lfx-openai>=0.1,<1"])
    verify_core_dependency_pins(wheel, "1.13.0.dev7")


def test_cli_checks_built_wheel(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from scripts.ci.check_core_dependency_pins import main

    wheel = write_wheel(tmp_path, "langflow", "1.13.0", ["langflow-base==1.13.0"])
    monkeypatch.setattr(sys, "argv", ["check_core_dependency_pins.py", str(wheel), "--dependency-version", "1.13.0"])
    main()


@pytest.mark.parametrize("metadata_count", [0, 2])
def test_rejects_missing_or_ambiguous_wheel_metadata(tmp_path: Path, metadata_count: int) -> None:
    from scripts.ci.check_core_dependency_pins import verify_core_dependency_pins

    wheel = tmp_path / "invalid.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        for index in range(metadata_count):
            archive.writestr(f"package{index}.dist-info/METADATA", "Name: langflow\n")
    with pytest.raises(ValueError, match="Expected one METADATA"):
        verify_core_dependency_pins(wheel, "1.13.0")


def test_rejects_unexpected_consumer(tmp_path: Path) -> None:
    from scripts.ci.check_core_dependency_pins import verify_core_dependency_pins

    wheel = write_wheel(tmp_path, "lfx-openai", "0.1.0", ["lfx>=1.13.0"])
    with pytest.raises(ValueError, match="Unsupported core consumer"):
        verify_core_dependency_pins(wheel, "1.13.0")


def test_make_patch_preserves_exact_pins_on_repeated_bumps(tmp_path: Path) -> None:
    for relative, dependency in [("pyproject.toml", "langflow-base"), ("src/backend/base/pyproject.toml", "lfx")]:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, target)
        content = target.read_text().replace(
            "[project.optional-dependencies]",
            f"[project.optional-dependencies]\ntest-pin = [\"{dependency}[sqlite]>=1.0; sys_platform != 'win32'\"]",
        )
        target.write_text(content)
    recipe = [
        line
        for line in (ROOT / "Makefile").read_text().splitlines(keepends=True)
        if 'LANGFLOW_VERSION="$(v)"' in line
        or "fname='pyproject.toml'" in line
        or "fname='src/backend/base/pyproject.toml'" in line
    ]
    assert len(recipe) == 3
    recipe[-1] = recipe[-1].removesuffix("\\\n") + "\n"
    (tmp_path / "Makefile").write_text("patch:\n" + "".join(recipe))
    env = {**os.environ, "PATH": f"{Path(sys.executable).parent}{os.pathsep}{os.environ['PATH']}"}
    for version in ["1.13.1", "1.13.2"]:
        result = subprocess.run(  # noqa: S603
            ["make", "patch", f"v={version}"],  # noqa: S607
            cwd=tmp_path,
            env=env,
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        for relative, dependency in [("pyproject.toml", "langflow-base"), ("src/backend/base/pyproject.toml", "lfx")]:
            project = tomllib.loads((tmp_path / relative).read_text())["project"]
            values = project["dependencies"] + [
                value for extra in project["optional-dependencies"].values() for value in extra
            ]
            requirements = [Requirement(value) for value in values if Requirement(value).name == dependency]
            assert requirements
            assert all(str(requirement.specifier) == f"=={version}" for requirement in requirements)
            assert any(str(requirement.marker) == 'sys_platform != "win32"' for requirement in requirements)
