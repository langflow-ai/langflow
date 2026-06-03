"""Script to update LFX version for nightly builds."""

import re
import sys
from pathlib import Path

import tomllib
from packaging.version import Version
from update_pyproject_name import update_pyproject_name
from update_pyproject_version import update_pyproject_version

# Add the current directory to the path so we can import the other scripts
current_dir = Path(__file__).resolve().parent
sys.path.append(str(current_dir))

BASE_DIR = Path(__file__).parent.parent.parent
ROOT_PYPROJECT = BASE_DIR / "pyproject.toml"


def update_lfx_workspace_dep(pyproject_path: str, new_project_name: str) -> None:
    """Update the LFX workspace dependency in pyproject.toml."""
    filepath = BASE_DIR / pyproject_path
    content = filepath.read_text(encoding="utf-8")

    if new_project_name == "lfx-nightly":
        pattern = re.compile(r"lfx = \{ workspace = true \}")
        replacement = "lfx-nightly = { workspace = true }"
    else:
        msg = f"Invalid LFX project name: {new_project_name}"
        raise ValueError(msg)

    # Updates the dependency name for uv
    if not pattern.search(content):
        msg = f"lfx workspace dependency not found in {filepath}"
        raise ValueError(msg)
    content = pattern.sub(replacement, content)
    filepath.write_text(content, encoding="utf-8")


def update_sdk_dependency_in_lfx(pyproject_path: str, sdk_version: str) -> None:
    """Update the SDK dependency in the LFX pyproject for nightly builds."""
    filepath = BASE_DIR / pyproject_path
    content = filepath.read_text(encoding="utf-8")

    pattern = re.compile(r'"langflow-sdk(?:-nightly)?(?:==|~=|>=)[\d.]+(?:\.(?:post|dev|a|b|rc)\d+)*"')
    replacement = f'"langflow-sdk-nightly=={sdk_version}"'

    if not pattern.search(content):
        msg = f"SDK dependency not found in {filepath}"
        raise ValueError(msg)

    content = pattern.sub(replacement, content)
    filepath.write_text(content, encoding="utf-8")


# Match an `lfx` (or `lfx-nightly`) dependency specifier inside a quoted
# string. The lookahead enforces a version operator immediately after the
# name so we don't accidentally match sibling packages like `lfx-arxiv` or
# `lfx-duckduckgo`.
_BUNDLE_LFX_DEP_PATTERN = re.compile(r'"lfx(?:-nightly)?(?=[<>=!~])[^"]*"')


def update_lfx_dep_in_bundles(lfx_version: str) -> None:
    """Pin every bundle's `lfx` dep to the renamed `lfx-nightly==<version>`.

    Each `src/bundles/*/pyproject.toml` floors its `lfx` dep at `>=X.Y`
    (no upper bound) against the published `lfx` package. During nightly builds the
    workspace `lfx` package gets renamed to `lfx-nightly`, so those pins
    no longer resolve against the workspace member — and PyPI may not yet
    ship a matching `lfx` either. Rewrite each bundle's pin to
    `lfx-nightly==<exact dev version>` so `uv lock` resolves cleanly.

    No-op when no bundles exist (e.g. on a branch that hasn't picked up
    the bundle extraction) or when a bundle has no `lfx` dep.
    """
    bundles_dir = BASE_DIR / "src" / "bundles"
    if not bundles_dir.is_dir():
        return

    replacement = f'"lfx-nightly=={lfx_version}"'
    for bundle_pyproject in sorted(bundles_dir.glob("*/pyproject.toml")):
        content = bundle_pyproject.read_text(encoding="utf-8")
        if not _BUNDLE_LFX_DEP_PATTERN.search(content):
            continue
        new_content = _BUNDLE_LFX_DEP_PATTERN.sub(replacement, content)
        if new_content == content:
            continue
        bundle_pyproject.write_text(new_content, encoding="utf-8")
        print(f"Updated lfx dep in {bundle_pyproject.relative_to(BASE_DIR)} -> lfx-nightly=={lfx_version}")


def _bundle_nightly_version(bundle_base_version: str, lfx_version: str) -> str:
    """Derive a bundle's nightly version: `<bundle base>.dev<N>`.

    The dev build number `N` is shared with `lfx-nightly` (the same value the
    nightly tagger already pins each bundle's `lfx` dep to), so a bundle's
    nightly version moves in lockstep with the lfx it was built against while
    keeping the bundle's own base version (e.g. `0.1.0`) truthful.
    """
    lfx_parsed = Version(lfx_version)
    if lfx_parsed.dev is None:
        msg = f"Expected a .devN nightly lfx version, got {lfx_version!r}"
        raise ValueError(msg)
    base = Version(bundle_base_version).base_version
    return f"{base}.dev{lfx_parsed.dev}"


