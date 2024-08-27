#!/usr/bin/env python
"""
Idea from https://github.com/streamlit/streamlit/blob/4841cf91f1c820a392441092390c4c04907f9944/scripts/pypi_nightly_create_tag.py
"""

from datetime import datetime

import packaging.version
import pytz
from packaging.version import Version

PYPI_LANGFLOW_URL = "https://pypi.org/pypi/langflow/json"


def get_latest_langflow_version() -> Version:
    import requests

    res = requests.get(PYPI_LANGFLOW_URL)
    try:
        version_str = res.json()["info"]["version"]
    except Exception as e:
        raise RuntimeError("Got unexpected response from PyPI", e)
    return Version(version_str)


def create_tag():
    current_version = get_latest_langflow_version()

    # Append todays date
    version_with_date = (
        ".".join([str(x) for x in current_version])
        + ".dev"
        + datetime.now(pytz.timezone("US/Pacific")).strftime("%Y%m%d")
    )

    # Verify if version is PEP440 compliant.
    packaging.version.Version(version_with_date)

    return version_with_date


if __name__ == "__main__":
    tag = create_tag()
    print(tag)
