#!/usr/bin/env python3

import re
import sys

ARGUMENT_NUMBER = 3


def create_tag(package_version: str, latest_released_version: str | None) -> str:
    # normalize optional leading 'v' and whitespace
    pkg = package_version.strip().lstrip("v")
    latest = None
    if latest_released_version is not None:
        lr = latest_released_version.strip()
        if lr != "":
            latest = lr.lstrip("v")

    new_pre_release_version = f"{pkg}.rc0"

    if latest:
        # match either exact pkg or pkg.rcN
        m = re.match(rf"^{re.escape(pkg)}(?:\.rc(\d+))?$", latest)
        if m:
            if m.group(1):
                rc_number = int(m.group(1)) + 1
                new_pre_release_version = f"{pkg}.rc{rc_number}"
            else:
                new_pre_release_version = f"{pkg}.rc1"

    return new_pre_release_version


if __name__ == "__main__":
    if len(sys.argv) != ARGUMENT_NUMBER:
        msg = "Specify package_version and latest_released_version (use empty string for none)."
        raise ValueError(msg)

    package_version = sys.argv[1]
    latest_released_version = sys.argv[2]
    print(create_tag(package_version, latest_released_version))
