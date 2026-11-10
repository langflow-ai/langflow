"""Keep moving Docker tags on the highest published stable version."""

from __future__ import annotations

import argparse
import re
import sys
from typing import TYPE_CHECKING

from packaging.version import Version

if TYPE_CHECKING:
    from collections.abc import Iterable


def _stable_version(tag: str) -> Version | None:
    # Architecture tags, prereleases, and other aliases cannot establish latest.
    if re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", tag):
        return Version(tag)
    return None


def should_update_latest(version: str, released_tags: Iterable[str], *, prefix: str = "") -> bool:
    candidate = _stable_version(version)
    if candidate is None:
        return False

    for released_tag in released_tags:
        tag = released_tag.strip()
        if not tag.startswith(prefix):
            continue
        published = _stable_version(tag.removeprefix(prefix))
        if published is not None and published > candidate:
            return False
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version")
    parser.add_argument("--prefix", default="", help="Version tag prefix, such as 'base-'.")
    args = parser.parse_args()
    print(str(should_update_latest(args.version, sys.stdin, prefix=args.prefix)).lower())


if __name__ == "__main__":
    main()
