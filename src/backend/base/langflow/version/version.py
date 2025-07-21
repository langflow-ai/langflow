"""Module for package versioning."""

import contextlib
from importlib import metadata


def get_version() -> str:
    """Retrieves the version of the package from a possible list of package names.

    This accounts for after package names are updated for -nightly builds.

    Returns:
        str: The version of the package

    Raises:
        ValueError: If the package is not found from the list of package names.
    """
    pkg_names = [
        "langflow",
        "langflow-base",
        "langflow-nightly",
        "langflow-base-nightly",
    ]
    version = None
    for pkg_name in pkg_names:
        with contextlib.suppress(ImportError, metadata.PackageNotFoundError):
            version = metadata.version(pkg_name)

    if version is None:
        msg = f"Package not found from options {pkg_names}"
        raise ValueError(msg)

    return version


def is_pre_release(v: str) -> bool:
    """Returns a boolean indicating whether the version is a pre-release version.

    Returns a boolean indicating whether the version is a pre-release version,
    as per the definition of a pre-release segment from PEP 440.
    """
    return any(label in v for label in ["a", "b", "rc"])
