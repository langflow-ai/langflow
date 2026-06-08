"""Generate the nightly tag for the canonical ``langflow-sdk`` package.

Mirrors ``lfx_nightly_tag.py`` but for the SDK -- the nightly publishes ``langflow-sdk==<base>.devN``
to the canonical ``langflow-sdk`` PyPI project, so the dev counter is computed against that
project's ``.devN`` history (stable finals never contribute). ``<base>`` comes from
``src/sdk/pyproject.toml``. See ``src/bundles/NIGHTLY.md``.
"""

from pathlib import Path

import packaging.version
import requests
import tomllib
from packaging.version import Version

PYPI_SDK_URL = "https://pypi.org/pypi/langflow-sdk/json"


def _sdk_base_version() -> str:
    """Return the base_version (e.g. "0.1.0") from src/sdk/pyproject.toml."""
    sdk_pyproject_path = Path(__file__).parent.parent.parent / "src" / "sdk" / "pyproject.toml"
    pyproject_data = tomllib.loads(sdk_pyproject_path.read_text())
    return Version(pyproject_data["project"]["version"]).base_version


def _dev_numbers(url: str, base_version: str) -> list[int]:
    """Dev numbers of every release at ``url`` whose base_version matches ``base_version``.

    A 404 means the package has no releases yet and returns an empty list. Every other failure --
    a network error, a non-404 HTTP status, or a malformed 200 -- is fatal and raises, so the
    nightly job aborts BEFORE mutating tags rather than regenerating an already-published version.
    """
    res = requests.get(url, timeout=10)
    if res.status_code == requests.codes.not_found:
        return []
    res.raise_for_status()
    try:
        releases = res.json()["releases"]
    except (ValueError, KeyError) as e:
        msg = f"Unexpected response from {url!r}: missing 'releases' mapping"
        raise RuntimeError(msg) from e

    dev_numbers: list[int] = []
    for version_str in releases:
        try:
            version = Version(version_str)
        except packaging.version.InvalidVersion:
            continue
        if version.base_version == base_version and version.dev is not None:
            dev_numbers.append(version.dev)
    return dev_numbers


def create_sdk_tag() -> str:
    """Return the next ``langflow-sdk`` nightly tag (with a leading ``v``)."""
    base_version = _sdk_base_version()
    dev_numbers = _dev_numbers(PYPI_SDK_URL, base_version)
    next_dev = max(dev_numbers) + 1 if dev_numbers else 0

    new_nightly_version = f"v{base_version}.dev{next_dev}"

    # Verify the version is PEP 440 compliant.
    packaging.version.Version(new_nightly_version)

    return new_nightly_version


if __name__ == "__main__":
    print(create_sdk_tag())
