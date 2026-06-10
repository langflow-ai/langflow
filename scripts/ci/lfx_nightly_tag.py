"""Generate the nightly tag for the canonical ``lfx`` package.

The nightly publishes ``lfx==<base>.devN`` to the canonical ``lfx`` PyPI project (not a separate
``lfx-nightly`` distribution), so the dev counter is computed against ``lfx``'s own release history.
``<base>`` is the in-development version from
``src/lfx/pyproject.toml`` (the latest ``release-*`` branch the nightly builds from) and ``N`` is
``max(existing same-base devN) + 1``.

Only ``.devN`` releases whose ``base_version`` matches contribute; stable finals (e.g. ``1.10.0``)
are ignored. A 404 (no releases yet) yields ``dev0``; any other lookup failure is fatal (fail
closed) so a transient error cannot regenerate an already-published version. See
``src/bundles/NIGHTLY.md``.
"""

from pathlib import Path

import packaging.version
import requests
import tomllib
from packaging.version import Version

PYPI_LFX_URL = "https://pypi.org/pypi/lfx/json"


def _lfx_base_version() -> str:
    """Return the base_version (e.g. "1.11.0") from src/lfx/pyproject.toml."""
    lfx_pyproject_path = Path(__file__).parent.parent.parent / "src" / "lfx" / "pyproject.toml"
    pyproject_data = tomllib.loads(lfx_pyproject_path.read_text())
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


def create_lfx_tag() -> str:
    """Return the next ``lfx`` nightly tag (with a leading ``v``)."""
    base_version = _lfx_base_version()
    dev_numbers = _dev_numbers(PYPI_LFX_URL, base_version)
    next_dev = max(dev_numbers) + 1 if dev_numbers else 0

    new_nightly_version = f"v{base_version}.dev{next_dev}"

    # Verify the version is PEP 440 compliant.
    packaging.version.Version(new_nightly_version)

    return new_nightly_version


if __name__ == "__main__":
    print(create_lfx_tag())
