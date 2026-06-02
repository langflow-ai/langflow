"""Rename ``lfx-*`` bundle packages to their ``-nightly`` counterparts.

Bundles under ``src/bundles/*`` follow the same package-rename convention as
``langflow``, ``langflow-base``, ``lfx``, and ``langflow-sdk``: for nightly
builds, the distribution is published as ``<name>-nightly`` so the regular
(non-nightly) PyPI name stays untouched.

This script (a) renames each bundle's ``[project] name`` to
``<name>-nightly``, (b) bumps its version to ``<base>.dev<N>``, (c) rewrites
its ``lfx`` runtime dep so it resolves against the renamed ``lfx-nightly``
workspace member, and (d) updates the root ``pyproject.toml`` so its bundle
deps and ``[tool.uv.sources]`` entries reference the renamed packages.

All operations are idempotent — running twice is a no-op.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent.parent

# Matches the lfx dep specifier inside a bundle pyproject's dependencies list.
# Accepts the bundle default ("lfx>=X.Y.Z" with an optional upper bound),
# legacy ~=/==, and the already-rewritten "lfx-nightly==X.Y.Z" form (idempotent).
_LFX_DEP_PATTERN = re.compile(
    r'"lfx(?:-nightly)?'
    r"(?:"
    r"(?:~=|==)[\d.]+(?:\.(?:post|dev|a|b|rc)\d+)*"
    r"|"
    r">=[\d.]+(?:\.(?:post|dev|a|b|rc)\d+)*"
    r"(?:,\s*<[\d.]+(?:\.(?:post|dev|a|b|rc)\d+)*)?"
    r')"'
)

_PROJECT_NAME_PATTERN = re.compile(r'(\[project\][^\[]*?\nname = ")([^"]+)(")', re.DOTALL)
_PROJECT_VERSION_PATTERN = re.compile(r'(\[project\][^\[]*?\nversion = ")([^"]+)(")', re.DOTALL)


def _strip_nightly(name: str) -> str:
    """Return the base name with a trailing ``-nightly`` stripped (for idempotency)."""
    return name.removesuffix("-nightly")


def _strip_dev_suffix(version: str) -> str:
    """Return the base version with any trailing PEP 440 dev segment stripped."""
    return re.sub(r"\.dev\d+$", "", version)


def _extract_dev_n(tag: str) -> str:
    """Extract ``N`` from a tag like ``v0.5.0.dev38`` or ``0.5.0.dev38``."""
    match = re.search(r"\.dev(\d+)$", tag)
    if not match:
        msg = f"Tag does not end in .devN: {tag!r}"
        raise ValueError(msg)
    return match.group(1)


def rename_bundle_pyproject(pyproject_path: Path, lfx_version: str, dev_n: str) -> tuple[str, str, str] | None:
    """Rewrite a single bundle ``pyproject.toml`` for nightly publication.

    - ``[project] name``         → ``<base_name>-nightly``
    - ``[project] version``      → ``<base_version>.dev<N>``
    - entry-point key            → ``<base_name>-nightly``
    - ``"lfx>=...,<..."`` dep    → ``"lfx-nightly==<lfx_version>"``

    Returns ``(base_name, nightly_name, nightly_version)`` so the caller can
    update the root pyproject. Returns ``None`` if the file has no
    ``[project]`` name/version (shouldn't happen, but we skip rather than fail).
    """
    content = pyproject_path.read_text(encoding="utf-8")

    name_match = _PROJECT_NAME_PATTERN.search(content)
    version_match = _PROJECT_VERSION_PATTERN.search(content)
    if not name_match or not version_match:
        return None

    base_name = _strip_nightly(name_match.group(2))
    nightly_name = f"{base_name}-nightly"
    base_version = _strip_dev_suffix(version_match.group(2))
    nightly_version = f"{base_version}.dev{dev_n}"

    content = _PROJECT_NAME_PATTERN.sub(rf"\g<1>{nightly_name}\g<3>", content, count=1)
    content = _PROJECT_VERSION_PATTERN.sub(rf"\g<1>{nightly_version}\g<3>", content, count=1)

    # Entry-point key. The key may already be the nightly form on a re-run.
    entry_point_pattern = re.compile(
        rf'(\[project\.entry-points\."langflow\.extensions"\]\s*\n)'
        rf"{re.escape(base_name)}(?:-nightly)?"
        rf'(\s*=\s*"[^"]+")'
    )
    content = entry_point_pattern.sub(rf"\g<1>{nightly_name}\g<2>", content, count=1)

    # Rewrite the lfx dep regardless of which form it's in.
    content = _LFX_DEP_PATTERN.sub(f'"lfx-nightly=={lfx_version}"', content)

    pyproject_path.write_text(content, encoding="utf-8")
    return base_name, nightly_name, nightly_version


def update_root_pyproject_for_bundle(
    root_pyproject: Path,
    base_name: str,
    nightly_name: str,
    nightly_version: str,
) -> None:
    """Update root ``pyproject.toml`` to reference the nightly bundle.

    - dependency line  ``"<base_name>[..]"`` → ``"<nightly_name>==<version>"``
    - uv.sources entry ``<base_name> = { workspace = true }`` → ``<nightly_name> = ...``

    Idempotent: also matches the already-nightly form.
    """
    content = root_pyproject.read_text(encoding="utf-8")

    # Dependency in [project.dependencies] (any PEP 440 specifier or range form).
    dep_pattern = re.compile(
        rf'"{re.escape(base_name)}(?:-nightly)?'
        r"(?:"
        r"(?:~=|==|>=)[\d.]+(?:\.(?:post|dev|a|b|rc)\d+)*"
        r"(?:,\s*<[\d.]+(?:\.(?:post|dev|a|b|rc)\d+)*)?"
        r')"'
    )
    content = dep_pattern.sub(f'"{nightly_name}=={nightly_version}"', content)

    # uv.sources entry — only the workspace = true form is used by bundles today.
    source_pattern = re.compile(
        rf"^{re.escape(base_name)}(?:-nightly)?(\s*=\s*\{{\s*workspace\s*=\s*true\s*\}})",
        re.MULTILINE,
    )
    content = source_pattern.sub(rf"{nightly_name}\g<1>", content)

    root_pyproject.write_text(content, encoding="utf-8")


def update_bundles_for_nightly(lfx_tag: str) -> list[tuple[str, str, str]]:
    """Rename every ``src/bundles/*`` package to its ``-nightly`` counterpart.

    Returns a list of ``(base_name, nightly_name, nightly_version)`` tuples
    for the bundles that were rewritten.
    """
    bundles_dir = BASE_DIR / "src" / "bundles"
    if not bundles_dir.is_dir():
        return []

    lfx_version = lfx_tag.lstrip("v")
    dev_n = _extract_dev_n(lfx_version)
    root_pyproject = BASE_DIR / "pyproject.toml"

    results: list[tuple[str, str, str]] = []
    for bundle_pyproject in sorted(bundles_dir.glob("*/pyproject.toml")):
        renamed = rename_bundle_pyproject(bundle_pyproject, lfx_version, dev_n)
        if renamed is None:
            continue
        base_name, nightly_name, nightly_version = renamed
        update_root_pyproject_for_bundle(root_pyproject, base_name, nightly_name, nightly_version)
        results.append(renamed)
        print(f"Renamed {base_name} -> {nightly_name} ({nightly_version}) in {bundle_pyproject.relative_to(BASE_DIR)}")
    return results


def main() -> None:
    """Entry point.

    Usage:
        update_bundle_versions.py <lfx_tag>

    ``lfx_tag`` is the LFX nightly tag (e.g., ``v0.5.0.dev38``); its ``.devN``
    suffix is reused for all bundles so they share a single nightly cadence.
    """
    expected_args = 2
    if len(sys.argv) != expected_args:
        print("Usage: update_bundle_versions.py <lfx_tag>")
        sys.exit(1)
    update_bundles_for_nightly(sys.argv[1])


if __name__ == "__main__":
    main()
