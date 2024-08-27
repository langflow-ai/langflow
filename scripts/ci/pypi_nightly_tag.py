#!/usr/bin/env python
"""
Idea from https://github.com/streamlit/streamlit/blob/4841cf91f1c820a392441092390c4c04907f9944/scripts/pypi_nightly_create_tag.py
"""

from datetime import datetime
import sys

import packaging.version
import pytz
from packaging.version import Version

PYPI_LANGFLOW_URL = "https://pypi.org/pypi/langflow/json"
PYPI_LANGFLOW_BASE_URL = "https://pypi.org/pypi/langflow-base/json"


def get_latest_langflow_version(build_type: str) -> Version:
    import requests

    if build_type == "base":
        url = PYPI_LANGFLOW_BASE_URL
    elif build_type == "main":
        url = PYPI_LANGFLOW_URL
    else:
        raise ValueError(f"Invalid build type: {build_type}")

    res = requests.get(url)
    try:
        version_str = res.json()["info"]["version"]
    except Exception as e:
        raise RuntimeError("Got unexpected response from PyPI", e)
    return Version(version_str)


def create_tag(build_type: str):
    current_version = get_latest_langflow_version(build_type)

    # Append todays date
    version_with_date = (
        ".".join([str(x) for x in current_version.release])
        + ".dev"
        + datetime.now(pytz.timezone("US/Pacific")).strftime("%Y%m%d")
    )

    # Verify if version is PEP440 compliant.
    packaging.version.Version(version_with_date)

    return version_with_date


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise Exception("Specify base or main")

    build_type = sys.argv[1]
    tag = create_tag(build_type)
    print(tag)
