"""Pin langflow-base's LFX requirements to the coordinated release version."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from packaging.version import Version

_LFX_REQUIREMENT = re.compile(r'"lfx(?P<extras>\[[^\]]+\])?(?=[<>=!~;"])[^";]*(?P<marker>;[^"]*)?"')


def update_lfx_requirements(content: str, version: str) -> str:
    """Update only the canonical LFX requirements, preserving extras and markers."""
    version = str(Version(version))

    def replace_requirement(match: re.Match[str]) -> str:
        extras = match.group("extras") or ""
        marker = match.group("marker") or ""
        return f'"lfx{extras}=={version}{marker}"'

    updated, count = _LFX_REQUIREMENT.subn(replace_requirement, content)
    if count == 0:
        msg = "No canonical LFX requirement found"
        raise ValueError(msg)
    return updated


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("pyproject", type=Path)
    parser.add_argument("version")
    args = parser.parse_args()

    content = args.pyproject.read_text(encoding="utf-8")
    args.pyproject.write_text(update_lfx_requirements(content, args.version), encoding="utf-8")


if __name__ == "__main__":
    main()
