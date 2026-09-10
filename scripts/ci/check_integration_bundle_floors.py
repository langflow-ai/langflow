"""Require integration-declaring bundles to depend on a compatible lfx.

Run with Python 3.11+ and packaging, without installing lfx or any bundles.
The same feature floor is used by the runtime's pre-schema version check.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import tomllib
from packaging.requirements import Requirement

BASE_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE_DIR / "src" / "lfx" / "src" / "lfx" / "extension"))

from integration_compat import INTEGRATIONS_MIN_LFX_VERSION, supports_integration_manifests  # noqa: E402


def _declares_integrations(manifest: object) -> bool:
    if not isinstance(manifest, dict):
        msg = "Extension manifests must be objects"
        raise TypeError(msg)
    # Even an empty field is rejected by lfx releases that predate the schema.
    return "integrations" in manifest


def check_bundle(pyproject: Path) -> list[str]:
    """Check shipped JSON and TOML manifests against project runtime dependencies."""
    try:
        project = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        declarations = []
        inline = project.get("tool", {}).get("langflow", {}).get("extension", {})
        if _declares_integrations(inline):
            declarations.append(str(pyproject))
        manifests = [pyproject.parent / "extension.json", *(pyproject.parent / "src").rglob("extension.json")]
        declarations.extend(
            str(manifest)
            for manifest in manifests
            if manifest.is_file() and _declares_integrations(json.loads(manifest.read_text(encoding="utf-8")))
        )
        for manifest in (pyproject.parent / "src").rglob("pyproject.toml"):
            data = tomllib.loads(manifest.read_text(encoding="utf-8"))
            if _declares_integrations(data.get("tool", {}).get("langflow", {}).get("extension", {})):
                declarations.append(str(manifest))
        if not declarations:
            return []
        dependencies = project.get("project", {}).get("dependencies", [])
        if any(supports_integration_manifests(Requirement(dependency)) for dependency in dependencies):
            return []
    except (OSError, ValueError, TypeError, AttributeError) as exc:
        return [f"{pyproject}: cannot validate integration dependency floor: {exc}"]
    return [
        f"{pyproject}: integrations declared in {', '.join(declarations)} require an unconditional "
        f"lfx>={INTEGRATIONS_MIN_LFX_VERSION} runtime dependency. "
        "Run uv run python scripts/ci/sync_bundle_lfx_pin.py 1.13.0."
    ]


def check_bundles(bundles_dir: Path) -> list[str]:
    """Return all integration/floor pairing failures in the bundle workspace."""
    return [error for project in sorted(bundles_dir.glob("*/pyproject.toml")) for error in check_bundle(project)]


def main() -> int:
    errors = check_bundles(BASE_DIR / "src" / "bundles")
    for error in errors:
        print(error, file=sys.stderr)
    if not errors:
        print("Integration bundle lfx floors: ok")
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
