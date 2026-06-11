#!/usr/bin/env python
"""Idea from https://github.com/streamlit/streamlit/blob/4841cf91f1c820a392441092390c4c04907f9944/scripts/pypi_nightly_create_tag.py.

The nightly is published as canonical `.devN` pre-releases (e.g. `langflow==X.Y.Z.devN`), NOT
separate `*-nightly` distributions, so the dev counter is computed against the canonical
`langflow` / `langflow-base` PyPI histories (their `.devN` pre-releases; stable finals never
contribute). See `src/bundles/NIGHTLY.md`.

`langflow` (the nightly pre-release) pins an EXACT dependency on `langflow-base[complete]==X.Y.Z.devN`.
For the latest published nightly `langflow` to be installable, the base version it pins must
exist on PyPI. The two packages are therefore versioned in lockstep: they share a single dev
number so that, in a single nightly run (publish order base -> main, gated), main's `devN` pin
always references the base `devN` built and published in the same run.

The shared dev number is `max(dev across BOTH packages' PyPI histories) + 1`, restricted to
releases whose base_version matches the root pyproject. Both "main" and "base" build types
return the identical tag; the "both" mode emits it twice so the workflow can read the release
and base tags from a single invocation (one PyPI snapshot) and avoid any cross-call drift.
"""

import sys
from pathlib import Path

import packaging.version
import requests
from packaging.version import Version

# Count dev releases against the CANONICAL projects (not `*-nightly`), since the nightly is
# published as canonical `.devN` pre-releases of `langflow` / `langflow-base`.
PYPI_LANGFLOW_URL = "https://pypi.org/pypi/langflow/json"
PYPI_LANGFLOW_BASE_URL = "https://pypi.org/pypi/langflow-base/json"

# main and base MUST share one dev number, so the shared number is derived from both packages.
PYPI_CANONICAL_URLS = (PYPI_LANGFLOW_URL, PYPI_LANGFLOW_BASE_URL)

ARGUMENT_NUMBER = 2
VALID_BUILD_TYPES = ("main", "base", "both")


def _root_base_version() -> str:
    """Return the base_version (e.g. "1.10.0") from the root pyproject.toml.

    Both langflow-nightly and langflow-base-nightly are versioned from the ROOT pyproject on
    purpose. Do not switch base to read src/backend/base/pyproject.toml, or the two dev counters
    will fork again and the exact `==` pin can reference a version that was never published.
    """
    import tomllib

    pyproject_path = Path(__file__).parent.parent.parent / "pyproject.toml"
    pyproject_data = tomllib.loads(pyproject_path.read_text())
    return Version(pyproject_data["project"]["version"]).base_version


def _all_dev_numbers(url: str, base_version: str) -> list[int]:
    """Dev numbers of every release of url whose base_version matches base_version.

    A 404 means the package genuinely has no releases yet (e.g. the first-ever nightly): it
    contributes nothing and returns an empty list. Every OTHER failure -- a network error, a
    non-404 HTTP status (5xx / 403 / ...), or a malformed 200 response -- is fatal and raises,
    so the nightly job aborts BEFORE mutating tags. Failing closed prevents a transient lookup
    failure on the higher-versioned package from lowering max(dev) + 1 and regenerating an
    already-published version. Non-dev/final releases and releases from another base_version
    never contribute.
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


def _shared_nightly_version() -> str:
    """Compute the single dev number shared by langflow-nightly and langflow-base-nightly."""
    base_version = _root_base_version()

    dev_numbers = [dev for url in PYPI_CANONICAL_URLS for dev in _all_dev_numbers(url, base_version)]

    # First-ever nightly for this base_version -> dev0. Otherwise max+1, so the result is
    # strictly ahead of BOTH packages' newest same-series dev release.
    next_dev = max(dev_numbers) + 1 if dev_numbers else 0

    new_nightly_version = f"v{base_version}.dev{next_dev}"

    # Verify the version is PEP 440 compliant.
    packaging.version.Version(new_nightly_version)

    return new_nightly_version


def create_tag(build_type: str) -> str:
    """Return the shared nightly tag (with a leading ``v``).

    ``build_type`` is accepted for backward compatibility and validated, but "main" and "base"
    always return the identical version by design (lockstep versioning).
    """
    if build_type not in VALID_BUILD_TYPES:
        msg = f"Invalid build type: {build_type}"
        raise ValueError(msg)
    return _shared_nightly_version()


if __name__ == "__main__":
    if len(sys.argv) != ARGUMENT_NUMBER:
        msg = "Specify base, main, or both"
        raise ValueError(msg)

    requested_build_type = sys.argv[1]
    tag = create_tag(requested_build_type)
    if requested_build_type == "both":
        # Emit twice so the workflow can capture release_tag and base_tag from a SINGLE
        # invocation -> one PyPI snapshot -> guaranteed-identical tags.
        print(tag)
        print(tag)
    else:
        print(tag)
