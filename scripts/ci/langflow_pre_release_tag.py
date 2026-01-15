#!/usr/bin/env python

import sys

ARGUMENT_NUMBER = 3


def create_tag(package_version: str, latest_pypi_version: str | None) -> str:
    new_pre_release_version = package_version + ".rc1"
    if latest_pypi_version and package_version in latest_pypi_version and ".rc" in latest_pypi_version:
        rc_number = int(latest_pypi_version.split(".rc")[-1])
        new_pre_release_version = package_version + ".rc" + str(rc_number + 1)
    return new_pre_release_version


if __name__ == "__main__":
    if len(sys.argv) != ARGUMENT_NUMBER:
        msg = "Specify base or main"
        raise ValueError(msg)

    package_version: str = sys.argv[1]
    latest_pypi_version: str = sys.argv[2]
    tag = create_tag(package_version, latest_pypi_version)
    print(tag)
