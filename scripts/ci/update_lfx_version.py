"""Update the canonical ``lfx`` package (and its SDK dep) for nightly builds.

The nightly publishes ``lfx`` and ``langflow-sdk`` under their CANONICAL names as ``.devN``
pre-releases -- it does NOT rename them to ``lfx-nightly`` / ``langflow-sdk-nightly``, and it does
NOT give the ``src/bundles/*`` packages their own nightly track. The stable ``lfx-*`` bundles
(pinning ``lfx>=X.Y.0,<(X+1).0.0``) then resolve against the single canonical ``lfx`` distribution,
so there is no ``lfx`` vs ``lfx-nightly`` install collision. See ``src/bundles/NIGHTLY.md``.

This script therefore only (a) sets ``lfx``'s version to the nightly ``.devN`` and (b) re-pins
lfx's ``langflow-sdk`` dependency to the exact canonical dev version.
"""

import re
import sys
from pathlib import Path

from update_pyproject_version import update_pyproject_version

# Add the current directory to the path so we can import the other scripts
current_dir = Path(__file__).resolve().parent
sys.path.append(str(current_dir))

BASE_DIR = Path(__file__).parent.parent.parent


def update_sdk_dependency_in_lfx(pyproject_path: str, sdk_version: str) -> None:
    """Pin lfx's ``langflow-sdk`` dependency to the exact canonical dev version.

    An exact ``==<dev>`` pin keeps the SDK in lockstep with the lfx built in the same run and,
    because it names a pre-release explicitly, enables pre-release resolution for ``langflow-sdk``
    down the dependency tree without requiring ``--pre``.
    """
    filepath = BASE_DIR / pyproject_path
    content = filepath.read_text(encoding="utf-8")

    pattern = re.compile(r'"langflow-sdk(?:-nightly)?(?:==|~=|>=)[\d.]+(?:\.(?:post|dev|a|b|rc)\d+)*"')
    replacement = f'"langflow-sdk=={sdk_version}"'

    if not pattern.search(content):
        msg = f"SDK dependency not found in {filepath}"
        raise ValueError(msg)

    content = pattern.sub(replacement, content)
    filepath.write_text(content, encoding="utf-8")


def update_lfx_for_nightly(lfx_tag: str, sdk_tag: str):
    """Update the canonical ``lfx`` package for a nightly build.

    Args:
        lfx_tag: The nightly tag for LFX (e.g., "v1.11.0.dev0").
        sdk_tag: The nightly tag for the SDK (e.g., "v0.1.0.dev0").
    """
    lfx_pyproject_path = "src/lfx/pyproject.toml"

    # Set the version (strip 'v' prefix if present); the package keeps its canonical `lfx` name.
    version = lfx_tag.lstrip("v")
    update_pyproject_version(lfx_pyproject_path, version)

    # Re-pin lfx's SDK dependency to the exact canonical dev version.
    sdk_version = sdk_tag.lstrip("v")
    update_sdk_dependency_in_lfx(lfx_pyproject_path, sdk_version)

    print(f"Updated lfx to nightly version {version}")


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
