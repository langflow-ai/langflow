"""Make a full pre-release accept the exact bundle pre-releases built with it."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import tomllib
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from packaging.version import Version

ARGUMENT_COUNT = 3


def update_bundle_prerelease_dependencies(pyproject_path: Path, manifest_path: Path) -> int:
    """Lower bundle floors to the RC versions recorded in ``manifest_path``.

    Stable source requirements stay broad. Only the temporary full-package build
    manifest is changed, and existing upper bounds and extras are preserved.
    """
    content = pyproject_path.read_text(encoding="utf-8")
    project = tomllib.loads(content)["project"]
    manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest = {canonicalize_name(name): Version(version) for name, version in manifest_data.items()}

    dependencies = list(project.get("dependencies", []))
    for group in project.get("optional-dependencies", {}).values():
        dependencies.extend(group)

    updated = 0
    for raw_dependency in dependencies:
        requirement = Requirement(raw_dependency)
        name = canonicalize_name(requirement.name)
        bundle_version = manifest.get(name)
        if bundle_version is None or not bundle_version.is_prerelease:
            continue

        rewritten, replacements = re.subn(
            r">=[^,;\s]+",
            f">={bundle_version}",
            raw_dependency,
            count=1,
        )
        if replacements != 1:
            msg = f"Cannot rewrite the lower bound for {raw_dependency!r}"
            raise ValueError(msg)

        rewritten_requirement = Requirement(rewritten)
        if not rewritten_requirement.specifier.contains(bundle_version):
            msg = f"Rewritten dependency {rewritten!r} still excludes {bundle_version}"
            raise ValueError(msg)

        old_literal = f'"{raw_dependency}"'
        new_literal = f'"{rewritten}"'
        if old_literal not in content:
            msg = f"TOML literal not found for {raw_dependency!r}"
            raise ValueError(msg)
        content = content.replace(old_literal, new_literal, 1)
        updated += 1

    pyproject_path.write_text(content, encoding="utf-8")
    return updated


def main() -> None:
    if len(sys.argv) != ARGUMENT_COUNT:
        message = "Usage: update_bundle_prerelease_dependencies.py <pyproject.toml> <bundle-version-manifest.json>"
        raise SystemExit(message)

    updated = update_bundle_prerelease_dependencies(Path(sys.argv[1]), Path(sys.argv[2]))
    print(f"Updated {updated} bundle pre-release requirement(s).")


if __name__ == "__main__":
    main()
