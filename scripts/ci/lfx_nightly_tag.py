"""Script to generate nightly tags for LFX package."""

import packaging.version
import requests
from packaging.version import Version

PYPI_LFX_URL = "https://pypi.org/pypi/lfx/json"
PYPI_LFX_NIGHTLY_URL = "https://pypi.org/pypi/lfx-nightly/json"


def get_latest_published_version(*, is_nightly: bool) -> Version:
    url = PYPI_LFX_NIGHTLY_URL if is_nightly else PYPI_LFX_URL

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


def create_lfx_tag():
    # Since LFX has never been released, we'll use the version from pyproject.toml as base
    from pathlib import Path

    import tomllib

    # Read version from pyproject.toml
    lfx_pyproject_path = Path(__file__).parent.parent.parent / "src" / "lfx" / "pyproject.toml"
    pyproject_data = tomllib.loads(lfx_pyproject_path.read_text())

    current_version_str = pyproject_data["project"]["version"]
    current_version = Version(current_version_str)

    try:
        current_nightly_version = get_latest_published_version(is_nightly=True)
        nightly_base_version = current_nightly_version.base_version
    except (requests.RequestException, KeyError, ValueError):
        # If LFX nightly doesn't exist on PyPI yet, this is the first nightly
        current_nightly_version = None
        nightly_base_version = None

    build_number = "0"
    latest_base_version = current_version.base_version

    if current_nightly_version and latest_base_version == nightly_base_version:
        # If the latest version is the same as the nightly version, increment the build number
        build_number = str(current_nightly_version.dev + 1)

    new_nightly_version = latest_base_version + ".dev" + build_number

    # Prepend "v" to the version, if DNE.
    # This is an update to the nightly version format.
    if not new_nightly_version.startswith("v"):
        new_nightly_version = "v" + new_nightly_version

    # Verify if version is PEP440 compliant.
    packaging.version.Version(new_nightly_version)

    return new_nightly_version


if __name__ == "__main__":
    tag = create_lfx_tag()
    print(tag)
