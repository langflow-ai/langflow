#!/usr/bin/env python3

from __future__ import annotations

import argparse
import sys
from typing import TYPE_CHECKING

import packaging.version
from packaging.version import Version

if TYPE_CHECKING:
    from collections.abc import Iterable


def _read_released_versions(values: list[str]) -> list[str]:
    if values == ["-"]:
        return [line.strip() for line in sys.stdin if line.strip()]
    return [value.strip() for value in values if value.strip()]


def next_rc_number(package_version: str, released_versions: Iterable[str]) -> int:
    base_version = Version(package_version.strip().lstrip("v")).base_version
    rc_numbers: list[int] = []
    exact_final_exists = False

    for released_version_str in released_versions:
        normalized_version_str = released_version_str.strip().lstrip("v")
        if not normalized_version_str:
            continue
        try:
            released_version = Version(normalized_version_str)
        except packaging.version.InvalidVersion:
            continue

        if released_version.base_version != base_version:
            continue

        if released_version.pre and released_version.pre[0] == "rc":
            rc_numbers.append(released_version.pre[1])
        elif not released_version.is_prerelease:
            exact_final_exists = True

    if rc_numbers:
        return max(rc_numbers) + 1
    if exact_final_exists:
        return 1
    return 0


def create_tag(
    package_version: str,
    released_versions: Iterable[str] | str | None,
    rc_number: int | None = None,
) -> str:
    if released_versions is None:
        versions: list[str] = []
    elif isinstance(released_versions, str):
        versions = [released_versions]
    else:
        versions = list(released_versions)

    base_version = Version(package_version.strip().lstrip("v")).base_version
    next_rc = next_rc_number(base_version, versions)
    if rc_number is not None:
        next_rc = max(next_rc, rc_number)

    return str(Version(f"{base_version}rc{next_rc}"))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Return the next rc pre-release for a package base version.",
    )
    parser.add_argument("package_version")
    parser.add_argument(
        "released_versions",
        nargs="*",
        help="Released versions to inspect, or '-' to read one version per line from stdin.",
    )
    parser.add_argument(
        "--rc-number",
        type=int,
        default=None,
        help="Minimum rc number to use. This lets a workflow apply one shared rc number across packages.",
    )
    parser.add_argument(
        "--print-rc-number",
        action="store_true",
        help="Print only the next rc number instead of the full version.",
    )
    args = parser.parse_args()

    released_versions = _read_released_versions(args.released_versions)
    if args.print_rc_number:
        print(next_rc_number(args.package_version, released_versions))
    else:
        print(create_tag(args.package_version, released_versions, args.rc_number))


if __name__ == "__main__":
    main()
