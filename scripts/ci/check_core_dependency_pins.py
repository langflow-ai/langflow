"""Reject release wheels that allow the backend or engine version to drift."""

from __future__ import annotations

import argparse
import zipfile
from email.parser import BytesParser
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from packaging.version import Version


def verify_core_dependency_pins(wheel: Path, dependency_version: str) -> None:
    """Check every core requirement against the dependency built for this release."""
    expected = Version(dependency_version)
    with zipfile.ZipFile(wheel) as archive:
        paths = [name for name in archive.namelist() if name.endswith(".dist-info/METADATA")]
        if len(paths) != 1:
            msg = f"Expected one METADATA file in {wheel}"
            raise ValueError(msg)
        metadata = BytesParser().parsebytes(archive.read(paths[0]))

    dependencies = {"langflow": "langflow-base", "langflow-base": "lfx"}
    package = canonicalize_name(metadata.get("Name", ""))
    if package not in dependencies:
        msg = f"Unsupported core consumer in {wheel}: {package}"
        raise ValueError(msg)
    dependency = dependencies[package]
    requirements = [
        Requirement(value)
        for value in metadata.get_all("Requires-Dist", [])
        if canonicalize_name(Requirement(value).name) == dependency
    ]
    if not any(requirement.marker is None for requirement in requirements):
        msg = f"{wheel.name} is missing its {dependency} runtime dependency"
        raise ValueError(msg)
    for requirement in requirements:
        specs = list(requirement.specifier)
        if (
            requirement.url is not None
            or len(specs) != 1
            or specs[0].operator != "=="
            or "*" in specs[0].version
            or Version(specs[0].version) != expected
        ):
            msg = f"{wheel.name} must have {dependency} exactly pinned to {expected}, got {requirement}"
            raise ValueError(msg)
    print(f"Verified {wheel.name} pins every {dependency} requirement to {expected}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wheels", type=Path, nargs="+")
    parser.add_argument("--dependency-version", required=True)
    args = parser.parse_args()
    for wheel in args.wheels:
        verify_core_dependency_pins(wheel, args.dependency_version)


if __name__ == "__main__":
    main()
