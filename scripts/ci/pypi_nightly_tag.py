#!/usr/bin/env python
"""Idea from https://github.com/streamlit/streamlit/blob/4841cf91f1c820a392441092390c4c04907f9944/scripts/pypi_nightly_create_tag.py."""

import sys

import packaging.version
from packaging.version import Version

PYPI_LANGFLOW_URL = "https://pypi.org/pypi/langflow/json"
PYPI_LANGFLOW_NIGHTLY_URL = "https://pypi.org/pypi/langflow-nightly/json"

PYPI_LANGFLOW_BASE_URL = "https://pypi.org/pypi/langflow-base/json"
PYPI_LANGFLOW_BASE_NIGHTLY_URL = "https://pypi.org/pypi/langflow-base-nightly/json"

ARGUMENT_NUMBER = 2


def get_latest_published_version(build_type: str, *, is_nightly: bool) -> Version:
    import requests

    url = ""
    if build_type == "base":
        url = PYPI_LANGFLOW_BASE_NIGHTLY_URL if is_nightly else PYPI_LANGFLOW_BASE_URL
    elif build_type == "main":
        url = PYPI_LANGFLOW_NIGHTLY_URL if is_nightly else PYPI_LANGFLOW_URL
    else:
        msg = f"Invalid build type: {build_type}"
        raise ValueError(msg)

    res = requests.get(url, timeout=10)
    try:
        version_str = res.json()["info"]["version"]
    except Exception as e:
        msg = "Got unexpected response from PyPI"
        raise RuntimeError(msg) from e
    return Version(version_str)


def create_tag(build_type: str):
    current_version = get_latest_published_version(build_type, is_nightly=False)
    current_nightly_version = get_latest_published_version(build_type, is_nightly=True)

    build_number = "0"
    latest_base_version = current_version.base_version
    nightly_base_version = current_nightly_version.base_version

    if latest_base_version == nightly_base_version:
        # If the latest version is the same as the nightly version, increment the build number
        build_number = str(current_nightly_version.dev + 1)

    new_nightly_version = latest_base_version + ".dev" + build_number

    # Prepend "v" to the version, if DNE.
    # This is an update to the nightly version format.
    if not new_nightly_version.startswith("v"):
        new_nightly_version = "v" + new_nightly_version

    # X.Y.Z.dev.YYYYMMDD
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
    #     + datetime.now(pytz.timezone("UTC")).strftime("%Y%m%d")
    # )

    # Verify if version is PEP440 compliant.
    packaging.version.Version(new_nightly_version)

    return new_nightly_version


if __name__ == "__main__":
    if len(sys.argv) != ARGUMENT_NUMBER:
        msg = "Specify base or main"
        raise ValueError(msg)

    build_type = sys.argv[1]
    tag = create_tag(build_type)
    print(tag)
