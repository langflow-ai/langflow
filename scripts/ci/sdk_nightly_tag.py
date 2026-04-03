"""Script to generate nightly tags for the SDK package."""

import packaging.version
import requests
from packaging.version import Version

PYPI_SDK_URL = "https://pypi.org/pypi/langflow-sdk/json"
PYPI_SDK_NIGHTLY_URL = "https://pypi.org/pypi/langflow-sdk-nightly/json"


def get_latest_published_version(*, is_nightly: bool) -> Version:
    url = PYPI_SDK_NIGHTLY_URL if is_nightly else PYPI_SDK_URL

    res = requests.get(url, timeout=10)
    if res.status_code == requests.codes.not_found:
        msg = "Package not found on PyPI"
        raise requests.RequestException(msg)

    try:
        version_str = res.json()["info"]["version"]
    except (KeyError, ValueError) as e:
        msg = "Got unexpected response from PyPI"
        raise requests.RequestException(msg) from e
    return Version(version_str)


def create_sdk_tag():
    from pathlib import Path

    import tomllib

    sdk_pyproject_path = Path(__file__).parent.parent.parent / "src" / "sdk" / "pyproject.toml"
    pyproject_data = tomllib.loads(sdk_pyproject_path.read_text())

    current_version_str = pyproject_data["project"]["version"]
    current_version = Version(current_version_str)

    try:
        current_nightly_version = get_latest_published_version(is_nightly=True)
        nightly_base_version = current_nightly_version.base_version
    except (requests.RequestException, KeyError, ValueError):
        current_nightly_version = None
        nightly_base_version = None

    build_number = "0"
    latest_base_version = current_version.base_version

    if current_nightly_version and latest_base_version == nightly_base_version:
        build_number = str(current_nightly_version.dev + 1)

    new_nightly_version = latest_base_version + ".dev" + build_number

    if not new_nightly_version.startswith("v"):
        new_nightly_version = "v" + new_nightly_version

    packaging.version.Version(new_nightly_version)

    return new_nightly_version


if __name__ == "__main__":
    tag = create_sdk_tag()
    print(tag)
