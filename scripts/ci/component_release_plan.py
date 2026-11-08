"""Select independently published compatibility baselines for application and bundles."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Any

import tomllib
from bundle_release_plan import PyPIClient
from component_compatibility import CompatibilityGateError
from packaging.utils import canonicalize_name
from packaging.version import InvalidVersion, Version


def previous_release(declared: str, releases: tuple[str, ...]) -> str | None:
    """Include equal versions so an unbumped PR compares with its published version."""
    ceiling = Version(declared)
    candidates = []
    for value in releases:
        try:
            parsed = Version(value)
        except InvalidVersion:
            continue
        if not parsed.is_prerelease and not parsed.is_devrelease and parsed.local is None and parsed <= ceiling:
            candidates.append(parsed)
    return str(max(candidates)) if candidates else None


def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=True).stdout  # noqa: S603,S607


def declared_distributions(root: Path, ref: str | None = None) -> dict[str, dict[str, str]]:
    if ref is not None and not re.fullmatch(r"[0-9a-f]{40}", ref):
        msg = "the baseline Git revision must be a full lowercase commit SHA"
        raise CompatibilityGateError(msg)
    paths = ["pyproject.toml"]
    if ref:
        paths += [
            value
            for value in _git(root, "ls-tree", "-r", "--name-only", ref, "--", "src/bundles").splitlines()
            if re.fullmatch(r"src/bundles/[^/]+/pyproject.toml", value)
        ]
    else:
        paths += [str(path.relative_to(root)) for path in sorted((root / "src/bundles").glob("*/pyproject.toml"))]
    result = {}
    for path in paths:
        text = _git(root, "show", f"{ref}:{path}") if ref else (root / path).read_text()
        project = tomllib.loads(text)["project"]
        result[canonicalize_name(project["name"])] = {"version": project["version"], "path": str(Path(path).parent)}
    return result


def release_plan(root: Path, base_sha: str, client: PyPIClient) -> dict[str, Any]:
    base = declared_distributions(root, base_sha)
    target = declared_distributions(root)
    comparisons = []
    for package, metadata in sorted(target.items()):
        baseline = base.get(package, metadata)
        versions = client.get_versions(package)
        previous = previous_release(baseline["version"], versions)
        comparisons.append(
            {
                "distribution": package,
                "target_version": metadata["version"],
                "target_path": metadata["path"],
                "baseline_ceiling": baseline["version"],
                "previous_version": previous,
                "history": "published_release" if previous else "no_published_predecessor",
                "whole_registry": package == "langflow",
            }
        )
    return {"format_version": 1, "base_sha": base_sha, "comparisons": comparisons}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--base-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    plan = release_plan(args.root.resolve(), args.base_sha, PyPIClient())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(plan, indent=2) + "\n")


if __name__ == "__main__":
    main()
