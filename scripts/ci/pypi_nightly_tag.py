#!/usr/bin/env python
"""
Idea from https://github.com/streamlit/streamlit/blob/4841cf91f1c820a392441092390c4c04907f9944/scripts/pypi_nightly_create_tag.py
"""

from datetime import datetime
import sys

import packaging.version
import pytz
from packaging.version import Version

PYPI_LANGFLOW_NIGHTLY_URL = "https://pypi.org/pypi/langflow-nightly/json"
PYPI_LANGFLOW_BASE_NIGHTLY_URL = "https://pypi.org/pypi/langflow-base-nightly/json"

def get_latest_published_version(build_type: str) -> Version:
    import requests

    if build_type == "base":
        url = PYPI_LANGFLOW_BASE_NIGHTLY_URL
    elif build_type == "main":
        url = PYPI_LANGFLOW_NIGHTLY_URL
    else:
        raise ValueError(f"Invalid build type: {build_type}")

    res = requests.get(url)
    try:
        version_str = res.json()["info"]["version"]
    except Exception as e:
        raise RuntimeError("Got unexpected response from PyPI", e)
    return Version(version_str)


def create_tag(build_type: str):
    # current_version = get_latest_published_version(build_type)

    # X.Y.Z.dev.YYYYMMDD
    # version_with_date = (
    #     ".".join([str(x) for x in current_version.release])
    #     + ".dev"
    #     + datetime.now(pytz.timezone("UTC")).strftime("%Y%m%d")
    # )

    # This takes the base version of the current version and appends the
    # current date. If the last release was on the same day, we exit, as
    # pypi does not allow for overwriting the same version.
    #
    # We could use a different versioning scheme, such as just incrementing
    # an integer.
    # version_with_date = (
    #     ".".join([str(x) for x in current_version.release])
    #     + ".dev"
    #     + "0"
    # )
    # Alright, hardcoding the first release.
    if build_type == "main":
        version_with_date = "1.0.17.dev0"
    else:
        version_with_date = "0.0.95.dev0"

   # if version_with_date == latest_pypi_version:
    #     n = version_with_date.split("-")[-1]
    #     if isinstance(n, int):
    #         b_n = str(int(n) + 1)
    #         version_with_date += b_n
    #     else:
    #         version_with_date += "0"
    #     # raise Exception("Version {version_with_date} already published on PyPI")


    # Verify if version is PEP440 compliant.
    packaging.version.Version(version_with_date)

    return version_with_date


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise Exception("Specify base or main")

    build_type = sys.argv[1]
    tag = create_tag(build_type)
    print(tag)
