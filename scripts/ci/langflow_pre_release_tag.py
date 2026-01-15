#!/usr/bin/env python

import sys

ARGUMENT_NUMBER = 3


def create_tag(package_version: str, latest_released_version: str | None) -> str:
    new_pre_release_version = package_version + ".rc1"
    if latest_released_version and package_version in latest_released_version and ".rc" in latest_released_version:
        rc_number = int(latest_released_version.split(".rc")[-1])
        new_pre_release_version = package_version + ".rc" + str(rc_number + 1)
    return new_pre_release_version


if __name__ == "__main__":
    if len(sys.argv) != ARGUMENT_NUMBER:
        msg = "Specify package_version and latest_released_version"
        raise ValueError(msg)

    package_version: str = sys.argv[1]
    latest_released_version: str = sys.argv[2]
    tag = create_tag(package_version, latest_released_version)
    print(tag)
