"""Install release-built wheels into a Docker image's prepared virtual environment.

Release Docker builds start from the tagged source tree so they can compile the
frontend for the target architecture. For pre-releases, however, the source tree
still contains the final package versions while the release jobs build restamped
RC wheels. This helper replaces the source-installed distributions with those
exact wheels before the runtime image is assembled.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import zipfile
from dataclasses import dataclass
from email.parser import BytesParser
from pathlib import Path

BASE_DISTRIBUTIONS = frozenset({"langflow-base", "langflow-sdk", "lfx"})
REQUIRED_DISTRIBUTIONS = {
    "base": frozenset({"langflow-base", "lfx"}),
    "main": frozenset({"langflow", "langflow-base", "lfx"}),
}


@dataclass(frozen=True)
class Wheel:
    """A wheel path and the canonical distribution metadata it contains."""

    path: Path
    name: str
    version: str


def _canonicalize_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _find_uv() -> str:
    uv = shutil.which("uv")
    if uv is None:
        msg = "uv is required to install release wheels"
        raise FileNotFoundError(msg)
    return uv


def _read_wheel(path: Path) -> Wheel:
    with zipfile.ZipFile(path) as archive:
        metadata_paths = [name for name in archive.namelist() if name.endswith(".dist-info/METADATA")]
        if len(metadata_paths) != 1:
            msg = f"Expected one METADATA file in {path}, found {len(metadata_paths)}"
            raise ValueError(msg)
        metadata = BytesParser().parsebytes(archive.read(metadata_paths[0]))

    name = metadata.get("Name")
    version = metadata.get("Version")
    if not name or not version:
        msg = f"Wheel {path} is missing Name or Version metadata"
        raise ValueError(msg)
    return Wheel(path=path, name=_canonicalize_name(name), version=version)


def _select_wheels(artifacts_dir: Path, mode: str) -> list[Wheel]:
    wheels = [_read_wheel(path) for path in sorted(artifacts_dir.rglob("*.whl"))]
    if mode == "base":
        wheels = [wheel for wheel in wheels if wheel.name in BASE_DISTRIBUTIONS]

    by_name: dict[str, Wheel] = {}
    for wheel in wheels:
        if previous := by_name.get(wheel.name):
            msg = f"Duplicate release wheels for {wheel.name}: {previous.path} and {wheel.path}"
            raise ValueError(msg)
        by_name[wheel.name] = wheel

    missing = REQUIRED_DISTRIBUTIONS[mode] - by_name.keys()
    if missing:
        msg = f"Release artifacts are missing required {mode} wheels: {', '.join(sorted(missing))}"
        raise ValueError(msg)
    return sorted(by_name.values(), key=lambda wheel: wheel.name)


def _restore_frontend(python: Path, frontend_source: Path) -> None:
    command = (
        "from importlib.util import find_spec; "
        "from pathlib import Path; "
        "spec = find_spec('langflow'); "
        "assert spec is not None and spec.origin is not None; "
        "print(Path(spec.origin).parent)"
    )
    # Isolated mode keeps the Dockerfile's source-tree working directory off
    # sys.path so find_spec resolves the wheel installed in site-packages.
    package_dir = Path(subprocess.check_output([python, "-I", "-c", command], text=True).strip())  # noqa: S603
    frontend_source = frontend_source.resolve()
    frontend_target = (package_dir / "frontend").resolve()
    if frontend_source == frontend_target:
        msg = f"Frontend source and target must be different: {frontend_source}"
        raise ValueError(msg)
    shutil.rmtree(frontend_target, ignore_errors=True)
    shutil.copytree(frontend_source, frontend_target)
    print(f"Restored Docker-built frontend assets to {frontend_target}")


def install_release_wheels(
    artifacts_dir: Path,
    python: Path,
    mode: str,
    frontend_source: Path | None = None,
) -> None:
    """Replace source-installed packages with the release workflow's wheels."""
    if not any(artifacts_dir.rglob("*.whl")):
        print(f"No release wheels found in {artifacts_dir}; keeping source-installed packages")
        return

    wheels = _select_wheels(artifacts_dir, mode)
    expected_versions = {wheel.name: wheel.version for wheel in wheels}
    uv = _find_uv()
    print("Installing release wheels:")
    for wheel in wheels:
        print(f"  {wheel.name}=={wheel.version} ({wheel.path})")

    subprocess.run(  # noqa: S603
        [
            uv,
            "pip",
            "install",
            "--python",
            str(python),
            "--no-deps",
            "--force-reinstall",
            *(str(wheel.path) for wheel in wheels),
        ],
        check=True,
    )

    verify_code = (
        "import importlib.metadata as metadata, json, sys; "
        "expected = json.loads(sys.argv[1]); "
        "actual = {name: metadata.version(name) for name in expected}; "
        "assert actual == expected, f'installed versions {actual!r} != release artifacts {expected!r}'; "
        "print(json.dumps(actual, sort_keys=True))"
    )
    subprocess.run(  # noqa: S603
        [python, "-c", verify_code, json.dumps(expected_versions, sort_keys=True)],
        check=True,
    )
    subprocess.run([uv, "pip", "check", "--python", str(python)], check=True)  # noqa: S603

    if frontend_source is not None:
        if not frontend_source.is_dir():
            msg = f"Docker-built frontend directory does not exist: {frontend_source}"
            raise FileNotFoundError(msg)
        _restore_frontend(python, frontend_source)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifacts_dir", type=Path)
    parser.add_argument("--python", type=Path, required=True, help="Python executable for the image virtualenv")
    parser.add_argument("--mode", choices=sorted(REQUIRED_DISTRIBUTIONS), required=True)
    parser.add_argument("--frontend-source", type=Path)
    args = parser.parse_args()

    try:
        install_release_wheels(args.artifacts_dir, args.python, args.mode, args.frontend_source)
    except (FileNotFoundError, OSError, subprocess.CalledProcessError, ValueError, zipfile.BadZipFile) as exc:
        print(f"Failed to install release wheels: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