def rename_bundles_for_nightly(lfx_version: str) -> None:
    """Rename each `src/bundles/*` package to its `-nightly` distribution.

    The stable bundles publish as `lfx-<name>` and pin `lfx>=X.Y`. During a
    nightly build the workspace `lfx` becomes `lfx-nightly` (no stable `lfx`
    matching the pin may exist on PyPI yet), so a `langflow-nightly` that still
    depended on the stable `lfx-<name>` would drag in `lfx>=X.Y` and fail to
    resolve. Give the bundles their own nightly track instead, mirroring how
    lfx/base/main are renamed. For every bundle this:

      * rewrites its `[project] name`     `lfx-<name>` -> `lfx-<name>-nightly`
      * rewrites its `[project] version`  `0.1.0`      -> `0.1.0.dev<N>`
      * repoints the root `[tool.uv.sources]` workspace entry to the new name
      * repoints the root `langflow` dependencies to `lfx-<name>-nightly==<dev>`,
        including extras forms like `lfx-docling[local]>=...` in
        `[project.optional-dependencies]` (the `[extra]` selector is preserved)

    The bundle's own `lfx` dep is repinned separately by
    `update_lfx_dep_in_bundles`. No-op when no bundles are present, and
    idempotent for bundles already carrying a `-nightly` name.
    """
    bundles_dir = BASE_DIR / "src" / "bundles"
    if not bundles_dir.is_dir():
        return

    root_content = ROOT_PYPROJECT.read_text(encoding="utf-8")

    for bundle_pyproject in sorted(bundles_dir.glob("*/pyproject.toml")):
        data = tomllib.loads(bundle_pyproject.read_text(encoding="utf-8"))
        old_name = data["project"]["name"]
        if old_name.endswith("-nightly"):
            continue
        new_name = f"{old_name}-nightly"
        new_version = _bundle_nightly_version(data["project"]["version"], lfx_version)

        rel_path = str(bundle_pyproject.relative_to(BASE_DIR))
        update_pyproject_name(rel_path, new_name)
        update_pyproject_version(rel_path, new_version)

        # Repoint the workspace source: `lfx-<name> = { workspace = true }`.
        source_pattern = re.compile(rf"^{re.escape(old_name)}(\s*=\s*\{{ workspace = true \}})", re.MULTILINE)
        if not source_pattern.search(root_content):
            msg = f"Workspace source entry for {old_name} not found in {ROOT_PYPROJECT}"
            raise ValueError(msg)
        root_content = source_pattern.sub(rf"{new_name}\1", root_content)

        # Repoint the root dependencies to the exact nightly pin. This covers
        # both the bare main dep `"lfx-<name>>=0.1.0"` and any extras form in
        # `[project.optional-dependencies]` such as `"lfx-docling[local]>=0.1.0"`.
        # The optional `[extra]` is captured and re-emitted so the selector
        # survives the rewrite (-> `"lfx-docling-nightly[local]==<dev>"`); a
        # missed extras ref would stay `lfx-<name>` and leak to PyPI, where no
        # `>=0.1.0` is published, breaking `uv lock`. The lookahead still
        # requires a version operator right after the name+optional-extra so we
        # match `lfx-arxiv>=...` / `lfx-docling[local]>=...` without also
        # matching an already-renamed `lfx-arxiv-nightly`.
        dep_pattern = re.compile(rf'"{re.escape(old_name)}(\[[^\]]+\])?(?=[<>=!~])[^"]*"')
        if not dep_pattern.search(root_content):
            msg = f"Root dependency on {old_name} not found in {ROOT_PYPROJECT}"
            raise ValueError(msg)
        root_content = dep_pattern.sub(rf'"{new_name}\g<1>=={new_version}"', root_content)

        print(f"Renamed bundle {old_name} -> {new_name}=={new_version}")

    ROOT_PYPROJECT.write_text(root_content, encoding="utf-8")


def update_lfx_for_nightly(lfx_tag: str, sdk_tag: str):
    """Update LFX package for nightly build.

    Args:
        lfx_tag: The nightly tag for LFX (e.g., "v0.1.0.dev0")
        sdk_tag: The nightly tag for the SDK (e.g., "v0.1.0.dev0")
    """
    lfx_pyproject_path = "src/lfx/pyproject.toml"

    # Update name to lfx-nightly
    update_pyproject_name(lfx_pyproject_path, "lfx-nightly")

    # Update version (strip 'v' prefix if present)
    version = lfx_tag.lstrip("v")
    update_pyproject_version(lfx_pyproject_path, version)

    # Update workspace dependency in root pyproject.toml
    update_lfx_workspace_dep("pyproject.toml", "lfx-nightly")

    sdk_version = sdk_tag.lstrip("v")
    update_sdk_dependency_in_lfx(lfx_pyproject_path, sdk_version)

    # Re-pin every bundle's lfx dep to the renamed workspace package so
    # `uv lock` resolves cleanly. No-op when no bundles are present.
    update_lfx_dep_in_bundles(version)

    # Give each bundle its own `-nightly` distribution and repoint the root
    # `langflow` deps + workspace sources at it, so `langflow-nightly` pulls
    # `lfx-<name>-nightly` (which pins `lfx-nightly`) instead of the stable
    # `lfx-<name>` (which pins an as-yet-unpublished stable `lfx`).
    rename_bundles_for_nightly(version)

    print(f"Updated LFX package to lfx-nightly version {version}")


def main():
    """Update LFX for nightly builds.

    Usage:
    update_lfx_version.py <lfx_tag> <sdk_tag>
    """
    expected_args = 3
    if len(sys.argv) != expected_args:
        print("Usage: update_lfx_version.py <lfx_tag> <sdk_tag>")
        sys.exit(1)

    lfx_tag = sys.argv[1]
    sdk_tag = sys.argv[2]
    update_lfx_for_nightly(lfx_tag, sdk_tag)


if __name__ == "__main__":
    main()
